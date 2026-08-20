# SUTRA — Hosting & Deployment

## What SUTRA actually needs (measured, not guessed)

| Resource | Measured with 9 concurrent cameras | Why |
|---|---|---|
| RAM | **~2.1 GB** | one H.264 1080p decoder per camera (~200 MB each) + ONNX models |
| CPU | ~25% of an i7-14700K | 30–75 ms ANPR + 43 ms scene analysis per sampled frame |
| Network | 3–4 Mb/s inbound | camera streams; outbound is only metadata |
| Uptime | continuous | ingest holds long-lived connections; **the process must never sleep** |

**This rules out every free application-platform tier.** Render/Railway/Fly free
tiers cap at 256–512 MB and idle the process out — an ingest platform that
sleeps is not an ingest platform. SUTRA needs a real always-on machine.

## Recommended hosting

### Production: Oracle Cloud "Always Free" ARM VM — genuinely free, forever

4 ARM cores / 24 GB RAM / 200 GB storage, no time limit. That is more headroom
than the build machine used for development, and it costs nothing.

1. Create an Oracle Cloud account (card needed for identity verification; the
   Always Free shapes are never billed — do **not** upgrade to Pay As You Go).
2. Create a VM: shape `VM.Standard.A1.Flex`, 4 OCPU / 24 GB, Ubuntu 22.04.
   If the region reports "out of capacity", retry or pick another home region.
3. Open ports 80/443 in both the VCN security list *and* `ufw`.
4. `sudo apt install docker.io docker-compose-v2 git` and clone the repo.

*If Oracle signup stalls*, any ₹400–700/month VPS (Hetzner CX22, DigitalOcean,
Linode) with 4 GB RAM works identically — the deployment is plain Docker.

### Instant option, no signup: Cloudflare Tunnel from your own machine

Zero cost, works in ten minutes, and gives judges a real HTTPS URL. The
limitation is honest: the platform is up only while your machine is on.

```bash
winget install Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:5173
```

Good for a quick share; use the VM for the submitted judge URL so it stays up.

### Frontend

The React build is static, so `frontend/dist` can also go to **Cloudflare Pages**
(free, global CDN) with `VITE_API_BASE` pointed at the API host. The bundled
nginx service already serves it alongside the API, which keeps everything
same-origin — simpler, and it avoids CORS entirely. Prefer that unless you
specifically want CDN edge delivery.

## Branch model and pipeline

```
feat/xyz ──PR──▶ dev ──────────────▶ staging   (auto, after CI passes)
                  │
                  └──PR + review──▶ main ────▶ production (auto, after CI
                                                 passes AND human approval)
```

- **`feat/*` / `fix/*`** — short-lived. Open a PR into `dev`; CI runs tests,
  frontend build, dependency audit and secret scan. Delete the branch on merge.
- **`dev`** — integration branch. Every green push deploys to staging
  automatically (`deploy-staging.yml`).
- **`main`** — release branch. Merging requires a PR from `dev`; the production
  deploy then waits on the `production` GitHub Environment's required-reviewer
  gate, so nothing reaches the live judge URL without a deliberate click. A
  failed post-deploy smoke test rolls the previous image back automatically.

Useful commands:

```bash
git checkout dev && git pull                 # start from integration
git checkout -b feat/route-export            # do the work
gh pr create --base dev                      # CI runs on the PR
gh pr merge --squash --delete-branch         # tidy up after review
gh pr create --base main --head dev --title "Release: <summary>"
```

## One-time setup on GitHub

1. **Make the repository public** (Settings → General → Danger Zone). This is
   required for branch protection and unlimited Actions minutes on the Free
   plan, and the submission asks for a repo link anyway. Verified safe: no live
   secrets are in history — the old placeholder signing key is no longer used
   (secrets are now generated per install), and the seed passwords are
   sandbox-only and overridden by environment variables in any real deployment.

2. **Protect `main`** (Settings → Branches → Add rule, `main`):
   require a pull request, require status checks `Backend tests` /
   `Frontend build`, and dismiss stale approvals.

3. **Create Environments** (Settings → Environments):
   - `staging` — variables `STAGING_URL`, `STAGING_PATH`
   - `production` — variables `PRODUCTION_URL`, `PRODUCTION_PATH`, plus
     **Required reviewers = yourself**. This single setting is what makes
     production deploys manual-approval.

4. **Repository secrets** (Settings → Secrets and variables → Actions):
   `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` (a deploy-only key pair).

## Server-side setup (per environment)

```bash
sudo mkdir -p /opt/sutra /opt/sutra-staging
sudo git clone https://github.com/laveshparyani/SUTRA /opt/sutra
cd /opt/sutra && sudo git checkout main
```

Create `/opt/sutra/.env.production` (never committed):

```ini
SUTRA_JWT_SECRET=<openssl rand -base64 48>
SUTRA_SEED_ADMIN_PW=<strong password for judges>
SUTRA_SEED_OPERATOR_PW=<strong password>
SUTRA_SEED_VIEWER_PW=<strong password>
SUTRA_CORS_ORIGINS=["https://sutra.example.in"]
SUTRA_INGEST_BUDGET=8
WEB_PORT=8080
```

Staging is the same file with different passwords and `SUTRA_TAG=staging`.

Then put Caddy or nginx in front for TLS (Caddy is one line and auto-renews
Let's Encrypt certificates), and set the media cookie to `Secure` in
`backend/app/routers/auth.py` once HTTPS is live.

## Deployment checklist before sharing the judge URL

- [ ] `.env.production` has non-default passwords and a fresh JWT secret
- [ ] HTTPS working; cookie marked `Secure`
- [ ] `SUTRA_CORS_ORIGINS` set to the real origin
- [ ] `docker compose ps` shows both services healthy
- [ ] `/api/health` returns ok through the public URL
- [ ] Log in as each role and confirm the viewer cannot mutate anything
- [ ] Server firewall exposes only 80/443
