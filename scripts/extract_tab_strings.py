#!/usr/bin/env python3
"""Detect the six TAB lines and create one OCR strip per guitar string.

Requires OpenCV. Output names are SYSTEM-sSTRING.jpg, where string 1 is the
highest-pitched line and string 6 is the lowest.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def grouped_centers(rows: np.ndarray) -> list[int]:
    groups: list[list[int]] = []
    for value in rows.tolist():
        if not groups or value > groups[-1][-1] + 1:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [round(sum(group) / len(group)) for group in groups]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pattern", default="*", help="source filename stem glob")
    parser.add_argument("--strip-half-height", type=int, default=24)
    parser.add_argument("--scale", type=float, default=3.0)
    parser.add_argument("--line-threshold", type=int, default=60)
    parser.add_argument("--line-coverage", type=float, default=0.25)
    parser.add_argument("--fixed-lines",
                        help="comma-separated six y positions for a fixed video overlay")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = []
    sources = sorted([
        *args.input.glob(f"{args.pattern}.jpg"),
        *args.input.glob(f"{args.pattern}.jpeg"),
        *args.input.glob(f"{args.pattern}.png"),
    ])
    for source in sources:
        gray = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
        binary = cv2.threshold(gray, args.line_threshold, 255, cv2.THRESH_BINARY)[1]
        if args.fixed_lines:
            lines = [int(value) for value in args.fixed_lines.split(",")]
            if len(lines) != 6:
                raise SystemExit("--fixed-lines must contain six y positions")
            candidates = [(sum(lines) / len(lines), lines)]
            centers = lines
        else:
            coverage = (binary > 0).mean(axis=1)
            centers = grouped_centers(np.flatnonzero(coverage > args.line_coverage))
            centers = [center for center in centers if gray.shape[0] * 0.05 < center < gray.shape[0] * 0.94]
            candidates: list[tuple[float, list[int]]] = []
            for index in range(max(0, len(centers) - 5)):
                group = centers[index:index + 6]
                diffs = np.diff(group)
                median = float(np.median(diffs))
                if 12 <= median <= 50 and float(np.std(diffs)) <= 4:
                    candidates.append((sum(group) / len(group), group))
        if not candidates:
            manifest.append({"system": source.name, "status": "needs_review", "detected_lines": centers})
            continue
        lines = max(candidates, key=lambda item: item[0])[1]
        item = {"system": source.name, "status": "ok", "line_y": lines, "strips": []}
        for string, center in enumerate(lines, start=1):
            top = max(0, center - args.strip_half_height)
            bottom = min(gray.shape[0], center + args.strip_half_height + 1)
            strip = binary[top:bottom].copy()
            local_center = center - top
            strip[max(0, local_center - 2):min(strip.shape[0], local_center + 3), :] = 0
            vertical = cv2.morphologyEx(strip, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 28)))
            strip = cv2.subtract(strip, vertical)
            page = cv2.bitwise_not(strip)
            page = cv2.copyMakeBorder(page, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
            enlarged = cv2.resize(page, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_CUBIC)
            filename = f"{source.stem}-s{string}.jpg"
            cv2.imwrite(str(args.output / filename), enlarged, [cv2.IMWRITE_JPEG_QUALITY, 96])
            item["strips"].append({"string": string, "file": filename, "source_y": center / gray.shape[0]})
        manifest.append(item)
    (args.output / "manifest.json").write_text(json.dumps({"version": 1, "systems": manifest}, indent=2) + "\n")
    print(f"Prepared string strips for {sum(item['status'] == 'ok' for item in manifest)} of {len(manifest)} systems.")


if __name__ == "__main__":
    main()
