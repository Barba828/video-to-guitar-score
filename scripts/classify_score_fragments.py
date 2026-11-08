#!/usr/bin/env python3
"""Identify score-like frames by detecting repeated long horizontal staff/TAB lines.

This deliberately classifies visual structure, not musical content. It separates
black title/progress cards from score fragments before a human or OMR pass groups
fragments into pages.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def dimensions(path: Path) -> tuple[int, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def long_line_rows(path: Path, bright_threshold: int, coverage: float) -> int:
    width, height = dimensions(path)
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        check=True, capture_output=True,
    )
    pixels = result.stdout
    if len(pixels) != width * height:
        raise RuntimeError(f"unexpected grayscale size for {path}")
    minimum = round(width * coverage)
    return sum(sum(value >= bright_threshold for value in pixels[row * width:(row + 1) * width]) >= minimum
               for row in range(height))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction", type=Path)
    parser.add_argument("--input-dir", default="cleaned-pages")
    parser.add_argument("--output-dir", default="score-fragments")
    parser.add_argument("--bright-threshold", type=int, default=180)
    parser.add_argument("--row-coverage", type=float, default=0.35)
    parser.add_argument("--min-line-rows", type=int, default=8)
    args = parser.parse_args()
    manifest_path = args.extraction / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    source_dir = args.extraction / args.input_dir
    target_dir = args.extraction / args.output_dir
    target_dir.mkdir(exist_ok=True)
    kept, rejected = [], []
    for source in sorted(source_dir.glob("*.jpg")):
        rows = long_line_rows(source, args.bright_threshold, args.row_coverage)
        item = {"file": source.name, "long_line_rows": rows}
        if rows >= args.min_line_rows:
            destination = target_dir / source.name
            shutil.copy2(source, destination)
            kept.append(item)
        else:
            rejected.append(item)
    manifest["score_fragment_classification"] = {
        "input_dir": args.input_dir,
        "output_dir": args.output_dir,
        "bright_threshold": args.bright_threshold,
        "row_coverage": args.row_coverage,
        "min_line_rows": args.min_line_rows,
        "kept": kept,
        "rejected": rejected,
        "note": "A kept frame has score-like horizontal line structure, not necessarily a complete unique page. Review before merging.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"Kept {len(kept)} score-like fragments; rejected {len(rejected)} non-score candidates.")


if __name__ == "__main__":
    main()
