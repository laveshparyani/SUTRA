"""Mux a recorded take with its narration and burn the captions in.

The captions are burned rather than shipped as a sidecar: the submission is
watched in whatever player the evaluator happens to open, and a separate .srt
is only subtitles if that player goes looking for it.

    python scripts/encode_video.py <take.webm> <narration.mp3> <captions.srt> <out.mp4>

ASS styling note: without PlayResX/PlayResY libass assumes a 384x288 reference
and scales every size up to the real frame, which rendered the first attempt at
roughly three times the intended size and broke lines after single words.
"""

import subprocess
import sys
from pathlib import Path

STYLE = ",".join([
    "FontName=Segoe UI Semibold",
    "FontSize=30",
    "PrimaryColour=&H00FFFFFF",
    "OutlineColour=&H00000000",
    "BackColour=&HA0000000",
    "BorderStyle=3",        # opaque box, so captions stay legible over the map
    "Outline=2",
    "Shadow=0",
    "Alignment=2",          # bottom centre
    "MarginV=180",          # clear of the on-screen verdict banner
    "MarginL=180",
    "MarginR=180",
    "PlayResX=1920",
    "PlayResY=1080",
])


def main() -> int:
    take, audio, srt, out = (Path(a).resolve() for a in sys.argv[1:5])
    out.parent.mkdir(parents=True, exist_ok=True)

    # Run from the subtitle's own directory and pass a bare filename: the
    # filter's argument syntax treats ':' as a separator, so a Windows drive
    # letter in the path needs escaping that varies by ffmpeg build.
    cmd = [
        "ffmpeg", "-y",
        "-i", str(take),
        "-i", str(audio),
        "-vf", f"subtitles={srt.name}:force_style='{STYLE}'",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        "-shortest",
        str(out),
    ]
    print(" ".join(cmd[:9]), "...\n")
    r = subprocess.run(cmd, cwd=srt.parent, stderr=subprocess.PIPE, text=True)
    if r.returncode:
        print(r.stderr[-2500:])
        return r.returncode

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
         "-of", "default=nw=1", str(out)],
        capture_output=True, text=True).stdout.strip()
    print(f"{out}\n{probe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
