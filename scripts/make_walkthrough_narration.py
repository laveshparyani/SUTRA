"""Synthesise the walkthrough narration, one clip per test case."""
import asyncio, json, subprocess, sys
from pathlib import Path
import edge_tts
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walkthrough_steps import steps

VOICE, RATE = "en-US-BrianMultilingualNeural", "-8%"


def dur(p: Path) -> float:
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-of","csv=p=0",str(p)], capture_output=True, text=True, check=True)
    return round(float(r.stdout.strip()), 2)


async def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    tl = []
    for ref, title, text, action in steps():
        slug = ref.replace(".", "_")
        dest = out / f"wt_{slug}.mp3"
        comm, subs = edge_tts.Communicate(text, VOICE, rate=RATE), edge_tts.SubMaker()
        with open(dest, "wb") as fh:
            async for ch in comm.stream():
                if ch["type"] == "audio": fh.write(ch["data"])
                elif ch["type"] in ("SentenceBoundary","WordBoundary"): subs.feed(ch)
        (out / f"wt_{slug}.srt").write_text(subs.get_srt(), encoding="utf-8")
        d = dur(dest)
        tl.append({"shot": f"wt_{slug}", "ref": ref, "title": title,
                   "action": action, "file": dest.name, "duration": d,
                   "start": round(sum(s["duration"] for s in tl), 2)})
        print(f"  {ref:<6} {d:6.2f}s  {title[:44]}")
    lst = out / "wt_concat.txt"
    lst.write_text("".join(f"file '{s['file']}'\n" for s in tl), encoding="utf-8")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0",
                    "-i",str(lst),"-c","copy",str(out/"wt_narration.mp3")], check=True)
    (out/"timeline.json").write_text(json.dumps({"wt": tl}, indent=2), encoding="utf-8")
    total = sum(s["duration"] for s in tl)
    print(f"\n{len(tl)} steps, total {total:.0f}s ({total/60:.1f} min)")
    return 0

raise SystemExit(asyncio.run(main()))
