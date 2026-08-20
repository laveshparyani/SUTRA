# SUTRA — Security Posture & Pre-Submission Audit

Audited 20 August 2026 against the platform as built. Every finding below was
fixed and is pinned by an automated test (`backend/tests/`, 19 tests).
Run them with: `cd backend && ../.venv/Scripts/python -m pytest tests -q`

## Threat model

SUTRA handles vehicle sightings, watchlist records tied to FIRs, camera
locations, and live imagery of public spaces. The assets an attacker wants are
(a) surveillance imagery, (b) the watchlist (which reveals active
investigations), (c) movement histories of individuals, and (d) the ingest
engine itself as a pivot into departmental networks. The controls below are
organised around denying each of those.

## Findings from the audit, and their fixes

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | JWT signing secret was a constant in the repository — anyone with the source could forge an admin token for any deployment | **Critical** | Secret is generated per install and stored outside version control (`data/.jwt_secret`), overridable by `SUTRA_JWT_SECRET`. No default exists in code. |
| 2 | `/data/**` (all detection crops and annotated alert frames) was served by an unauthenticated static mount | **Critical** | Replaced with an authenticated route that resolves the path, confines it to the data directory, and serves only image types. |
| 3 | Camera snapshot and MJPEG endpoints were unauthenticated — live imagery from every camera was readable by anyone who could reach the port | **High** | Both now require the media credential. |
| 4 | The alert WebSocket accepted any connection, streaming plates, locations and FIR references to unauthenticated listeners | **High** | Handshake is authenticated; unauthorised sockets are closed with 4401. |
| 5 | No login rate limiting — offline-speed brute force against the login endpoint | **High** | Five failures per five minutes per client address → HTTP 429. Every failure is written to the audit trail with its source address. |
| 6 | Camera names and locations (which arrive from CSV import and an external portal) were interpolated into Leaflet popup HTML — stored XSS | **High** | All popup interpolation is HTML-escaped. |
| 7 | `source_url` accepted any string, so an operator-level account could point the ingest engine at internal services (SSRF) or at arbitrary server files | **Medium** | Network sources restricted to `rtsp/http/https`; file sources confined to the media directory. Enforced on create, update and bulk import. |
| 8 | CORS allowed every origin with credentials | **Medium** | Restricted to configured origins. |
| 9 | Ingest status and scheduler endpoints were unauthenticated (camera inventory and topology recon) | **Low** | Authenticated. |
| 10 | Seed passwords are documented in the repository for judges | **Note** | Overridable via `SUTRA_SEED_ADMIN_PW` / `_OPERATOR_PW` / `_VIEWER_PW`; the server logs a warning when defaults are in use. **Any publicly hosted instance must set these.** |

### How media authentication works, and why

Browsers cannot attach an `Authorization` header to `<img>` tags or WebSocket
handshakes, which is exactly why those endpoints were left open in the first
place. The fix issues a second, media-scoped token at login as an **HttpOnly,
SameSite=Lax cookie**: the browser sends it automatically on same-origin image
and socket requests, while page scripts cannot read it — so even a successful
XSS cannot exfiltrate the credential. API calls continue to use the bearer
token; both are accepted on media routes.

## Controls in place

**Authentication & authorisation.** PBKDF2-SHA256 password hashing (200,000
iterations, per-user salt). Signed JWTs with expiry. Three roles: `admin`
(full control), `operator` (department-scoped — server-side filtering, not a
UI hint), `viewer` (read-only). Role checks are enforced as endpoint
dependencies, so a hidden UI button cannot be bypassed by calling the API.

**Injection resistance.** All database access goes through SQLAlchemy ORM
parameterisation — no string-built SQL anywhere. React escapes rendered values
by default; the one place raw HTML is produced (map popups) is explicitly
escaped. Uploaded CSVs are parsed as data, never evaluated.

**Path safety.** Evidence paths are resolved and checked for containment
before serving, which defeats URL-encoded traversal (`%2e%2e`, `..%2f`) as well
as plain `../`; extension is allowlisted to images.

**Auditability.** Logins (success and failure), camera onboarding and edits,
discovery runs, bulk imports, registry exports, watchlist additions and
deactivations, and alert acknowledgements are all written to an audit trail
with actor and timestamp, viewable in the Atlas page.

**Privacy.** No continuous central video recording — only detections, evidence
thumbnails and metadata leave the edge. Alerts fire only on watchlist matches.
Owner names from the vehicle-details connector are masked. Face recognition is
deliberately *not* implemented as automatic identification; the roadmap places
a human confirmation step before any identity assertion.

## Deployment hardening checklist (before any public host)

1. Set `SUTRA_JWT_SECRET` (or let the per-install file generate one) and
   **`SUTRA_SEED_*_PW`** — never expose the documented demo passwords.
2. Terminate TLS in front of the app; set cookies `Secure` (one flag, in
   `auth.py`) once HTTPS is in place.
3. Set `SUTRA_CORS_ORIGINS` to the real front-end origin only.
4. Put the API behind a reverse proxy with request limits; keep the database
   and evidence store on non-public interfaces.
5. Migrate SQLite → PostgreSQL/PostGIS with least-privilege database
   credentials (the ORM layer is unchanged by this).
6. Ship audit and application logs to a SIEM; alert on repeated 401/429.
7. Rotate credentials on a schedule; disable rather than delete accounts so the
   audit trail stays referentially intact.

## Known limitations (stated honestly)

- The audit trail is append-only by convention, not cryptographically chained;
  hash chaining is on the roadmap for tamper evidence.
- Rate limiting is per-process and in-memory; a multi-replica deployment should
  move it to Redis or the API gateway.
- The bundled government-database connector serves a representative dataset, by
  design — production credentials were never in scope for a sandbox.
