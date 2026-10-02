#!/usr/bin/env python3
"""Start the vedit web editor.

    python serve.py                       http://127.0.0.1:5000
    python serve.py --open                and open a browser
    python serve.py --allow-dir D:/clips  also let the page pick files already
                                          on this machine, without uploading

By default it listens on localhost only. Binding anywhere else hands whoever can
reach the port the ability to upload video and download renders, so it asks you
to confirm with --i-know before it will do that.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vedit.ffmpeg_tools import FFmpegMissing, describe_tools  # noqa: E402
from webapp import Settings, create_app  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--allow-dir",
        action="append",
        default=[],
        metavar="DIR",
        help="let the page open files under DIR directly instead of uploading (repeatable)",
    )
    parser.add_argument(
        "--max-upload", type=float, default=8.0, metavar="GB", help="upload size limit (8)"
    )
    parser.add_argument("--work-dir", help="where workspaces live (default: your temp dir)")
    parser.add_argument("--open", action="store_true", help="open a browser once it is up")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--i-know",
        action="store_true",
        help="required to bind to anything other than localhost",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    local = args.host in ("127.0.0.1", "localhost", "::1")
    if not local and not args.i_know:
        print(
            "Refusing to listen on %s.\n\n"
            "This server accepts uploads, runs ffmpeg and serves the results back, and it\n"
            "has no authentication. On a shared network that is an open door. If you really\n"
            "want it, re-run with --i-know, and put it behind something that authenticates."
            % args.host,
            file=sys.stderr,
        )
        return 2

    try:
        print(describe_tools())
    except FFmpegMissing as exc:
        print(exc, file=sys.stderr)
        return 3

    for directory in args.allow_dir:
        if not Path(directory).expanduser().is_dir():
            print("error: --allow-dir %s is not a directory" % directory, file=sys.stderr)
            return 2

    settings = Settings(
        allow_dirs=args.allow_dir,
        max_upload=int(args.max_upload * 1024**3),
        store_root=args.work_dir,
    )
    app = create_app(settings)

    url = "http://%s:%d/" % ("127.0.0.1" if args.host == "0.0.0.0" else args.host, args.port)
    print()
    print("vedit web editor  ->  %s" % url)
    print("workspaces        ->  %s" % settings.store_root)
    if settings.allow_dirs:
        print("browsable         ->  %s" % ", ".join(str(d) for d in settings.allow_dirs))
    else:
        print("browsable         ->  (off; upload only)")
    print("Press Ctrl+C to stop.")
    print()

    if args.open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    # threaded=True matters: the page polls progress while ffmpeg is running.
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True,
            use_reloader=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
