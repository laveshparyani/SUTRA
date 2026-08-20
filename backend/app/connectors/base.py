"""Government-database connector framework.

The production system must correlate detections with VAHAN, SARTHI, eGujCop,
AFIS and NAFIS. Those systems are not reachable from a sandbox, so each
integration is expressed as a connector implementing this interface; the
platform is written against the interface, and production integration is a
connector swap — not a redesign.

Contract every connector provides:
  name        — source system identifier ("vahan", "egujcop", ...)
  available() — reachability/health of the upstream system
  lookup(key) — query by the system's natural key (registration number,
                person id, FIR number...); returns a dict or None

The bundled `RepresentativeVahanConnector` serves the hackathon-permitted
representative dataset with the same response shape the real VAHAN
vehicle-details API exposes, so swapping in the NIC endpoint later changes
one class, zero callers.
"""

from abc import ABC, abstractmethod


class GovDBConnector(ABC):
    name: str = "abstract"

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def lookup(self, key: str) -> dict | None: ...
