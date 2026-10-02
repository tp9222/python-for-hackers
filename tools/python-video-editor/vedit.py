#!/usr/bin/env python3
"""Launcher so you can run `python vedit.py ...` from this folder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vedit.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
