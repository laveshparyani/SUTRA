# Submission artifacts — SUTRA

Gujarat Police CCTV Integration Hackathon 2026 · Category 1 · Lavesh Paryani and Hiral Kotwani
Repository: https://github.com/laveshparyani/SUTRA
Hosted platform: https://sutra-central.onrender.com

| File | What it is |
|---|---|
| `SUTRA_Solution_Presentation.pptx` | Solution presentation (deliverable 1) |
| `SUTRA_HLD.pdf` | High-Level Design / technical proposal (deliverable 2) |
| `SUTRA_own_feed_demo_captioned.mp4` | Demo video 1 — own feed, narrated, captions burned in (2:36) |
| `SUTRA_government_feed_demo_captioned.mp4` | Demo video 2 — the challenge portal's cameras, narrated (2:31) |
| `SUTRA_verification_walkthrough.mp4` | **Verification walkthrough** — every acceptance test in `docs/TESTING.md` run against the live system, annotated with its test reference and verdict (6:04) |
| `sutra_gov_feed_output_report_2026-09-26.csv` | **Government-feed output report** — 82 plate reads with timestamps |
| `evidence_2026-09-26/` | The 82 evidence crops the report references, one per row |
| `sutra_camera_registry.csv` | Registry export — all onboarded cameras and their metadata |
| `sutra_anpr_output_report_full.csv` | Earlier combined run (own feed + government feed) |
| `sutra_gov_feed_output_report_2026-09-24.csv` | Earlier government-feed run, first on the September portal |
| `evidence_cam7/`, `sutra_gov_feed_output_report_cam7.csv` | August run against a single camera |
| `*.srt`, `narration/` | Caption tracks and the narration audio, kept beside each video. The captions are already burned into the `_captioned` files; these are the sources, not a second thing to play. |

The `_captioned` videos are the ones to watch. The plain `SUTRA_own_feed_demo.mp4`
and `SUTRA_government_feed_demo.mp4` are the same takes before the subtitles were
burned in, kept only so the captions can be regenerated without re-recording.

---

## The government-feed output report

Produced by the platform's own `GET /api/insight/report` endpoint, filtered to
cameras served by the hackathon portal — no local demo footage is included.

| | |
|---|---|
| Run window | 2026-09-26 06:45:30 → 08:42:16 UTC (12:15 → 14:12 IST) |
| Cameras | `cam06` Timbavadi gate-Junagadh (78 reads), `cam07` hero-showroom-gir-somnath (4 reads) |
| Rows | 82 |
| Distinct registration numbers | 51 |
| Confidence | min 0.70 · mean 0.94 · max 1.00 |
| Evidence | every row links a cropped plate image; all 82 are present in `evidence_2026-09-26/` |

Columns: `sr_no, camera, location, district, plate_number, ocr_confidence,
reads_in_vote, timestamp_utc, timestamp_ist, evidence_snapshot`.

`reads_in_vote` is how many separate frames backed the read through temporal
voting. 62 of 82 rows rest on a single frame — at 1 fps sampling most vehicles
cross a camera's field of view in about a second, so the voting layer often has
only one look to work with.

## Read accuracy — measured, not asserted

Seven rows were checked by eye against their own evidence crops, chosen to
span the confidence range:

| Reported | Confidence | Plate in the image | |
|---|---|---|---|
| `GJ11G1388` | 1.00 | GJ11G1388 | correct |
| `GJ11CL3557` | 0.99 | GJ11CL3557 | correct |
| `GJ23H1546` | 0.96 | GJ23H1546 | correct |
| `GJ02CL1526` | 0.86 | GJ02CL**3**526 | one character wrong |
| `GJ11C0349` | 0.85 | GJ11C**D34 9 1** | characters dropped |
| `GJ10C6479` | 0.78 | GJ10C**G**479**6** | characters dropped |
| `GJ11C0349` | 0.70 | GJ11C**D**349**1** | characters dropped |

The separation is clean in this sample: every read at **0.96 and above was
correct**, every read at **0.86 and below had a character error**. This is a
seven-row spot check, not an exhaustive audit, so treat it as an indication of
where the threshold sits rather than a precision figure.

Distribution across the 82 rows: **47 at ≥0.95**, 19 between 0.90 and 0.95,
10 between 0.85 and 0.90, 6 below 0.85.

**Why the confidence column is in the report at all.** An ANPR system that
prints only plate numbers invites the reader to treat all of them as facts.
These are camera reads at 50–90 px plate height on a live street, and some are
wrong. The column is there so a reader can apply their own threshold, and the
same principle runs through the platform: a fuzzy watchlist match is labelled
*probable* and shows the raw characters the camera actually read, rather than
presenting an inference as an identification.

## Reproducing the report

With the edge node running and portal credentials in `backend/.env`:

```
GET /api/insight/report?since=2026-09-26T00:00:00Z&camera_id=<id>
```

Returns CSV directly. Omit `camera_id` for every camera; the government-only
report here is the per-camera output for the portal cameras, merged and
renumbered by timestamp.

## The verification walkthrough

`SUTRA_verification_walkthrough.mp4` is not a highlights reel. It runs all 31
acceptance tests from `docs/TESTING.md` in order against the running platform.
Each step names the requirement it proves, rings the element under test, and
states the result on screen as it happens.

It is produced by `scripts/record_walkthrough.py`, which drives the browser and
records from inside it, so what the video shows is what the test actually did.
A failing check is marked on screen as an issue and written to a defect report
beside the video rather than stopping the take. The take used here reports
**31 of 31 passed, 0 issues**, and its defect report is empty.

The run that preceded it did not: it found a crash in the detections view,
where switching back to the Vehicles tab rendered the new layout against the
previous tab's payload and took the whole page down. That is fixed, and the
walkthrough is the reason it was found — it drives the tabs the way an operator
would, which neither demo video did.

## A note on cross-camera tracking

No registration number has yet been read on two different cameras in any run.
The portal's 30 cameras are scattered across districts up to ~1,000 km apart
and each replays independent footage, so a single vehicle appearing on two of
them is not something the dataset offers. Vehicle Trace reconstructs and draws
a multi-camera route when the data contains one — and says plainly that a
vehicle was seen at one location only when it does not, rather than leaving an
unexplained single point on the map.
