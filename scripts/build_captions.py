"""Merge the per-shot SRTs into one caption track per video.

Each shot's subtitles start at zero, because each was synthesised on its own.
Shifting every cue by that shot's start time in the timeline reassembles them
into a single file that matches the concatenated narration.

    python scripts/build_captions.py <narration_dir>
"""

import json
import re
import sys
from pathlib import Path

CUE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def to_ts(ms):
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> int:
    narration = Path(sys.argv[1])
    timeline = json.loads((narration / "timeline.json").read_text(encoding="utf-8"))

    for video, shots in timeline.items():
        out, n = [], 0
        for shot in shots:
            srt = narration / f"{video}_{shot['shot']}.srt"
            if not srt.is_file():
                print(f"  missing {srt.name}")
                continue
            offset = int(shot["start"] * 1000)
            blocks = [b for b in srt.read_text(encoding="utf-8").strip().split("\n\n") if b.strip()]
            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) < 3:
                    continue
                m = CUE.search(lines[1])
                if not m:
                    continue
                g = m.groups()
                start = to_ms(*g[:4]) + offset
                end = to_ms(*g[4:]) + offset
                n += 1
                out.append(f"{n}\n{to_ts(start)} --> {to_ts(end)}\n" + "\n".join(lines[2:]))

        dest = narration / f"{video}_captions.srt"
        dest.write_text("\n\n".join(out) + "\n", encoding="utf-8")
        last = to_ts(to_ms(*CUE.search(out[-1].split("\n")[1]).groups()[4:])) if out else "-"
        print(f"  {video}: {n} cues, ends {last} -> {dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
