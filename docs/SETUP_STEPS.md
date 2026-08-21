# Setup Steps — Always-On Hosting (no credit card)

The judge URL runs on **Render's free tier**: no card, 750 instance-hours a
month (enough for 24/7), HTTPS, WebSockets. Your PC does not need to be on.

## Why this works when "SUTRA needs 2 GB" was the blocker

Nine live 1080p decoders need ~2.1 GB — far past any free tier. So the
deployment is split along the same boundary the HLD proposes for the statewide
rollout: **video stays at the edge, metadata flows up.**

| Tier | Runs | Measured RAM | Where |
|---|---|---|---|
| **central** | command centre, registry, watchlist, trace, alerts, evidence, reports | **102 MB** | Render free |
| **edge** | stream ingest, ANPR, scene analytics | 514 MB (9 cameras) | your PC, when you want live ingest |

The central tier is always up and always shows real accumulated data. When you
run the edge node, fresh detections and alerts flow up within 30 seconds. The
hosted URL is a working instance of the architecture you proposed — not a
compromise.

---

## Step 1 — Deploy the central tier (10 min)

1. Sign up at https://render.com with your **GitHub account** (no card).
2. **New → Blueprint** → select `laveshparyani/SUTRA` → Render reads
   `render.yaml` and proposes `sutra-central` plus a free Postgres database.
3. It will prompt for the three values marked `sync: false`. Set strong ones:

   | Variable | Value |
   |---|---|
   | `SUTRA_SEED_ADMIN_PW` | strong password — **this goes to the judges** |
   | `SUTRA_SEED_OPERATOR_PW` | strong password |
   | `SUTRA_SEED_VIEWER_PW` | strong password |

4. **Apply**. First build takes ~5 minutes (installs deps, builds the UI).
5. Note your URL: `https://sutra-central.onrender.com`.
6. In the service's **Environment** tab, copy the generated
   **`SUTRA_SYNC_API_KEY`** — the edge node needs it in step 2.

If the URL differs from `sutra-central.onrender.com`, update
`SUTRA_CORS_ORIGINS` in the Environment tab to match, then redeploy.

**Then tell me the URL** and I will verify health, roles, and the security
checks against the live host.

## Step 2 — Point your PC at it as an edge node (2 min)

Create `C:\Users\Admin\Desktop\SUTRA\backend\.env`:

```ini
SUTRA_ROLE=edge
SUTRA_CENTRAL_URL=https://sutra-central.onrender.com
SUTRA_SYNC_API_KEY=<the generated key from step 1>
```

Restart the backend. It keeps ingesting exactly as now, and every 30 seconds
pushes new cameras, detections, alerts and evidence thumbnails upstream. If the
centre is unreachable the edge keeps working and retries — nothing is lost.

## Step 3 — Keep it warm (2 min, optional but recommended)

Render free services sleep after 15 minutes idle and take ~1 minute to wake.
For a judge clicking your link, that is a bad first impression. Fix it free:

1. https://cron-job.org → sign up (no card)
2. Create a job: URL `https://sutra-central.onrender.com/api/health`,
   every 10 minutes

750 free hours covers 24/7 for one service, so this stays inside the free tier.

## Step 4 — Enable auto-deploy (already wired)

Render redeploys `main` automatically on every push. Combined with the branch
protection now enforced on `main`, the flow you asked for is complete:

```
feat/xyz ──PR──▶ dev ────────────▶ (CI green)
                  │
                  └─PR + review──▶ main ──▶ Render auto-deploys the judge URL
```

The GitHub Actions deploy workflows stay dormant (they skip unless
`DEPLOY_CONFIGURED=true`); they are there for a VPS deployment later, and do
not interfere with Render.

---

## Optional: a nicer URL

`sutra-central.onrender.com` is fine for submission. If you want
`sutra.yourdomain.in`, buy any cheap domain, add it under Render → Settings →
Custom Domains, and point the CNAME. Render issues the TLS certificate free.

## Fallback if Render disappoints

Everything is containerised (`Dockerfile`, `docker-compose.yml`), so moving to
a VPS is a copy-paste. Indian providers accept UPI/netbanking without a credit
card — Utho (~₹350/month) or E2E Networks (~₹700/month) — and the GitHub
Actions pipeline is already written for that path: add `DEPLOY_HOST`,
`DEPLOY_USER`, `DEPLOY_SSH_KEY` and set `DEPLOY_CONFIGURED=true`.

Your deploy public key, if you go that route:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN+jhw948kPgV3DIvFdWMYjAUEDKNRyujAVi/kopeEE7 sutra-github-actions-deploy
```

## What to put in the submission form

- **Platform URL:** `https://sutra-central.onrender.com`
- **Credentials:** `admin` / *(your step-1 password)*, plus `viewer` for a
  read-only account
- **Repository:** https://github.com/laveshparyani/SUTRA
- **Note for judges:** the hosted instance is the central tier; live camera
  ingest runs on an edge node, matching the deployment model in the HLD.

---

## Running the edge node in the background (done)

The edge node — ingest, ANPR, scene analytics and the upstream sync — now runs
without a terminal window.

- `infra/run_edge.ps1` — supervises the backend, restarts it if it exits, and
  rotates its log at 20 MB (`data/logs/edge.log`).
- `infra/install_edge_startup.ps1` — installs a hidden Startup-folder entry
  (**no administrator rights needed**). Already installed on this machine.
- `infra/install_edge_task.ps1` — the Task Scheduler equivalent, if you would
  rather run it as a scheduled task. Needs an **elevated** PowerShell:
  right-click PowerShell -> Run as administrator, then
  `powershell -ExecutionPolicy Bypass -File infra\install_edge_task.ps1`

Start it now without logging out:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\Admin\Desktop\SUTRA\infra\run_edge.ps1"
```

Check what the background tasks are doing (any node, authenticated):

```
GET /api/system      # scheduler, analytics, edge sync, retention
```
