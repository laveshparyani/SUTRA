"""Backfill Alert.match_type for alerts raised before the column existed.

The additive migration gives every existing row the column default ('exact'),
but some of those alerts were fuzzy matches — the camera read a plate one
OCR-confusable character away from the watchlist entry. Leaving them labelled
'exact' would assert a certainty the pipeline never had, which is precisely the
claim an operator must not be handed. This recomputes the label from the stored
detection text using the same comparison the live matcher uses.

    python scripts/backfill_match_type.py [--apply]

Without --apply it reports what would change and writes nothing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import SessionLocal  # noqa: E402
from app.models import Alert, Detection, WatchlistVehicle  # noqa: E402
from app.services import anpr  # noqa: E402


def main() -> int:
    apply = "--apply" in sys.argv
    db = SessionLocal()
    try:
        dets = {d.id: d for d in db.query(Detection).all()}
        entries = {w.id: w for w in db.query(WatchlistVehicle).all()}
        changed, unresolved = [], 0

        for a in db.query(Alert).all():
            det, entry = dets.get(a.detection_id), entries.get(a.watchlist_id)
            if det is None or entry is None or not det.plate_text:
                unresolved += 1
                continue
            # None means the read no longer resembles the entry at all (the
            # watchlist plate was edited after the alert fired); 'probable' is
            # the honest label there — it matched once, but not character-exact.
            actual = anpr.plate_similarity(det.plate_text, entry.plate) or "probable"
            if actual != a.match_type:
                changed.append((a.id, det.plate_text, entry.plate, a.match_type, actual))
                a.match_type = actual

        for aid, read, target, was, now in changed:
            print(f"  alert {aid:>5}: read {read} vs watchlist {target} — {was} -> {now}")
        print(f"\n{len(changed)} alert(s) relabelled, {unresolved} unresolvable")

        if apply and changed:
            db.commit()
            print("committed")
        elif changed:
            print("dry run — pass --apply to write")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
