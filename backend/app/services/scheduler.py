"""Adaptive ingest scheduler — time-multiplexes cameras under a concurrency budget.

The sandbox portal (and, at scale, district networks) can only serve a limited
number of simultaneous streams. Instead of failing beyond that limit, SUTRA
schedules ingest:

- `monitoring=True` marks a camera as *in the sampling pool* (desired state);
  this scheduler reconciles the pool against `ingest_budget` actual connections.
- **Residents** hold their slot: pinned cameras and alert-boosted cameras.
  When a watchlist alert fires, the hit camera and its nearest neighbours are
  boosted — coverage tightens around the vehicle instead of rotating away.
- Remaining slots **rotate** through the pool on a dwell timer,
  least-recently-served first, with staggered connects (no thundering herd).
- File sources cost the portal nothing and are always ingested.
"""

import logging
import threading
import time

from ..config import settings
from ..db import SessionLocal
from ..models import Camera
from . import sampler

log = logging.getLogger("sutra.scheduler")


class IngestScheduler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="ingest-scheduler")
        self.stop_flag = threading.Event()
        self.pinned: set[int] = set()
        self.boosted: dict[int, float] = {}       # camera_id -> monotonic expiry
        self._slot_started: dict[int, float] = {} # camera_id -> monotonic slot start
        self._last_served: dict[int, float] = {}  # camera_id -> monotonic last rotation end
        self._lock = threading.Lock()
        self.last_tick: dict = {}

    # ------------------------------------------------------------ public API

    def pin(self, camera_id: int) -> None:
        with self._lock:
            self.pinned.add(camera_id)

    def unpin(self, camera_id: int) -> None:
        with self._lock:
            self.pinned.discard(camera_id)

    def boost(self, camera_id: int) -> list[int]:
        """Alert reaction: keep this camera + nearest neighbours resident."""
        targets = [camera_id]
        db = SessionLocal()
        try:
            cam = db.get(Camera, camera_id)
            if cam and cam.lat is not None and settings.boost_neighbors > 0:
                others = (
                    db.query(Camera)
                    .filter(Camera.monitoring, Camera.id != camera_id, Camera.lat.isnot(None))
                    .all()
                )
                others.sort(key=lambda o: (o.lat - cam.lat) ** 2 + (o.lon - cam.lon) ** 2)
                targets += [o.id for o in others[: settings.boost_neighbors]]
        finally:
            db.close()
        expiry = time.monotonic() + settings.alert_boost_s
        with self._lock:
            for t in targets:
                self.boosted[t] = expiry
        log.info("alert boost: cameras %s resident for %ds", targets, settings.alert_boost_s)
        return targets

    def status(self) -> dict:
        now = time.monotonic()
        with self._lock:
            return {
                "budget": settings.ingest_budget,
                "pinned": sorted(self.pinned),
                "boosted": {str(k): round(v - now, 1) for k, v in self.boosted.items()},
                "slot_ages_s": {str(k): round(now - v, 1) for k, v in self._slot_started.items()},
                "dwell_s": settings.rotation_dwell_s,
                **self.last_tick,
            }

    # ------------------------------------------------------------ main loop

    def run(self) -> None:
        log.info("ingest scheduler started (budget=%d, dwell=%.0fs)", settings.ingest_budget, settings.rotation_dwell_s)
        while not self.stop_flag.wait(settings.scheduler_tick_s):
            try:
                self.tick()
            except Exception:
                log.exception("scheduler tick failed")

    def tick(self) -> None:
        now = time.monotonic()
        db = SessionLocal()
        try:
            pool = db.query(Camera).filter(Camera.monitoring).all()
        finally:
            db.close()

        files = [c for c in pool if c.source_type == "file"]
        live = [c for c in pool if c.source_type != "file"]
        pool_ids = {c.id for c in pool}
        running = sampler.running_ids()

        # cameras removed from the pool → stop their workers
        for cam_id in running - pool_ids:
            sampler.stop_worker(cam_id)
            self._slot_started.pop(cam_id, None)

        # file sources: always on, no budget cost
        to_start: list[Camera] = [c for c in files if c.id not in running]

        with self._lock:
            self.boosted = {k: v for k, v in self.boosted.items() if v > now}
            resident_ids = [c.id for c in live if c.id in self.pinned]
            resident_ids += [c.id for c in live if c.id in self.boosted and c.id not in resident_ids]
        resident_ids = resident_ids[: settings.ingest_budget]  # residents never exceed budget

        slots_left = settings.ingest_budget - len(resident_ids)

        # rotating cameras keep their slot until dwell expires
        rotating = [c for c in live if c.id not in resident_ids]
        keep = [
            c for c in rotating
            if c.id in running and now - self._slot_started.get(c.id, 0) < settings.rotation_dwell_s
        ][:slots_left]

        # fill remaining slots least-recently-served first; a camera currently
        # holding a slot counts as served since its slot start, else expired
        # low-id cameras tie with never-served ones and starve the rotation
        def serve_key(c: Camera) -> float:
            return max(self._last_served.get(c.id, 0.0), self._slot_started.get(c.id, 0.0))

        queued = sorted((c for c in rotating if c not in keep), key=serve_key)
        fill = queued[: max(0, slots_left - len(keep))]

        # a running camera re-picked into fill gets a fresh dwell lease
        for c in fill:
            if c.id in running:
                self._slot_started[c.id] = now

        chosen_ids = set(resident_ids) | {c.id for c in keep} | {c.id for c in fill}

        # stop rotating cameras that lost their slot
        for c in rotating:
            if c.id in running and c.id not in chosen_ids:
                sampler.stop_worker(c.id)
                self._last_served[c.id] = now
                self._slot_started.pop(c.id, None)

        # start whatever should be running but isn't (staggered)
        by_id = {c.id: c for c in pool}
        for cam_id in chosen_ids:
            cam = by_id.get(cam_id)
            if cam and cam.id not in running:
                to_start.append(cam)
        for i, cam in enumerate(to_start):
            if cam.id in sampler.running_ids():
                continue
            try:
                sampler.start_worker(cam.id, cam.source_url, cam.source_type)
                self._slot_started[cam.id] = time.monotonic()
            except RuntimeError as e:
                log.warning("could not start cam %s: %s", cam.id, e)
                break
            if i < len(to_start) - 1:
                time.sleep(settings.connect_stagger_s)

        self.last_tick = {
            "pool": len(pool),
            "live_pool": len(live),
            "file_sources": len(files),
            "residents": resident_ids,
            "active_rotating": sorted(c.id for c in keep + fill),
            "queued": [c.id for c in queued[max(0, slots_left - len(keep)):]],
        }


engine = IngestScheduler()
