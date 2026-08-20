"""Re-normalise stored detections after an ANPR correction-logic change.

Older rows were written before state-code validation existed, so they can hold
impossible registrations (GI01D7553) or partial reads (113117). Re-running the
current normaliser over them repairs what is repairable and drops the rest, so
the evidence log and vehicle traces agree with what the pipeline would produce
today.

Usage:  python scripts/repair_detections.py [--apply]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db import SessionLocal  # noqa: E402
from app.models import Alert, Detection  # noqa: E402
from app.services import anpr  # noqa: E402


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        repaired, dropped, untouched = [], [], 0
        for det in db.query(Detection).all():
            if not det.plate_text:
                continue
            fixed, valid = anpr.normalise_plate(det.plate_text)
            if not valid:
                dropped.append((det.id, det.plate_text))
            elif fixed != det.plate_text:
                repaired.append((det.id, det.plate_text, fixed))
                det.plate_text = fixed
            else:
                untouched += 1

        print(f"repair: {len(repaired)}   drop: {len(dropped)}   unchanged: {untouched}")
        for _, old, new in repaired[:5]:
            print(f"  {old} -> {new}")
        if dropped[:5]:
            print("  dropping invalid-format reads e.g. " + ", ".join(p for _, p in dropped[:5]))

        if not apply:
            print("\ndry run — pass --apply to write changes")
            return

        drop_ids = [d for d, _ in dropped]
        if drop_ids:
            # alerts reference detections; remove dependents first
            db.query(Alert).filter(Alert.detection_id.in_(drop_ids)).delete(synchronize_session=False)
            db.query(Detection).filter(Detection.id.in_(drop_ids)).delete(synchronize_session=False)
        db.commit()
        print(f"\napplied: {len(repaired)} repaired, {len(drop_ids)} removed")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
