"""Retention housekeeping — the central tier's background task.

Evidence accumulates forever otherwise, and a managed free-tier database is
capped (1 GB on the hosted deployment). This trims the oldest evidence blobs
once the store exceeds its budget, and prunes detections past the retention
window, so the platform degrades gracefully instead of hitting a hard wall
mid-evaluation.

Detection *metadata* is small and is what vehicle traces are built from, so it
is kept far longer than the imagery.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from ..config import settings
from ..db import SessionLocal
from ..models import Alert, Detection, Evidence

log = logging.getLogger("sutra.retention")


class RetentionWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="retention")
        self.stop_flag = threading.Event()
        self.last_run: float | None = None
        self.last_result: dict = {}

    def run(self) -> None:
        log.info(
            "retention worker started (evidence budget %d MB, detections kept %d days)",
            settings.evidence_budget_mb, settings.detection_retention_days,
        )
        # first pass shortly after boot, then on the configured interval
        if self.stop_flag.wait(60):
            return
        while True:
            try:
                self.last_result = self.sweep()
                self.last_run = time.time()
            except Exception:
                log.exception("retention sweep failed")
            if self.stop_flag.wait(settings.retention_interval_s):
                return

    def sweep(self) -> dict:
        db = SessionLocal()
        removed_blobs = freed_bytes = removed_dets = 0
        try:
            # 1. evidence over budget: drop oldest first
            budget = settings.evidence_budget_mb * 1024 * 1024
            total = db.query(func.coalesce(func.sum(Evidence.size_bytes), 0)).scalar() or 0
            if total > budget:
                for row in db.query(Evidence).order_by(Evidence.created_at.asc()).yield_per(50):
                    db.delete(row)
                    removed_blobs += 1
                    freed_bytes += row.size_bytes or 0
                    if total - freed_bytes <= budget * 0.9:   # trim to 90% to avoid thrashing
                        break

            # 2. detections past the retention window, keeping anything an
            #    alert refers to (that is evidence in an active case)
            if settings.detection_retention_days > 0:
                cutoff = datetime.now(timezone.utc) - timedelta(days=settings.detection_retention_days)
                alerted = {a.detection_id for a in db.query(Alert.detection_id).all()}
                stale = db.query(Detection).filter(Detection.ts < cutoff).limit(5000).all()
                for det in stale:
                    if det.id in alerted:
                        continue
                    db.delete(det)
                    removed_dets += 1

            db.commit()
        finally:
            db.close()

        result = {
            "evidence_removed": removed_blobs,
            "mb_freed": round(freed_bytes / 1024 / 1024, 2),
            "detections_pruned": removed_dets,
        }
        if any(result.values()):
            log.info("retention sweep: %s", result)
        return result

    def status(self) -> dict:
        db = SessionLocal()
        try:
            total = db.query(func.coalesce(func.sum(Evidence.size_bytes), 0)).scalar() or 0
            count = db.query(func.count(Evidence.id)).scalar() or 0
        finally:
            db.close()
        return {
            "evidence_items": count,
            "evidence_mb": round(total / 1024 / 1024, 2),
            "budget_mb": settings.evidence_budget_mb,
            "detection_retention_days": settings.detection_retention_days,
            "last_run": self.last_run,
            "last_result": self.last_result,
        }


retention = RetentionWorker()
