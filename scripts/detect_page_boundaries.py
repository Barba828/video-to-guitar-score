#!/usr/bin/env python3
"""Detect scrolling-score page breaks from a wide low-variance separator band.

Requires OpenCV. The output timestamps can be fed to the page stitcher.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-fps", type=float, default=10.0)
    parser.add_argument("--mean-min", type=float, default=140.0)
    parser.add_argument("--std-max", type=float, default=12.0)
    parser.add_argument("--min-band-rows", type=int, default=5)
    args = parser.parse_args()
    capture = cv2.VideoCapture(str(args.video))
    source_fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / source_fps
    step = max(1, round(source_fps / args.sample_fps))
    hits: list[float] = []
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (480, 270), interpolation=cv2.INTER_AREA)
            row_means = gray.mean(axis=1)
            row_stds = gray.std(axis=1)
            band_rows = int(np.count_nonzero((row_means >= args.mean_min) & (row_stds <= args.std_max)))
            if band_rows >= args.min_band_rows:
                hits.append(frame_index / source_fps)
        frame_index += 1
    capture.release()
    groups: list[list[float]] = []
    for timestamp in hits:
        if not groups or timestamp - groups[-1][-1] > 0.8:
            groups.append([timestamp])
        else:
            groups[-1].append(timestamp)
    boundaries = [round((group[0] + group[-1]) / 2, 3) for group in groups]
    args.output.write_text(json.dumps({"version": 1, "duration_seconds": duration, "boundaries_seconds": boundaries}, indent=2) + "\n")
    print(f"Detected {len(boundaries)} page-boundary bands: {boundaries}")


if __name__ == "__main__":
    main()
