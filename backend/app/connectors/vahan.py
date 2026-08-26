"""Representative VAHAN connector — vehicle-details lookup by registration number.

Response fields mirror the VAHAN vehicle-details API surface (make, model,
class, fuel, colour, registration date, RTO, owner name) so the production
swap is shape-compatible. Data source: data/vahan_representative.json —
a participant-created representative dataset, as the hackathon rules permit.
Owner names are masked the way VAHAN's public endpoint masks them.
"""

import json
import logging
from pathlib import Path

from ..config import settings
from .base import GovDBConnector

log = logging.getLogger("sutra.connectors.vahan")


class RepresentativeVahanConnector(GovDBConnector):
    name = "vahan"

    # Shipped with the code, not in the runtime data dir. The dataset used to
    # live only under data/, which is gitignored and therefore absent from every
    # deployed image: the hosted tier answered 404 for every lookup, so the
    # government-database correlation panel was empty on the judge-facing URL
    # while working locally. An operator-supplied file still wins, so a real
    # VAHAN extract can be dropped in without a code change.
    _PACKAGED = Path(__file__).resolve().parent / "data" / "vahan_representative.json"

    def __init__(self):
        override = settings.data_dir / "vahan_representative.json"
        self._path: Path = override if override.exists() else self._PACKAGED
        self._cache: dict | None = None

    def _load(self) -> dict:
        if self._cache is None:
            try:
                self._cache = json.loads(self._path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                log.warning("representative VAHAN dataset missing at %s", self._path)
                self._cache = {}
            except json.JSONDecodeError:
                log.warning("representative VAHAN dataset at %s is not valid JSON", self._path)
                self._cache = {}
        return self._cache

    def available(self) -> bool:
        return self._path.exists()

    def lookup(self, key: str) -> dict | None:
        rec = self._load().get(key.upper())
        if rec is None:
            return None
        return {"source": "VAHAN (representative)", "registration_no": key.upper(), **rec}


vahan = RepresentativeVahanConnector()
