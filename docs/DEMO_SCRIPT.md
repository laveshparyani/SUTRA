# SUTRA — Demo Video Scripts (read-aloud)

Two videos are required. Everything in **quotes** is meant to be read aloud at
a normal speaking pace. Everything in *italics* is a screen action, not
narration.

Judges explicitly reject mock-ups, so let the running system carry the video.
Speak plainly, don't oversell, and never claim something the screen isn't
showing.

---

## Before you press record

**Setup (do this 10–15 minutes ahead):**

1. Both servers running — API on **8010**, UI on **5173**.
2. Signed in at http://localhost:5173 as `admin` / `SutraAdmin@26`.
3. Pin the plate-rich cameras so they hold their slots — in **Registry**, click
   the ★ on cameras **6, 7 and 12**. Give them ten minutes to accumulate reads.
4. Check `Detections` has fresh rows from today before you start.
5. Browser at **full screen**, 1080p. Close other tabs — the tab bar is visible
   in the recording.
6. Recorder: OBS Studio, or Windows Game Bar (**Win + Alt + R**).

**Practise the click path once without recording.** The narration is written to
match a specific order of pages.

**Two things to avoid saying:**
- Don't claim ANPR is perfectly accurate. It isn't, and the confidence column
  is the honest answer.
- Don't claim a vehicle was tracked across multiple cameras. No plate has yet
  appeared on two cameras in this dataset.

---

# VIDEO 1 — Own-Feed Demonstration

**Target: 2 min 30 s. Hard limit 3 min.**

---

### Shot 1 — Login  ·  0:00–0:15

*Start on the login page. Sign in as admin while speaking.*

> "This is SUTRA — Statewide Unified Tracking, Registry and Analytics, built
> for the Gujarat Police CCTV Integration Challenge.
>
> It's a hybrid of Model 1 and Model 3 — a mandatory camera registry with GIS,
> plus a federation layer that brings multiple vendors' feeds into one
> platform. Everything you're about to see is a running system."

---

### Shot 2 — Overview  ·  0:15–0:40

*Land on the Overview page. Let the KPI tiles and the Gujarat map render.
Move the cursor slowly across the map markers.*

> "The Atlas registry has onboarded cameras across five departments —
> government feeds from the challenge portal, recorded file sources, and an
> RTSP relay, all federated into a single platform.
>
> Each marker is a real camera with its department, location and live health.
> This map is the Model 1 foundation everything else keys off."

---

### Shot 3 — Registry and the scheduler  ·  0:40–1:05

*Go to Registry. Scroll so several cameras are visible. Hover over a ★ pin
button.*

> "Live connections are a budgeted resource. The challenge portal only serves a
> few concurrent streams per client, so an adaptive scheduler time-multiplexes
> the cameras — pinned cameras hold their slots, the rest rotate through on a
> dwell timer.
>
> Health is reported honestly per camera: connecting is not the same as live,
> and a camera that stopped sending frames says so."

---

### Shot 4 — Video Wall  ·  1:05–1:30

*Open Video Wall. Let the live tiles load. Point at the person/vehicle counts
on a tile, then at a tile in a non-live state.*

> "Live viewing of the federated feeds. Alongside number-plate recognition,
> every camera gets person and vehicle counts from an object-detection
> sidecar — all of this is CPU inference, there is no GPU anywhere in this
> demo.
>
> Notice the tiles that aren't streaming say why — queued, connecting, or
> unreachable. The system never shows a frozen frame and calls it live."

---

### Shot 5 — Watchlist  ·  1:30–1:45

*Open Watchlist. Show the stolen-vehicle entries with FIR references.*

> "A representative watchlist — stolen vehicles, each with an FIR reference and
> a priority. In production this maps one-to-one onto eGujCop records.
>
> Every plate the system reads is cross-referenced against this list
> continuously."

---

### Shot 6 — Alerts  ·  1:45–2:10

*Open Alerts. Click an evidence thumbnail to open the annotated frame. Close
it, then point at the VAHAN details panel.*

> "When a match fires, the operator gets the camera, the location, and the
> annotated evidence frame — and the record is enriched from a VAHAN-shaped
> connector: make, model, owner, insurance status.
>
> And where a match was fuzzy rather than exact, it's labelled a probable match
> and shows the characters the camera actually read. An operator is never
> handed an inference as a certainty."

---

### Shot 7 — Trace  ·  2:10–2:35

*Open Trace. Type a plate that has detections — check Detections first for a
good one. Let the timeline, map and VAHAN panel load.*

> "This is the evaluation scenario. Given a registration number, SUTRA
> reconstructs that vehicle's timestamped movement history across the
> integrated network and draws it on the GIS map.
>
> Where a vehicle has been seen at only one location, it says so plainly rather
> than leaving an unexplained dot — and a route line appears as soon as a
> second camera reads the same plate."

---

### Shot 8 — Output report  ·  2:35–2:50

*Go to Detections. Click the ⬇ Output Report button. Open the downloaded CSV.*

> "And every detection exports to a timestamped output report — camera,
> location, plate, confidence, UTC and IST timestamps, and the path to its
> evidence image.
>
> All open-source, all running on one machine."

---

# VIDEO 2 — Government-Feed Demonstration

**Target: 2 min 30 s.** This is the one the evaluation weighs most — it must
visibly be *their* cameras.

---

### Shot 1 — Onboarding the portal cameras  ·  0:00–0:30

*Start in Registry. Scroll to the `sentinel-*` cameras. Click ⟳ Discover and
let it complete.*

> "SUTRA onboards the government-provided cameras automatically from the
> challenge portal's own catalogue — thirty live feeds across five departments,
> a mix of H.264 and H.265, at different resolutions.
>
> They're pulled over authenticated RTSP, with credentials injected at
> connection time. The credentials are never written into the registry, never
> logged, and never stored with the camera record."

---

### Shot 2 — Live government feeds  ·  0:30–1:00

*Open Video Wall. Wait for a moment when several government tiles are
streaming. Point at two or three by name.*

> "Live viewing of the government feeds. These are the portal's cameras —
> Junagadh, Gir Somnath, Ahmedabad — decoding right now on this machine.
>
> We measured the portal before designing for it: it rations delivery to about
> five megabits per second per client, whether you open ten connections or
> twenty. That's three to four real-time streams. So the scheduler rotates all
> thirty cameras through the slots available, rather than opening thirty
> connections that would all starve."

---

### Shot 3 — ANPR on the government feed  ·  1:00–1:30

*Open Detections. Show today's reads from the government cameras. Point at the
camera column and the confidence column.*

> "Number-plate recognition running on the government feeds. These are today's
> reads from the Junagadh and Gir Somnath cameras — each one with the camera it
> came from, a timestamp, and the confidence of the read.
>
> That confidence column is deliberate. These are plates fifty to ninety pixels
> tall on a live street. Reads above about 0.95 are reliable; below that,
> characters can be wrong. Publishing the number without the confidence would
> invite you to treat every row as a fact."

---

### Shot 4 — Evidence  ·  1:30–1:50

*Click an evidence thumbnail from a high-confidence government read. Let the
lightbox open on the cropped plate.*

> "Every read is evidenced. This is the actual crop the recognition ran on, kept
> alongside the detection so any read can be checked by a human — which is the
> minimum bar for anything that might support an investigation."

---

### Shot 5 — Output report  ·  1:50–2:15

*Click ⬇ Output Report. Open the CSV and scroll it.*

> "And this is the required output report, straight from the government feeds:
> eighty-two plate reads over a two-hour run, fifty-one distinct registration
> numbers, each with UTC and IST timestamps and a path to its evidence image."

---

### Shot 6 — Atlas and audit  ·  2:15–2:40

*Open Atlas. Show the GIS coverage map with the layer filters, then scroll to
the district gap-analysis table and the audit trail.*

> "Completing the Model 1 foundation: a layered coverage map by department,
> camera type and status; district-level gap analysis showing thin coverage and
> ageing infrastructure; and a full metadata audit trail — every onboarding,
> export and watchlist change is recorded against a user.
>
> The hosted platform, the source code and this report are all linked in the
> submission."

---

## If something goes wrong mid-take

- **A government tile isn't streaming** — don't wait on camera. Say "these
  rotate under the concurrency budget" and move to a camera that is live.
- **No fresh detections today** — use Detections with a wider time window and
  say so; the timestamps are visible and honest.
- **The alert toast doesn't fire in Video 1** — skip it. The Alerts page
  already shows real alerts with evidence; you don't need a live one.
- **Anything looks stale** — hard-refresh (Ctrl+Shift+R) and re-take the shot.

## After recording

1. Export 1080p MP4.
2. Upload to YouTube as **Unlisted**, or Google Drive with *"Anyone with the
   link — Viewer"*.
3. **Open the link in a private window to confirm it plays** — a dead link is a
   failed deliverable.
4. Paste both links into the submission form alongside the deck, the HLD PDF,
   the output report, the repo URL, and the hosted URL with credentials.
