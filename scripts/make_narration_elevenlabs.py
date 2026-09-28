"""Regenerate the demo narration with an ElevenLabs voice (optionally a clone).

Same shot list and same output shape as make_narration.py, so the recording
driver and the mux step do not change — only the voice does. Kept separate
rather than folded in because edge-tts needs no account and must keep working
for anyone cloning this repository.

The API key is read from backend/.env (gitignored), never from the command
line, so it cannot end up in shell history or a transcript:

    ELEVENLABS_API_KEY=...
    ELEVENLABS_VOICE_ID=...        # from the voice's page in the dashboard

    python scripts/make_narration_elevenlabs.py <outdir>
"""

import json
import subprocess
import sys
from pathlib import Path

import httpx

from make_narration import SHOTS          # single source of truth for the script

MODEL = "eleven_multilingual_v2"          # best quality for cloned voices
API = "https://api.elevenlabs.io/v1/text-to-speech"
REPO = Path(__file__).resolve().parents[1]


def env() -> dict[str, str]:
    path = REPO / "backend" / ".env"
    if not path.is_file():
        sys.exit(f"no {path} — see docs for the two ELEVENLABS_ keys")
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    missing = [k for k in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID") if not out.get(k)]
    if missing:
        sys.exit(f"missing in backend/.env: {', '.join(missing)}")
    return out


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return round(float(r.stdout.strip()), 2)


def main() -> int:
    cfg = env()
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "narration_11")
    outdir.mkdir(parents=True, exist_ok=True)

    chars = sum(len(t) for _, _, t in SHOTS)
    print(f"{len(SHOTS)} shots, {chars} characters of speech\n")

    timeline: dict[str, list[dict]] = {"v1": [], "v2": []}
    with httpx.Client(timeout=180) as client:
        for video, shot, text in SHOTS:
            dest = outdir / f"{video}_{shot}.mp3"
            r = client.post(
                f"{API}/{cfg['ELEVENLABS_VOICE_ID']}",
                headers={"xi-api-key": cfg["ELEVENLABS_API_KEY"],
                         "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": MODEL,
                    # stability low-ish keeps delivery lively; similarity high
                    # keeps a cloned voice recognisably the speaker's
                    "voice_settings": {"stability": 0.45, "similarity_boost": 0.8,
                                       "style": 0.15, "use_speaker_boost": True},
                },
            )
            if r.status_code != 200:
                sys.exit(f"\n{video} {shot}: HTTP {r.status_code} — {r.text[:300]}")
            dest.write_bytes(r.content)
            d = duration(dest)
            start = sum(s["duration"] for s in timeline[video])
            timeline[video].append(
                {"shot": shot, "file": dest.name, "duration": d, "start": round(start, 2)})
            print(f"  {video} {shot:<14} {d:6.2f}s")

    for video, shots in timeline.items():
        lst = outdir / f"{video}_concat.txt"
        lst.write_text("".join(f"file '{s['file']}'\n" for s in shots), encoding="utf-8")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", str(outdir / f"{video}_narration.mp3")],
                       check=True)
        total = sum(s["duration"] for s in shots)
        flag = "  <-- OVER 3:00" if video == "v1" and total > 180 else ""
        print(f"\n{video}: {total:.1f}s ({total/60:.2f} min){flag}")

    (outdir / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    print(f"\ntimeline -> {outdir/'timeline.json'}")
    print("re-record with this timeline, since shot lengths will differ from the edge-tts take")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
