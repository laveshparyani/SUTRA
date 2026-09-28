"""Caption and highlight a SUTRA screenshot in the platform's own visual language.

Adds a navy caption band (amber title, ice body text) under the screenshot and,
optionally, amber rounded highlights with numbered badges over regions of the
page. Palette and type match the Command UI and the solution deck, so the
annotation reads as intentional, not pasted on.

Usage (one screenshot):
    python scripts/annotate_screenshot.py in.png out.png \
        --title "Registry" --text "One line of context.|Second line." \
        --box 120,80,640,300 --box 700,80,1200,300

Boxes are x1,y1,x2,y2 in the source image's pixels; the first box gets badge
1, the second badge 2, and so on. Caption lines are separated with '|'.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = (14, 26, 43)
INK_EDGE = (36, 50, 64)
AMBER = (240, 164, 40)
ICE = (203, 216, 232)
MUTE = (138, 155, 176)
WHITE = (255, 255, 255)

FONTS = Path(r"C:\Windows\Fonts")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def annotate(src: Path, dst: Path, title: str, text: str, boxes: list[tuple[int, int, int, int]],
             step: str = "") -> None:
    img = Image.open(src).convert("RGB")
    w, h = img.size
    scale = w / 1600  # keep proportions stable across capture sizes

    # --- highlights on the page itself -------------------------------------
    over = img.copy()
    d = ImageDraw.Draw(over)
    badge_font = font(int(22 * scale), bold=True)
    for i, (x1, y1, x2, y2) in enumerate(boxes, 1):
        d.rounded_rectangle((x1, y1, x2, y2), radius=int(10 * scale), outline=AMBER, width=max(3, int(4 * scale)))
        r = int(18 * scale)
        cx, cy = x1 + r + int(4 * scale), y1 - r - int(4 * scale)
        if cy - r < 0:
            cy = y1 + r + int(6 * scale)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=AMBER)
        label = str(i)
        tw = d.textlength(label, font=badge_font)
        d.text((cx - tw / 2, cy - badge_font.size * 0.62), label, font=badge_font, fill=INK)
    img = over

    # --- caption band ------------------------------------------------------
    pad = int(28 * scale)
    title_font = font(int(26 * scale), bold=True)
    body_font = font(int(17 * scale))
    tag_font = font(int(12 * scale), bold=True)
    tmp = ImageDraw.Draw(img)
    body_lines: list[str] = []
    for part in text.split("|"):
        body_lines += wrap(tmp, part.strip(), body_font, w - 2 * pad)
    line_h = int(body_font.size * 1.45)
    band_h = pad + title_font.size + int(10 * scale) + len(body_lines) * line_h + pad

    canvas = Image.new("RGB", (w, h + band_h), INK)
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, h, w, h + int(4 * scale)), fill=AMBER)
    d.line((0, h + int(4 * scale), w, h + int(4 * scale)), fill=INK_EDGE)

    y = h + pad
    if step:
        d.text((pad, y - int(2 * scale)), step.upper(), font=tag_font, fill=AMBER)
        y += tag_font.size + int(8 * scale)
    d.text((pad, y), title, font=title_font, fill=WHITE)
    y += title_font.size + int(10 * scale)
    for i, line in enumerate(body_lines):
        d.text((pad, y), line, font=body_font, fill=ICE)
        y += line_h

    # brand mark top-right of the band, on the tag line, clear of the body text
    foot = "SUTRA · Statewide Unified Tracking, Registry & Analytics"
    fw = d.textlength(foot, font=tag_font)
    d.text((w - pad - fw, h + pad - int(2 * scale)), foot, font=tag_font, fill=MUTE)

    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst, optimize=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--text", required=True, help="caption lines separated by '|'")
    ap.add_argument("--step", default="", help="small amber tag above the title, e.g. '03 · Analyse'")
    ap.add_argument("--box", action="append", default=[], help="x1,y1,x2,y2 highlight (repeatable)")
    a = ap.parse_args()
    boxes = [tuple(int(v) for v in b.split(",")) for b in a.box]
    annotate(a.src, a.dst, a.title, a.text, boxes, a.step)
    print("wrote", a.dst)


if __name__ == "__main__":
    main()
