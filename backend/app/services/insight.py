"""SUTRA Insight — the analytics engine between Bridge (frames) and Watch (alerts).

Camera ingest threads push sampled frames into a bounded queue (dropping when
saturated — live analytics must never back-pressure ingestion). A small pool of
inference workers runs ANPR, persists detections (deduped per camera+plate
window), and correlates every read against the active watchlist, firing alerts
through the Watch WebSocket channel.
"""

import logging
import queue
import threading
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from ..config import settings
from ..db import SessionLocal
from ..models import Alert, Camera, Detection, WatchlistVehicle
from ..routers.watch import broadcast_alert
from . import anpr
from .scheduler import engine as ingest_scheduler

log = logging.getLogger("sutra.insight")


class PlateTrack:
    """Reads of one physical vehicle as it crosses one camera's view."""

    __slots__ = ("camera_id", "center", "reads", "best", "last_frame_no", "first_ts")

    def __init__(self, camera_id: int, hit: anpr.PlateHit, frame_no: int, frame: np.ndarray):
        self.camera_id = camera_id
        self.reads: list[tuple[str, list[float]]] = []
        self.best: tuple[float, anpr.PlateHit, np.ndarray] | None = None  # (conf, hit, frame)
        self.first_ts = datetime.now(timezone.utc)
        self.update(hit, frame_no, frame)

    def update(self, hit: anpr.PlateHit, frame_no: int, frame: np.ndarray) -> None:
        x1, y1, x2, y2 = hit.bbox
        self.center = ((x1 + x2) / 2, (y1 + y2) / 2)
        self.last_frame_no = frame_no
        self.reads.append((hit.text, hit.char_probs))
        if self.best is None or hit.ocr_conf > self.best[0]:
            self.best = (hit.ocr_conf, hit, frame.copy())

    def matches(self, hit: anpr.PlateHit, frame_no: int, max_dist: float, max_gap: int) -> bool:
        if frame_no - self.last_frame_no > max_gap:
            return False
        x1, y1, x2, y2 = hit.bbox
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if ((cx - self.center[0]) ** 2 + (cy - self.center[1]) ** 2) ** 0.5 > max_dist:
            return False
        # same vehicle usually reads similarly — reject wildly different text
        return anpr.levenshtein(anpr.fold_plate(hit.text), anpr.fold_plate(self.reads[-1][0])) <= 3


class InsightEngine:
    def __init__(self):
        self.queue: queue.Queue = queue.Queue(maxsize=settings.inference_queue_size)
        self.workers: list[threading.Thread] = []
        self.running = False
        # stats
        self.frames_in = 0
        self.frames_dropped = 0
        self.frames_processed = 0
        self.plates_read = 0
        self.detections_saved = 0
        self.alerts_fired = 0
        self.last_latency_ms = 0.0
        self.tracks_finalized = 0
        self.reads_rejected = 0
        # dedup caches: (camera_id, plate) -> last monotonic ts
        self._recent_detections: dict[tuple[int, str], float] = {}
        self._recent_alerts: dict[tuple[int, str], float] = {}
        self._lock = threading.Lock()
        # temporal voting state, all guarded by _track_lock
        self._tracks: dict[int, list[PlateTrack]] = {}      # camera_id -> active tracks
        self._frame_counters: dict[int, int] = {}           # camera_id -> sampled frame count
        self._track_lock = threading.Lock()

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        for i in range(settings.inference_workers):
            t = threading.Thread(target=self._worker, daemon=True, name=f"insight-{i}")
            t.start()
            self.workers.append(t)
        log.info("insight engine started (%d workers)", settings.inference_workers)

    def stop(self) -> None:
        self.running = False

    # ------------------------------------------------------------- ingestion

    def on_frame(self, camera_id: int, frame: np.ndarray, ts: float) -> None:
        """Bridge frame subscriber — called from camera ingest threads.

        Blocks briefly when the queue is full (back-pressure paces fast file
        decoding); drops only after the timeout so live ingest never stalls long.
        """
        self.frames_in += 1
        try:
            self.queue.put((camera_id, frame, time.monotonic()), timeout=2.0)
        except queue.Full:
            self.frames_dropped += 1

    # ------------------------------------------------------------- workers

    def _worker(self) -> None:
        while True:
            try:
                camera_id, frame, enqueued_at = self.queue.get(timeout=1.0)
            except queue.Empty:
                if not self.running:
                    return
                continue
            try:
                t0 = time.monotonic()
                hits = anpr.analyse_frame(frame)
                self.last_latency_ms = round((time.monotonic() - t0) * 1000, 1)
                self.frames_processed += 1
                self._track_frame(camera_id, frame, hits)
            except Exception:
                log.exception("inference failed for camera %s", camera_id)

    # --------------------------------------------------------- temporal voting

    def _track_frame(self, camera_id: int, frame: np.ndarray, hits: list[anpr.PlateHit]) -> None:
        """Assign hits to per-vehicle tracks; finalize tracks whose vehicle left."""
        diag = (frame.shape[0] ** 2 + frame.shape[1] ** 2) ** 0.5
        max_dist = diag * 0.22  # a plate moves ≤ ~22% of the frame between samples
        max_gap = 4             # sampled frames a track survives without a read
        expired: list[PlateTrack] = []
        with self._track_lock:
            frame_no = self._frame_counters.get(camera_id, 0) + 1
            self._frame_counters[camera_id] = frame_no
            tracks = self._tracks.setdefault(camera_id, [])
            for hit in hits:
                self.plates_read += 1
                for track in tracks:
                    if track.matches(hit, frame_no, max_dist, max_gap):
                        track.update(hit, frame_no, frame)
                        break
                else:
                    tracks.append(PlateTrack(camera_id, hit, frame_no, frame))
            still_active = []
            for track in tracks:
                (expired if frame_no - track.last_frame_no > max_gap else still_active).append(track)
            self._tracks[camera_id] = still_active
        for track in expired:
            self._finalize_track(track)

    def _finalize_track(self, track: PlateTrack) -> None:
        voted_raw, voted_conf = anpr.vote_plate(track.reads)
        if not voted_raw or voted_conf < settings.plate_ocr_min_conf:
            return
        normalised, valid = anpr.normalise_plate(voted_raw)
        # only store reads that resolve to a real registration format — partial
        # reads like "113117" are noise in an evidence log and can never match
        # a watchlist entry anyway
        if not valid:
            self.reads_rejected += 1
            return
        _, best_hit, best_frame = track.best
        final = anpr.PlateHit(
            text=voted_raw,
            normalised=normalised,
            valid_format=valid,
            ocr_conf=round(voted_conf, 4),
            char_probs=best_hit.char_probs,
            det_conf=best_hit.det_conf,
            bbox=best_hit.bbox,
            crop=best_hit.crop,
        )
        self.tracks_finalized += 1
        self._persist(track.camera_id, best_frame, final, reads=len(track.reads))

    def _persist(self, camera_id: int, frame: np.ndarray, hit: anpr.PlateHit, reads: int = 1) -> None:
        now_mono = time.monotonic()
        key = (camera_id, hit.normalised)
        with self._lock:
            last = self._recent_detections.get(key)
            if last and now_mono - last < settings.detection_dedup_s:
                return  # same plate on same camera within window
            self._recent_detections[key] = now_mono

        # save plate crop as evidence
        rel_dir = f"detections/{camera_id}"
        out_dir = settings.data_dir / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        crop_rel = f"{rel_dir}/{stamp}_{hit.normalised}.jpg"
        cv2.imwrite(str(settings.data_dir / crop_rel), hit.crop)

        db = SessionLocal()
        try:
            det = Detection(
                camera_id=camera_id,
                object_class="vehicle",
                plate_text=hit.normalised,
                plate_conf=hit.ocr_conf,
                det_conf=hit.det_conf,
                bbox=",".join(map(str, hit.bbox)),
                snapshot_path=crop_rel,
                track_id=f"votes:{reads}",
            )
            db.add(det)
            db.commit()
            db.refresh(det)
            self.detections_saved += 1
            self._correlate(db, det, frame, hit)
        finally:
            db.close()

    def _correlate(self, db, det: Detection, frame: np.ndarray, hit: anpr.PlateHit) -> None:
        """Watchlist matching → alert + broadcast (the Watch integration).

        Exact match fires at the entry's priority; a fuzzy 'probable' match
        (confusion-folded or edit-distance 1) fires one severity lower —
        CCTV OCR misses single characters, and a stolen-vehicle hit is worth
        an operator's glance even at 90% read certainty.
        """
        entry, match_type = None, None
        for candidate in db.query(WatchlistVehicle).filter(WatchlistVehicle.active).all():
            sim = anpr.plate_similarity(hit.normalised, candidate.plate)
            if sim == "exact":
                entry, match_type = candidate, sim
                break
            if sim == "probable" and entry is None:
                entry, match_type = candidate, sim
        if entry is None:
            return
        key = (det.camera_id, entry.plate)
        now_mono = time.monotonic()
        with self._lock:
            last = self._recent_alerts.get(key)
            if last and now_mono - last < settings.alert_cooldown_s:
                return
            self._recent_alerts[key] = now_mono

        # annotated full frame as alert evidence
        x1, y1, x2, y2 = hit.bbox
        annotated = frame.copy()
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)
        cv2.putText(annotated, hit.normalised, (x1, max(30, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3)
        rel = f"alerts/{det.camera_id}"
        (settings.data_dir / rel).mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        frame_rel = f"{rel}/{stamp}_{hit.normalised}.jpg"
        cv2.imwrite(str(settings.data_dir / frame_rel), annotated)

        severity = {"high": "high", "medium": "medium"}.get(entry.priority, "low")
        if match_type == "probable" and severity == "high":
            severity = "medium"
        alert = Alert(detection_id=det.id, watchlist_id=entry.id, severity=severity)
        db.add(alert)
        db.commit()
        db.refresh(alert)
        self.alerts_fired += 1

        cam = db.get(Camera, det.camera_id)
        payload = {
            "type": "watchlist_alert",
            "alert_id": alert.id,
            "match_type": match_type,
            "watchlist_plate": entry.plate,
            "plate": hit.normalised,
            "reason": entry.reason,
            "priority": entry.priority,
            "fir_ref": entry.fir_ref,
            "camera_id": det.camera_id,
            "camera_name": cam.name if cam else "",
            "location": cam.location if cam else "",
            "lat": cam.lat if cam else None,
            "lon": cam.lon if cam else None,
            "ts": det.ts,
            "ocr_conf": hit.ocr_conf,
            "snapshot": f"/data/{det.snapshot_path}",
            "frame": f"/data/{frame_rel}",
        }
        broadcast_alert(payload)
        # tighten the net: alert camera + nearest neighbours become scheduler residents
        try:
            ingest_scheduler.boost(det.camera_id)
        except Exception:
            log.exception("scheduler boost failed")
        log.warning("WATCHLIST ALERT: %s (%s) on cam %s — %s",
                    hit.normalised, entry.reason, det.camera_id, cam.location if cam else "?")

    # ------------------------------------------------------------- stats

    def stats(self) -> dict:
        return {
            "running": self.running,
            "workers": len(self.workers),
            "queue_depth": self.queue.qsize(),
            "frames_in": self.frames_in,
            "frames_dropped": self.frames_dropped,
            "frames_processed": self.frames_processed,
            "plates_read": self.plates_read,
            "detections_saved": self.detections_saved,
            "tracks_finalized": self.tracks_finalized,
            "reads_rejected_invalid_format": self.reads_rejected,
            "alerts_fired": self.alerts_fired,
            "last_inference_ms": self.last_latency_ms,
        }


engine = InsightEngine()
