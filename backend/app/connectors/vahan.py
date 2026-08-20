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

    def __init__(self):
        self._path: Path = settings.data_dir / "vahan_representative.json"
        self._cache: dict | None = None

    def _load(self) -> dict:
        if self._cache is None:
            try:
                self._cache = json.loads(self._path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                log.warning("representative VAHAN dataset missing at %s", self._path)
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
