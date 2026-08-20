# Setup Steps — Hosting & Auto-Deploy

Follow in order. Each step says what to do, and what I do afterwards.
Total hands-on time ≈ 45–60 minutes, most of it waiting on Oracle.

---

## Step 1 — Make the repository public (2 min)

Needed for free branch protection and unlimited CI minutes. Verified safe:
gitleaks scanned the full history and found no real secrets.

1. Open https://github.com/laveshparyani/SUTRA/settings
2. Scroll to the bottom → **Danger Zone** → **Change repository visibility**
3. Choose **Make public**, type `laveshparyani/SUTRA` to confirm

Or from the terminal:

```bash
gh repo edit laveshparyani/SUTRA --visibility public --accept-visibility-change-consequences
```

**Then tell me** — I enable branch protection on `main` via the API immediately.

---

## Step 2 — Create the Oracle Always Free server (20–30 min, mostly waiting)

Free forever: 4 ARM cores, 24 GB RAM. A card is required for identity
verification only; Always Free shapes are never charged. **Do not upgrade to
Pay As You Go.**

1. Sign up at https://signup.cloud.oracle.com — pick a home region near you
   (Mumbai or Hyderabad). The home region cannot be changed later.
2. In the console: **Compute → Instances → Create instance**
   - Name: `sutra-prod`
   - Image: **Ubuntu 22.04**
   - Shape: **Change shape → Ampere → VM.Standard.A1.Flex → 4 OCPU, 24 GB**
   - Networking: **Assign a public IPv4 address**
   - SSH keys: **Paste public keys** and paste the block below
   - Create
3. If you see *"Out of host capacity"*: retry in a few hours, or try another
   availability domain / region. This is common with Ampere shapes.

Your deploy public key (already generated on this machine):

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN+jhw948kPgV3DIvFdWMYjAUEDKNRyujAVi/kopeEE7 sutra-github-actions-deploy
```

4. Open the firewall: **Networking → Virtual Cloud Networks → your VCN →
   Security Lists → Default → Add Ingress Rules**
   - Source `0.0.0.0/0`, TCP, destination port **80**
   - Source `0.0.0.0/0`, TCP, destination port **443**

**Then give me the public IP** — I take it from there.

---

## Step 3 — Prepare the server (5 min, copy-paste)

SSH in from your machine (replace `<IP>`):

```bash
ssh -i C:\Users\Admin\.ssh\sutra_deploy ubuntu@<IP>
```

Then paste this whole block:

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker ubuntu
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
sudo mkdir -p /opt/sutra /opt/sutra-staging && sudo chown ubuntu:ubuntu /opt/sutra /opt/sutra-staging
git clone https://github.com/laveshparyani/SUTRA /opt/sutra
git clone https://github.com/laveshparyani/SUTRA /opt/sutra-staging
cd /opt/sutra && git checkout main
cd /opt/sutra-staging && git checkout dev
exit
```

(Oracle images block ports in `iptables` as well as the cloud firewall — that
is what the two `iptables` lines are for. Log out and back in for the docker
group to apply.)

---

## Step 4 — Write the environment files on the server (5 min)

Generate three strong passwords and a signing secret first:

```bash
ssh -i C:\Users\Admin\.ssh\sutra_deploy ubuntu@<IP>
openssl rand -base64 48   # JWT secret
openssl rand -base64 18   # admin password
openssl rand -base64 18   # operator password
openssl rand -base64 18   # viewer password
```

Create `/opt/sutra/.env.production` with `nano /opt/sutra/.env.production`:

```ini
SUTRA_JWT_SECRET=<the 48-char value>
SUTRA_SEED_ADMIN_PW=<admin password>
SUTRA_SEED_OPERATOR_PW=<operator password>
SUTRA_SEED_VIEWER_PW=<viewer password>
SUTRA_CORS_ORIGINS=["http://<IP>"]
SUTRA_INGEST_BUDGET=8
WEB_PORT=80
```

Repeat for `/opt/sutra-staging/.env.staging` with **different** passwords and
`WEB_PORT=8080`.

**Keep the three passwords somewhere safe** — the admin one goes to the judges.

---

## Step 5 — Add GitHub secrets and environments (5 min)

**Secrets** — https://github.com/laveshparyani/SUTRA/settings/secrets/actions →
*New repository secret*, three times:

| Name | Value |
|---|---|
| `DEPLOY_HOST` | the server's public IP |
| `DEPLOY_USER` | `ubuntu` |
| `DEPLOY_SSH_KEY` | the **entire contents** of `C:\Users\Admin\.ssh\sutra_deploy` (open it in Notepad, copy everything including the BEGIN/END lines) |

**Environments** — https://github.com/laveshparyani/SUTRA/settings/environments

Create **`staging`** → add variables:
- `STAGING_URL` = `http://<IP>:8080`
- `STAGING_PATH` = `/opt/sutra-staging`

Create **`production`** → tick **Required reviewers**, add yourself → Save
protection rules. Then add variables:
- `PRODUCTION_URL` = `http://<IP>`
- `PRODUCTION_PATH` = `/opt/sutra`

That reviewer tick is the approval gate you asked for: nothing reaches the live
URL without you clicking Approve.

---

## Step 6 — First deploy (I do this)

Tell me when steps 1–5 are done. I will:

1. Trigger the staging deploy and confirm it comes up healthy
2. Trigger production, you approve the gate, I verify the judge URL
3. Log in as each of the three roles and re-run the security checks against the
   live host
4. Hand you the URL and credentials for the submission form

---

## Daily workflow from then on

```bash
git checkout dev && git pull
git checkout -b feat/whatever          # your change
git add -A && git commit -m "..."
git push -u origin feat/whatever
gh pr create --base dev                # CI runs
gh pr merge --squash --delete-branch   # -> auto-deploys to staging
```

When staging looks right:

```bash
gh pr create --base main --head dev --title "Release: ..."
gh pr merge --squash                   # -> waits for your approval, then live
```

---

## Optional later: a real domain and HTTPS

The judge URL works over plain HTTP on the IP. If you want HTTPS (nicer for a
government submission), get any cheap domain, point an A record at the IP, and
I will switch the stack to Caddy — it obtains and renews Let's Encrypt
certificates automatically, one line of config. Tell me the domain and I will
do the rest, including flipping the session cookie to `Secure`.
