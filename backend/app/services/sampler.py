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

# RTSP must ride TCP: RTP-over-UDP is silently dropped by host firewalls,
# giving an open connection that never delivers a frame. Ignored by other
# protocols, so safe to set globally for the FFmpeg capture backend.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2  # noqa: E402

from ..config import settings
from ..db import SessionLocal
from ..models import Camera

log = logging.getLogger("sutra.sampler")

# camera_id -> (jpeg bytes, monotonic ts) — latest frame cache for the API layer
_latest: dict[int, tuple[bytes, float]] = {}
_latest_lock = threading.Lock()

# camera_id -> worker
_workers: dict[int, "CameraWorker"] = {}
_workers_lock = threading.Lock()

# Phase B hook: callables invoked as (camera_id, frame_bgr, ts) on each sampled frame
frame_subscribers: list[Callable] = []


def get_latest_frame(camera_id: int) -> tuple[bytes, float] | None:
    with _latest_lock:
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
        while not self.stop_flag.is_set():
            cap = cv2.VideoCapture(self.source_url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                self.last_error = "failed to open source"
                self._update_health("down", self.last_error)
                if self.stop_flag.wait(settings.reconnect_backoff_s):
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
            try:
                while not self.stop_flag.is_set():
                    ok, frame = cap.read()
                    if ok and warmup > 0:
                        warmup -= 1
                        continue
                    if not ok:
                        self.last_error = "stream read failed; reconnecting"
                        self._update_health("degraded", self.last_error)
                        break
                    now = time.monotonic()
                    if is_file:
                        frame_idx += 1
                        if frame_idx % keep_every:
                            continue
                    elif now - last_kept < settings.sample_interval_s:
                        continue
                    last_kept = now
                    self.frames_seen += 1
                    self.last_frame_at = datetime.now(timezone.utc)
                    if self.frames_seen == 1:
                        self._update_health("ok", "")  # first real picture

                    ok_jpg, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ok_jpg:
                        with _latest_lock:
                            _latest[self.camera_id] = (jpg.tobytes(), now)

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

            if not self.stop_flag.is_set():
                self.stop_flag.wait(settings.reconnect_backoff_s)

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
