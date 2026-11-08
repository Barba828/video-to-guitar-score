#!/usr/bin/env python3
"""Apply one verified FFmpeg crop rectangle to a directory of score-frame JPEGs."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="directory of reviewed JPEG score fragments")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--crop", required=True, metavar="W:H:X:Y",
                        help="verified FFmpeg crop geometry; preserve source frames separately")
    args = parser.parse_args()
    sources = sorted(args.input.glob("*.jpg"))
    if not sources:
        parser.error(f"no JPEG files in {args.input}")
    args.output.mkdir(parents=True, exist_ok=True)
    for source in sources:
        destination = args.output / source.name
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-vf", f"crop={args.crop}", str(destination)], check=True)
    print(f"Wrote {len(sources)} cleaned candidates to {args.output}")


if __name__ == "__main__":
    main()
