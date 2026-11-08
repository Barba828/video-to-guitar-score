#!/usr/bin/env python3
"""Extract a clean frame from the middle of each detected score-panel interval."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="manifest from extract_score_pages.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-time", type=float, default=1.0,
                        help="ignore scene changes before this timestamp")
    parser.add_argument("--minimum-interval", type=float, default=1.0,
                        help="merge transition frames closer than this many seconds")
    parser.add_argument("--offset", type=float, default=1.0,
                        help="seconds after each stable panel begins to sample")
    args = parser.parse_args()

    source = json.loads(args.manifest.read_text())
    video = Path(source["source_video"])
    crop = source.get("crop")
    times: list[float] = []
    for candidate in source["candidates"]:
        timestamp = float(candidate["timestamp_seconds"])
        if timestamp < args.minimum_time:
            continue
        if not times or timestamp - times[-1] >= args.minimum_interval:
            times.append(timestamp)

    args.output.mkdir(parents=True, exist_ok=True)
    panels = []
    for index, start in enumerate(times, start=1):
        sample = start + args.offset
        name = f"panel-{index:03d}.png"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{sample:.3f}",
                   "-i", str(video)]
        if crop:
            command += ["-vf", f"crop={crop}"]
        command += ["-frames:v", "1", str(args.output / name)]
        subprocess.run(command, check=True)
        panels.append({"file": name, "panel": index, "start_seconds": start,
                       "sample_seconds": sample})

    result = {"version": 1, "source_video": str(video), "crop": crop, "panels": panels}
    (args.output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Extracted {len(panels)} stable panels -> {args.output}")


if __name__ == "__main__":
    main()
