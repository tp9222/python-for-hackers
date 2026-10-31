#!/usr/bin/env python3

import os
import re
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

# matches an ANSI SGR sequence, capturing the parameters (e.g. "1;31")
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

# ANSI foreground codes -> RGB, tuned for a dark background
DEFAULT_FG = (220, 220, 220)
PALETTE = {
    30: (110, 110, 110), 31: (255, 85, 85), 32: (80, 250, 123),
    33: (241, 250, 140), 34: (130, 170, 255), 35: (255, 121, 198),
    36: (139, 233, 253), 37: (220, 220, 220),
    90: (140, 140, 140), 91: (255, 120, 120), 92: (120, 255, 150),
    93: (255, 255, 160), 94: (165, 195, 255), 95: (255, 150, 220),
    96: (170, 245, 255), 97: (255, 255, 255),
}

# monospace fonts that ship on Kali; fall back to PIL's bitmap font
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def load_font(size=16):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def parse_ansi(text):
    """Return a list of lines; each line is a list of (string, rgb) segments."""
    text = text.replace("\r\n", "\n").replace("\r", "").replace("\t", "    ")

    lines = [[]]
    cur = DEFAULT_FG
    pos = 0

    def emit(chunk):
        for i, part in enumerate(chunk.split("\n")):
            if i > 0:
                lines.append([])
            if part:
                lines[-1].append((part, cur))

    for m in SGR_RE.finditer(text):
        emit(text[pos:m.start()])
        codes = [int(c) for c in m.group(1).split(";") if c != ""] or [0]
        for code in codes:
            if code in (0, 39):
                cur = DEFAULT_FG
            elif code in PALETTE:
                cur = PALETTE[code]
            # other codes (bold, backgrounds, ...) are ignored
        pos = m.end()
    emit(text[pos:])

    return lines


def render_terminal(text, out_path, font):
    lines = parse_ansi(text) or [[]]

    ascent, descent = font.getmetrics()
    line_h = ascent + descent + 4

    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    max_w = max(
        (sum(measure.textlength(s, font=font) for s, _ in line) for line in lines),
        default=0,
    )

    pad = 20
    width = int(max_w) + pad * 2
    height = line_h * len(lines) + pad * 2

    img = Image.new("RGB", (width, height), (12, 12, 12))
    draw = ImageDraw.Draw(img)

    y = pad
    for line in lines:
        x = pad
        for seg, color in line:
            draw.text((x, y), seg, font=font, fill=color)
            x += draw.textlength(seg, font=font)
        y += line_h

    img.save(out_path, "PNG")


def main():
    sslscan = shutil.which("sslscan")
    if not sslscan:
        raise SystemExit("sslscan not found on PATH (apt install sslscan)")

    font = load_font()

    with open("ip.txt") as f:
        for raw in f:
            target = raw.strip()
            if not target:
                continue

            proc = subprocess.run(
                [sslscan, "--nofailed", target],
                capture_output=True,
                text=True,
            )
            output = proc.stdout + proc.stderr

            out_path = f"TLS_{target}.png"
            render_terminal(output, out_path, font)
            print(out_path)


if __name__ == "__main__":
    main()
