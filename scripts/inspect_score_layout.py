#!/usr/bin/env python3
"""Detect staff/TAB-line bands and probable barlines in cleaned score fragments.

The result is a visual-analysis aid for an OMR/vision pass, not a substitute for
reading notes. All coordinates are normalized so they remain useful after export.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def raster(path: Path) -> tuple[int, int, bytes]:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    stream = json.loads(probe.stdout)["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    if len(decoded) != width * height:
        raise RuntimeError(f"unexpected grayscale size for {path}")
    return width, height, decoded


def runs(indices: list[int]) -> list[list[int]]:
    groups: list[list[int]] = []
    for index in indices:
        if not groups or index > groups[-1][-1] + 1:
            groups.append([index])
        else:
            groups[-1].append(index)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bright-threshold", type=int, default=180)
    parser.add_argument("--row-coverage", type=float, default=0.10,
                        help="minimum bright-pixel share for a likely staff/TAB row")
    parser.add_argument("--column-coverage", type=float, default=0.10,
                        help="minimum bright-pixel share for a possible barline column")
    args = parser.parse_args()
    layouts = []
    for page in sorted(args.pages.glob("*.jpg")):
        width, height, pixels = raster(page)
        line_rows = [row for row in range(height) if sum(value >= args.bright_threshold for value in pixels[row * width:(row + 1) * width]) >= width * args.row_coverage]
        line_columns = [column for column in range(width) if sum(pixels[row * width + column] >= args.bright_threshold for row in range(height)) >= height * args.column_coverage]
        layouts.append({
            "file": page.name,
            "size": [width, height],
            "long_horizontal_runs": [[round(group[0] / height, 5), round(group[-1] / height, 5)] for group in runs(line_rows)],
            "probable_barlines": [round((group[0] + group[-1]) / 2 / width, 5) for group in runs(line_columns)],
        })
    args.output.write_text(json.dumps({"version": 1, "pages": layouts}, indent=2) + "\n")
    print(f"Inspected {len(layouts)} score fragments.")


if __name__ == "__main__":
    main()
