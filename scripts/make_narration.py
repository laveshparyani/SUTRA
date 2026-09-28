"""Generate the demo-video narration track, one audio file per shot.

Neural TTS via edge-tts (free, no API key). Each shot becomes its own file so
the screen-driving script can hold a page on screen for exactly as long as its
narration runs — that is what keeps picture and voice in step without an
editor.

    python scripts/make_narration.py <outdir>

Writes shot_01.mp3 … and timeline.json (per-shot durations, cumulative start
times), then a single concatenated track per video for muxing.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import edge_tts

VOICE = "en-US-BrianMultilingualNeural"   # newer conversational model — the older
                                          # en-IN neural voice read flat by comparison
RATE = "-8%"                    # Brian reads briskly; slowed so each shot has room to
                                # breathe. Still lands ~2:35, inside the 3:00 limit.

# Each entry: (video, shot id, narration). Text is written for the ear, not the
# eye — short clauses, no parentheses, numbers spelled where they would trip a
# synthesiser. Pauses come from sentence breaks, not markup.
SHOTS: list[tuple[str, str, str]] = [
    # ---------------------------------------------------------- video 1
    ("v1", "01_intro",
     "This is SUTRA — Statewide Unified Tracking, Registry and Analytics, "
     "built for the Gujarat Police CCTV Integration Challenge. "
     "It is a hybrid of Model One and Model Three: a camera registry with G I S, "
     "plus a federation layer bringing multiple vendors' feeds into one platform. "
     "Everything here is a running system."),

    ("v1", "02_overview",
     "The Atlas registry has onboarded cameras across five departments — "
     "Government feeds from the challenge portal, recorded file sources, and an "
     "R T S P relay. Each marker is a real camera with its department, location "
     "and live health."),

    ("v1", "03_registry",
     "Live connections are a budgeted resource. The portal serves only a few "
     "concurrent streams per client, so an adaptive scheduler time-multiplexes "
     "the cameras: pinned cameras hold their slots, the rest rotate on a dwell "
     "timer. Health is reported honestly — connecting is not the same as live."),

    ("v1", "04_wall",
     "Live viewing of the federated feeds. Alongside number plate recognition, "
     "every camera gets person and vehicle counts from an object detection "
     "sidecar — all C P U inference, no G P U anywhere. "
     "Tiles that are not streaming say why: queued, connecting, or unreachable. "
     "The system never shows a frozen frame and calls it live."),

    ("v1", "05_watchlist",
     "A representative watchlist — stolen vehicles, each with an F I R reference "
     "and a priority, mapping one to one onto e-Guj-Cop records in production. "
     "Every plate read is cross referenced against this list continuously."),

    ("v1", "06_alerts",
     "When a match fires, the operator gets the camera, the location, and the "
     "annotated evidence frame, enriched from a VAHAN shaped connector — make, "
     "model, owner, insurance status. "
     "Where a match was fuzzy, it is labelled a probable match and shows the "
     "characters the camera actually read. An operator is never handed an "
     "inference as a certainty."),

    ("v1", "07_trace",
     "The evaluation scenario. Given a registration number, SUTRA reconstructs "
     "that vehicle's timestamped movement history across the network and draws "
     "it on the G I S map. "
     "Where a vehicle was seen at one location only, it says so plainly rather "
     "than leaving an unexplained dot — a route line appears as soon as a second "
     "camera reads the same plate."),

    ("v1", "08_report",
     "And every detection exports to a timestamped output report — camera, "
     "location, plate, confidence, U T C and I S T timestamps, and its evidence "
     "image. All open source, running on one machine."),

    # ---------------------------------------------------------- video 2
    ("v2", "01_onboard",
     "SUTRA onboards the Government provided cameras automatically from the "
     "challenge portal's own catalogue. Thirty live feeds across five "
     "departments, a mix of H two six four and H two six five, at different "
     "resolutions. "
     "They are pulled over authenticated R T S P, with credentials injected at "
     "connection time. The credentials are never written into the registry, "
     "never logged, and never stored with the camera record."),

    ("v2", "02_live",
     "Live viewing of the Government feeds. These are the portal's cameras — "
     "Junagadh, Gir Somnath, Ahmedabad — decoding right now on this machine. "
     "We measured the portal before designing for it. It rations delivery to "
     "about five megabits per second per client, whether you open ten "
     "connections or twenty. That is three to four real time streams. "
     "So the scheduler rotates all thirty cameras through the slots available, "
     "rather than opening thirty connections that would all starve."),

    ("v2", "03_anpr",
     "Number plate recognition running on the Government feeds. These are "
     "today's reads from the Junagadh and Gir Somnath cameras, each one with the "
     "camera it came from, a timestamp, and the confidence of the read. "
     "That confidence column is deliberate. These are plates fifty to ninety "
     "pixels tall on a live street. Reads above about zero point nine five are "
     "reliable. Below that, characters can be wrong. Publishing the number "
     "without the confidence would invite you to treat every row as a fact."),

    ("v2", "04_evidence",
     "Every read is evidenced. This is the actual crop the recognition ran on, "
     "kept alongside the detection, so any read can be checked by a human. "
     "That is the minimum bar for anything that might support an investigation."),

    ("v2", "05_report",
     "And this is the required output report, straight from the Government "
     "feeds. Eighty two plate reads over a two hour run, fifty one distinct "
     "registration numbers, each with U T C and I S T timestamps and a path to "
     "its evidence image."),

    ("v2", "06_atlas",
     "Completing the Model One foundation: a layered coverage map by department, "
     "camera type and status. District level gap analysis showing thin coverage "
     "and ageing infrastructure. And a full metadata audit trail — every "
     "onboarding, export and watchlist change recorded against a user. "
     "The hosted platform, the source code and this report are all linked in the "
     "submission."),
]


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return round(float(out.stdout.strip()), 2)


async def synth(text: str, dest: Path) -> Path:
    """Write the audio and an SRT beside it.

    edge-tts reports boundary events as it speaks, so captions carry the
    synthesiser's own timings rather than an estimate from shot length — they
    stay in step even where a sentence runs long.
    """
    comm = edge_tts.Communicate(text, VOICE, rate=RATE)
    subs = edge_tts.SubMaker()
    with open(dest, "wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                # this voice reports sentence boundaries, which is the right
                # granularity for captions anyway — a cue per sentence rather
                # than a word flickering at a time
                subs.feed(chunk)
    srt = dest.with_suffix(".srt")
    srt.write_text(subs.get_srt(), encoding="utf-8")
    return srt


async def main() -> int:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "narration")
    outdir.mkdir(parents=True, exist_ok=True)

    timeline: dict[str, list[dict]] = {"v1": [], "v2": []}
    for video, shot, text in SHOTS:
        dest = outdir / f"{video}_{shot}.mp3"
        await synth(text, dest)
        d = duration(dest)
        start = sum(s["duration"] for s in timeline[video])
        timeline[video].append(
            {"shot": shot, "file": dest.name, "duration": d, "start": round(start, 2)})
        print(f"  {video} {shot:<14} {d:6.2f}s  (starts {start:6.2f}s)")

    # one concatenated track per video, for muxing onto the screen capture
    for video, shots in timeline.items():
        lst = outdir / f"{video}_concat.txt"
        lst.write_text("".join(f"file '{s['file']}'\n" for s in shots), encoding="utf-8")
        track = outdir / f"{video}_narration.mp3"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                        "-safe", "0", "-i", str(lst), "-c", "copy", str(track)], check=True)
        total = sum(s["duration"] for s in shots)
        print(f"\n{video}: {len(shots)} shots, total {total:.1f}s ({total/60:.1f} min) -> {track.name}")

    (outdir / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    print(f"\ntimeline -> {outdir/'timeline.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
