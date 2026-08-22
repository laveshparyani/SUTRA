"""Bridge frame sampler: one ingest worker per monitored camera.

Each worker opens the camera's source with OpenCV (FFmpeg backend — handles
progressive HTTP, HLS, RTSP and files uniformly), keeps the latest frame in
memory for snapshot/MJPEG endpoints, persists a JPEG every `snapshot_every_s`,
and maintains health state in the registry. Insight (Phase B) consumes frames
via `get_latest_frame` / an on-frame callback, so analytics stays decoupled
from ingestion.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# FFmpeg capture tuning, applied before cv2 imports its backend:
#   rtsp_transport=tcp — RTP-over-UDP is silently dropped by host firewalls,
#     giving an open connection that never delivers a frame.
#   timeout/stimeout (µs) — OpenCV serialises VideoCapture opens behind one
#     global lock, so a dead source blocking on the 30s default starves every
#     other camera's (re)open. Short timeouts keep that lock moving.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|timeout;8000000|stimeout;8000000",
)

import cv2  # noqa: E402

from ..config import settings
from ..db import SessionLocal
from ..models import Camera

log = logging.getLogger("sutra.sampler")

# camera_id -> (jpeg bytes, monotonic ts) — latest frame cache for the API layer
_latest: dict[int, tuple[bytes, float]] = {}
# a wall tile is ~330px wide, so a downscaled copy is encoded once per sampled
# frame and shared by every viewer: a full 1080p MJPEG grid saturates both the
# browser's decode budget and the uplink for no visible gain.
_latest_small: dict[int, tuple[bytes, float]] = {}
_latest_lock = threading.Lock()
PREVIEW_WIDTH = 480

# camera_id -> worker
_workers: dict[int, "CameraWorker"] = {}
_workers_lock = threading.Lock()

# Phase B hook: callables invoked as (camera_id, frame_bgr, ts) on each sampled frame
frame_subscribers: list[Callable] = []


def get_latest_frame(camera_id: int, preview: bool = False) -> tuple[bytes, float] | None:
    """Latest JPEG for a camera. `preview` returns the downscaled wall copy."""
    with _latest_lock:
        if preview:
            return _latest_small.get(camera_id) or _latest.get(camera_id)
        return _latest.get(camera_id)


class CameraWorker(threading.Thread):
    def __init__(self, camera_id: int, source_url: str, source_type: str = "http-progressive"):
        super().__init__(daemon=True, name=f"ingest-cam{camera_id}")
        self.camera_id = camera_id
        self.source_url = source_url
        self.source_type = source_type
        self.stop_flag = threading.Event()
        self.frames_seen = 0
        self.started_at = time.monotonic()
        self.last_frame_at: datetime | None = None
        self.last_error = ""

    def run(self) -> None:
        log.info("cam %s: ingest starting (%s)", self.camera_id, self.source_url)
        # OpenCV serialises VideoCapture opens behind a global FFmpeg lock; a
        # dead network source holding it for its 30s timeout starves every
        # other camera's (re)open. Failing sources must back off exponentially.
        consecutive_failures = 0
        while not self.stop_flag.is_set():
            cap = cv2.VideoCapture(self.source_url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                consecutive_failures += 1
                backoff = min(settings.reconnect_backoff_s * (2 ** consecutive_failures), 300.0)
                self.last_error = f"failed to open source (retry in {backoff:.0f}s)"
                self._update_health("down", self.last_error)
                if self.stop_flag.wait(backoff):
                    break
                continue

            self._update_health("ok", "")
            last_kept = 0.0
            last_saved = 0.0
            last_db = 0.0
            # files decode faster than real time → sample by video-frame index;
            # live streams are paced by the source → sample by wall clock
            is_file = self.source_type == "file"
            native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            keep_every = max(1, round(native_fps * settings.file_sample_interval_s))
            frame_idx = 0
            warmup = 0 if is_file else 10  # live mid-GOP joins decode corrupt (HEVC especially)
            frames_at_open = self.frames_seen
            try:
                while not self.stop_flag.is_set():
                    ok, frame = cap.read()
                    if ok and warmup > 0:
                        warmup -= 1
                        continue
                    if not ok:
                        # a file source has simply reached its end: rewind in
                        # place rather than reopening, which would queue behind
                        # OpenCV's global open lock
                        if is_file and cap.set(cv2.CAP_PROP_POS_FRAMES, 0):
                            frame_idx = 0
                            continue
                        self.last_error = "stream read failed; reconnecting"
                        self._update_health("degraded", self.last_error)
                        break
                    now = time.monotonic()
                    if is_file:
                        # advance video time by the sample step...
                        frame_idx += 1
                        if frame_idx % keep_every:
                            continue
                        # ...but never faster than real time. A file decodes far
                        # quicker than it plays, and an unpaced recorded camera
                        # pegs a core and floods the analytics queue, starving
                        # both the live cameras and the operator's browser.
                        wait = settings.file_sample_interval_s - (now - last_kept)
                        if last_kept and wait > 0:
                            if self.stop_flag.wait(wait):
                                break
                            now = time.monotonic()
                    elif now - last_kept < settings.sample_interval_s:
                        continue
                    last_kept = now
                    self.frames_seen += 1
                    self.last_frame_at = datetime.now(timezone.utc)
                    if self.frames_seen == 1:
                        self._update_health("ok", "")  # first real picture

                    ok_jpg, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ok_jpg:
                        small = None
                        if frame.shape[1] > PREVIEW_WIDTH:
                            scale = PREVIEW_WIDTH / frame.shape[1]
                            thumb = cv2.resize(frame, None, fx=scale, fy=scale,
                                               interpolation=cv2.INTER_AREA)
                            ok_s, enc = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 62])
                            small = enc.tobytes() if ok_s else None
                        with _latest_lock:
                            _latest[self.camera_id] = (jpg.tobytes(), now)
                            if small:
                                _latest_small[self.camera_id] = (small, now)

                    if now - last_saved >= settings.snapshot_every_s and ok_jpg:
                        last_saved = now
                        self._save_snapshot(jpg.tobytes())

                    for cb in frame_subscribers:
                        try:
                            cb(self.camera_id, frame, now)
                        except Exception:
                            log.exception("frame subscriber failed for cam %s", self.camera_id)

                    if now - last_db >= 15:
                        last_db = now
                        self._update_health("ok", "")
            finally:
                cap.release()

            # a session that delivered frames resets the backoff; one that
            # opened but produced nothing counts as a failure
            if self.frames_seen > frames_at_open:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
            if not self.stop_flag.is_set():
                backoff = min(settings.reconnect_backoff_s * (2 ** consecutive_failures), 300.0)
                self.stop_flag.wait(backoff if consecutive_failures else settings.reconnect_backoff_s)

        self._update_health("unknown", "monitoring stopped")
        log.info("cam %s: ingest stopped", self.camera_id)

    def _save_snapshot(self, jpg: bytes) -> None:
        out_dir: Path = settings.frames_dir / str(self.camera_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (out_dir / f"{stamp}.jpg").write_bytes(jpg)

    def _update_health(self, health: str, detail: str) -> None:
        """Persist health. `last_frame_at` advances only when frames really
        arrive — an open socket that never delivers a picture is not health."""
        elapsed = max(time.monotonic() - self.started_at, 1e-6)
        # a connection that has produced no frame yet is 'connecting', not 'ok'
        if health == "ok" and self.frames_seen == 0:
            health, detail = "connecting", detail or "awaiting first frame"
        db = SessionLocal()
        try:
            cam = db.get(Camera, self.camera_id)
            if cam:
                cam.health = health
                cam.health_detail = detail
                if self.frames_seen:
                    cam.last_frame_at = self.last_frame_at
                cam.ingest_fps = round(self.frames_seen / elapsed, 3)
                db.commit()
        finally:
            db.close()


def start_worker(camera_id: int, source_url: str, source_type: str = "http-progressive") -> bool:
    with _workers_lock:
        if camera_id in _workers and _workers[camera_id].is_alive():
            return False
        if len([w for w in _workers.values() if w.is_alive()]) >= settings.max_concurrent_cameras:
            raise RuntimeError(f"max concurrent cameras ({settings.max_concurrent_cameras}) reached")
        worker = CameraWorker(camera_id, source_url, source_type)
        _workers[camera_id] = worker
        worker.start()
        return True


def stop_worker(camera_id: int) -> bool:
    with _workers_lock:
        worker = _workers.pop(camera_id, None)
    if worker and worker.is_alive():
        worker.stop_flag.set()
        return True
    return False


def worker_status() -> list[dict]:
    with _workers_lock:
        items = list(_workers.items())
    out = []
    for cam_id, w in items:
        latest = get_latest_frame(cam_id)
        out.append(
            {
                "camera_id": cam_id,
                "alive": w.is_alive(),
                "frames_seen": w.frames_seen,
                "last_error": w.last_error,
                "has_frame": latest is not None,
                "frame_age_s": round(time.monotonic() - latest[1], 1) if latest else None,
            }
        )
    return out


def running_ids() -> set[int]:
    with _workers_lock:
        return {cam_id for cam_id, w in _workers.items() if w.is_alive() and not w.stop_flag.is_set()}


def stop_all() -> None:
    with _workers_lock:
        workers = list(_workers.values())
        _workers.clear()
    for w in workers:
        w.stop_flag.set()
