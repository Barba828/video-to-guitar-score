#!/usr/bin/env python3
"""Extract the opening frame and visual scene changes from a local score video.

Requires ffmpeg/ffprobe. This deliberately does not download URLs: acquisition is
authorization- and platform-specific, while extraction is reproducible locally.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scene-threshold", type=float, default=0.035,
                        help="ffmpeg scene-change threshold (lower captures more candidates)")
    parser.add_argument("--quality", type=int, default=2, choices=range(2, 32),
                        help="JPEG quality scale; 2 is highest")
    parser.add_argument("--crop",
                        help="optional ffmpeg crop expression, e.g. 1300:290:150:790")
    args = parser.parse_args()
    if not args.video.is_file():
        parser.error(f"video not found: {args.video}")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("ffmpeg and ffprobe are required")

    output = args.output
    frames = output / "source-frames"
    frames.mkdir(parents=True, exist_ok=True)
    # A score page may begin at time zero and is not a scene transition.
    opening = ["ffmpeg", "-y", "-ss", "0", "-i", str(args.video)]
    if args.crop:
        opening += ["-vf", f"crop={args.crop}"]
    opening += ["-frames:v", "1", "-update", "1", "-q:v", str(args.quality),
                str(frames / "0000-opening.jpg")]
    run(opening)
    # FFmpeg 9's MJPEG encoder rejects limited-range YUV input. Converting to
    # full-range yuvj420p keeps JPEG extraction working across FFmpeg versions.
    filters = []
    if args.crop:
        filters.append(f"crop={args.crop}")
    filters += [f"select=gt(scene\\,{args.scene_threshold})", "showinfo", "format=yuvj420p"]
    vf = ",".join(filters)
    scenes = subprocess.run(
        ["ffmpeg", "-y", "-i", str(args.video), "-vf", vf, "-fps_mode", "vfr",
         "-q:v", str(args.quality), str(frames / "%04d-scene.jpg")],
        check=True, capture_output=True, text=True,
    )
    timestamps = [float(value) for value in re.findall(r"n:\s*\d+.*?pts_time:([0-9.]+)", scenes.stderr)]
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(args.video)],
        check=True, capture_output=True, text=True,
    )
    manifest = {
        "version": 1,
        "source_video": str(args.video.resolve()),
        "duration_seconds": float(json.loads(probe.stdout)["format"]["duration"]),
        "scene_threshold": args.scene_threshold,
        "crop": args.crop,
        "candidates": [{"file": "0000-opening.jpg", "timestamp_seconds": 0.0}]
        + [{"file": f"{index:04d}-scene.jpg", "timestamp_seconds": timestamp}
           for index, timestamp in enumerate(timestamps, start=1)],
        "note": "Review source-frames, keep score pages, crop them into pages/, and add timestamps to manifest.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote candidate frames to {frames}")


if __name__ == "__main__":
    main()
