# Government Database Connectors

SUTRA correlates CCTV analytics with government records through a connector
framework (`backend/app/connectors/`). The platform is written against the
`GovDBConnector` interface — production integration with each system is a
connector swap, not a redesign.

| System | Purpose in SUTRA | Natural key | Sandbox status |
|---|---|---|---|
| **VAHAN** | Vehicle details on ANPR hits (make/model/colour/owner/RTO/insurance) | registration number | ✅ representative connector shipped (`vahan.py`), wired into alerts + Trace |
| **SARTHI** | Driving-licence lookup on person-of-interest hits | licence number | interface-ready; connector on production access |
| **eGujCop (CCTNS)** | Watchlist sourcing: stolen vehicles, wanted/missing persons, FIR linkage | FIR / person id | interface-ready; watchlist import maps 1:1 to our `watchlist_vehicles` schema |
| **AFIS / NAFIS** | Fingerprint-verified identity confirmation for FRS candidates | person id | interface-ready; downstream of FRS (roadmap) |

## Interface contract

```python
class GovDBConnector(ABC):
    name: str
    def available(self) -> bool: ...     # upstream reachability/health
    def lookup(self, key: str) -> dict | None
```

## Data flow (VAHAN example)

ANPR read → watchlist match → alert created → `vahan.lookup(plate)` →
vehicle details embedded in the alert WebSocket payload and shown in the
Command UI (alert toast context + Trace page panel).

## Production integration prerequisites (per department)

- API endpoint + credentials (NIC/SCRB issued), IP allow-listing to SUTRA's gateway
- Response schema confirmation (our representative shapes mirror public VAHAN fields)
- Rate limits and caching policy (SUTRA caches lookups per plate with TTL)
- Audit requirements: every lookup is written to SUTRA's audit trail
