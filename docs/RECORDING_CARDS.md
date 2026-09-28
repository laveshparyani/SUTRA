# Recording timing cards

You record the screen **silently**. I mux the narration on afterwards. These
cards say what to be doing, and for how long, so the picture lands with the
voice.

## The easy way — listen while you record

Don't watch a stopwatch. **Put the narration track on in headphones and click
along with it.**

1. Headphones in (so the recorder doesn't pick the audio up).
2. Open `v1_narration.mp3`, ready to press play.
3. Start the screen recorder.
4. Press play on the narration, and move to the next page as each new sentence
   block begins — the cards below tell you which page goes with which line.

Timing then takes care of itself, and the mux lines up because it's the same
track. The timings are only a fallback if you'd rather not listen.

**Recorder:** Windows Game Bar (**Win + Alt + R**) or OBS. Chrome **fullscreen
(F11)** — no tab bar, no address bar. Close anything you don't want on camera;
the whole screen is captured.

**Sign in before you start recording.** Both videos begin already logged in.

---

# VIDEO 1 — Own feed · total 2:55

| # | From → to | Hold | Be on | Do this |
|---|---|---|---|---|
| 1 | **0:00 → 0:24** | 25s | **Overview** | Sit still. Let the KPI tiles and the map render. Slowly move the cursor across the map once. |
| 2 | **0:24 → 0:42** | 18s | **Overview** | Hover two or three map markers so their popups show department and location. |
| 3 | **0:42 → 1:04** | 22s | **Registry** | Scroll slowly through the camera table. Pause on the health column. Hover a ★ pin button. |
| 4 | **1:04 → 1:30** | 26s | **Video Wall** | Let tiles load. Point at a live tile's person/vehicle counts, then at a tile that says Queued or Connecting. |
| 5 | **1:30 → 1:46** | 17s | **Watchlist** | Show the stolen-vehicle entries. Pause on an FIR reference. |
| 6 | **1:46 → 2:12** | 26s | **Alerts** | Click an evidence thumbnail → annotated frame opens → close it. Then scroll to the vehicle-details panel. |
| 7 | **2:12 → 2:39** | 27s | **Trace** | Type a plate from Detections, submit. Let the timeline, map and vehicle panel load. Don't rush this one. |
| 8 | **2:39 → 2:55** | 16s | **Detections** | Click **⬇ Output report**. Let the download appear. Stop recording at 2:55. |

**Cue lines** — the first words of each shot, so you know when to move:

1. *"This is SUTRA — Statewide Unified Tracking…"*
2. *"The Atlas registry has onboarded cameras across five departments…"*
3. *"Live connections are a budgeted resource…"*
4. *"Live viewing of the federated feeds…"*
5. *"A representative watchlist — stolen vehicles…"*
6. *"When a match fires, the operator gets the camera…"*
7. *"The evaluation scenario. Given a registration number…"*
8. *"And every detection exports to a timestamped output report…"*

---

# VIDEO 2 — Government feed · total 2:48

| # | From → to | Hold | Be on | Do this |
|---|---|---|---|---|
| 1 | **0:00 → 0:32** | 32s | **Registry** | Scroll to the `sentinel-*` cameras. Click **⟳ Discover** and let it finish. Then hover a camera row so the RTSP source URL is visible — **it has no password in it**, which the narration calls out. |
| 2 | **0:32 → 1:07** | 35s | **Video Wall** | Let government tiles stream. Move slowly across three or four live ones. Linger on Junagadh and Gir Somnath. |
| 3 | **1:07 → 1:45** | 38s | **Detections** | Longest shot. Scroll today's reads. Pause on the camera column, then on the **Confidence** column — the narration is explaining it. |
| 4 | **1:45 → 2:01** | 17s | **Detections** | Click a **high-confidence** evidence thumbnail. Let the cropped plate fill the lightbox. Close it. |
| 5 | **2:01 → 2:19** | 18s | **Detections** | Click **⬇ Output report**, open the CSV, scroll a few rows so timestamps and confidence are readable. |
| 6 | **2:19 → 2:48** | 29s | **Atlas** | Show the coverage map, change one layer filter, then scroll to district gap analysis and the audit trail. Stop at 2:48. |

**Cue lines:**

1. *"SUTRA onboards the Government provided cameras automatically…"*
2. *"Live viewing of the Government feeds…"*
3. *"Number plate recognition running on the Government feeds…"*
4. *"Every read is evidenced…"*
5. *"And this is the required output report…"*
6. *"Completing the Model One foundation…"*

---

## Before you press record

- [ ] Servers running; signed in as `admin` at http://localhost:5173
- [ ] Cameras **6, 7, 12** pinned and streaming *(done — they've been accumulating)*
- [ ] **Detections has fresh rows from today** — check first; shot 3 of video 2 depends on it
- [ ] Chrome **fullscreen (F11)**, other windows closed, notifications silenced
- [ ] Narration in headphones, recorder ready

## Record a little long

Start recording ~2 seconds before you press play on the narration, and keep
going ~2 seconds past the end. Trailing slack is trivial to trim; a clipped
first word is a re-record.

## When you're done

Send me the two MP4s. I will:

1. Trim each to the narration length
2. Mux `v1_narration.mp3` / `v2_narration.mp3` onto them
3. Encode to 1080p H.264 with AAC audio
4. Hand back `SUTRA_own_feed_demo.mp4` and `SUTRA_government_feed_demo.mp4`

If a take drifts out of sync, don't re-record the whole thing — tell me where
it slipped and I can nudge the audio offset during the mux.
