#!/usr/bin/env python3
"""Prepare TAB regions for digit OCR by removing staff/bar lines and enlarging glyphs.

Requires OpenCV. Output images are recognition aids only; retain original score
systems for provenance and visual validation.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top", type=float, default=0.52, help="top fraction of image to discard")
    parser.add_argument("--scale", type=float, default=2.0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for source in sorted(args.input.glob("*.jpg")):
        gray = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
        top = round(gray.shape[0] * args.top)
        crop = gray[top:, :]
        binary = cv2.threshold(crop, 125, 255, cv2.THRESH_BINARY)[1]
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (55, 1)))
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 55)))
        glyphs = cv2.subtract(binary, cv2.bitwise_or(horizontal, vertical))
        glyphs = cv2.morphologyEx(glyphs, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        page = cv2.bitwise_not(glyphs)
        enlarged = cv2.resize(page, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_CUBIC)
        cv2.imwrite(str(args.output / source.name), enlarged, [cv2.IMWRITE_JPEG_QUALITY, 96])
    print(f"Prepared {len(list(args.input.glob('*.jpg')))} TAB OCR images in {args.output}")


if __name__ == "__main__":
    main()
