# Security Policy

SUTRA processes live CCTV feeds, government watchlist records and vehicle
registration data. A vulnerability here is not an inconvenience — it is a
privacy incident affecting people who never opted in. Please treat findings
accordingly.

## Reporting a vulnerability

**Do not open a public issue.** Report privately:

- GitHub → **Security** tab → **Report a vulnerability** (private advisory), or
- email **laveshparyani01@gmail.com** with `SUTRA SECURITY` in the subject.

Please include the affected endpoint or component, the version or commit,
reproduction steps, and what an attacker gains. A proof of concept helps but
is not required.

You can expect an acknowledgement within **72 hours** and an assessment within
**7 days**. I will tell you plainly whether the report is accepted, and credit
you in the fix unless you prefer otherwise.

## Scope

In scope: authentication and session handling, role-based access control,
media and evidence endpoints, the edge↔central sync channel, input validation
on camera onboarding, the alert WebSocket, and anything that discloses plate
reads, watchlist contents or camera locations to an unauthorised party.

Out of scope: the hackathon feed portal itself (`cctv.corp8.cloud`, operated by
the organisers), denial of service by traffic volume, and findings that
require an already-compromised operator workstation.

## What is already implemented

The threat model and controls are documented in [docs/SECURITY.md](../docs/SECURITY.md).
In summary: JWT with PBKDF2 (200k iterations) and a per-install generated
signing secret, login rate limiting with audited failures, RBAC across
admin / department-scoped operator / viewer enforced server-side, HttpOnly
SameSite cookie authentication on every media endpoint and the alert socket,
evidence serving confined to its directory with an image-type allowlist,
camera source URLs restricted to camera protocols (no SSRF, no arbitrary file
reads), HTML escaping on all user-visible strings including map popups, and an
audit trail covering logins, onboarding, exports and watchlist changes.

Ten findings from a pre-submission audit are closed and each is pinned by an
automated test, so a regression fails CI rather than reaching a deployment.

## Known limitations

This is a hackathon sandbox deployment, not a hardened production
installation. Before real deployment the following are required and
documented but not implemented here: TLS termination and mTLS on federation
links, a secrets vault, network segmentation across ingest / analytics / data
planes, SIEM export, and a hash-chained audit log.

The hosted instance uses seeded demonstration accounts and a representative
watchlist. It contains no real case data.
