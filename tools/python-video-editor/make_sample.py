#!/usr/bin/env python3
"""Build a throwaway clip to practise on: a burned-in timecode plus a fake
password banner, so you can see exactly what got kept and what got hidden.

    python make_sample.py                 -> sample.mp4, 30 s, 1280x720
    python make_sample.py out.mp4 --secs 60
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vedit.ffmpeg_tools import FFmpegMissing, find_ffmpeg  # noqa: E402

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _font() -> str | None:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            # ffmpeg filter syntax needs the drive colon escaped
            return path.replace("\\", "/").replace(":", r"\:")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", nargs="?", default="sample.mp4")
    parser.add_argument("--secs", type=int, default=30)
    parser.add_argument("--size", default="1280x720")
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    try:
        ffmpeg = find_ffmpeg()
    except FFmpegMissing as exc:
        print(exc, file=sys.stderr)
        return 3

    font = _font()
    if font:
        overlays = (
            "drawtext=fontfile='%s':text='t=%%{pts\\:hms}':x=40:y=40:fontsize=48:"
            "fontcolor=white:box=1:boxcolor=black@0.7,"
            "drawtext=fontfile='%s':text='PASSWORD hunter2':x=400:y=520:fontsize=40:"
            "fontcolor=yellow:box=1:boxcolor=red@0.8" % (font, font)
        )
    else:
        print("no usable font found -- the clip will have no text overlay", file=sys.stderr)
        overlays = "null"

    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=%s:rate=%d:duration=%d" % (args.size, args.fps, args.secs),
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=%d" % args.secs,
        "-vf", overlays,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", args.output,
    ]
    subprocess.run(command, check=True)
    size = Path(args.output).stat().st_size / 1e6
    print("wrote %s  (%.1f MB, %d s)" % (args.output, size, args.secs))
    print()
    print("try:")
    print("  python vedit.py gui %s" % args.output)
    print("  python vedit.py cut %s -o cut.mp4 --keep 0.5-1.5,2.2-4.1" % args.output)
    print("  python vedit.py cut %s -o safe.mp4 --box 390,505,420,70" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
