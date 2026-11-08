#!/usr/bin/env python3
"""Select unique full score-system frames from scrolling-video candidates.

Requires OpenCV. Combines brightness, separator-band rejection, and aligned
duplicate detection. The output remains a reviewable draft selection.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction", type=Path)
    parser.add_argument("--input-dir", default="cleaned-pages")
    parser.add_argument("--output-dir", default="selected-systems")
    parser.add_argument("--min-luma", type=float, default=18.0)
    parser.add_argument("--duplicate-response", type=float, default=0.75)
    args = parser.parse_args()
    manifest_path = args.extraction / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    luma = {item["page_file"]: item["mean_luma"] for item in manifest["curation"]["kept"]}
    source_dir = args.extraction / args.input_dir
    target_dir = args.extraction / args.output_dir
    target_dir.mkdir(exist_ok=True)
    selected, rejected = [], []
    previous: np.ndarray | None = None
    for source in sorted(source_dir.glob("*.jpg")):
        image = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
        small = cv2.resize(image, (480, 245), interpolation=cv2.INTER_AREA).astype(np.float32)
        uniform_band_rows = int(np.count_nonzero((small.mean(axis=1) > 80) & (small.std(axis=1) < 20)))
        response = 0.0 if previous is None else float(cv2.phaseCorrelate(previous, small)[1])
        reasons = []
        if luma.get(source.name, 0) < args.min_luma:
            reasons.append("low_content_luma")
        if uniform_band_rows >= 5:
            reasons.append("page_separator")
        if response >= args.duplicate_response:
            reasons.append("aligned_duplicate")
        item = {"file": source.name, "mean_luma": luma.get(source.name), "uniform_band_rows": uniform_band_rows,
                "previous_alignment_response": round(response, 5)}
        if reasons:
            rejected.append({**item, "reasons": reasons})
        else:
            destination = target_dir / f"{len(selected) + 1:03d}.jpg"
            shutil.copy2(source, destination)
            selected.append({**item, "selected_file": destination.name})
        previous = small
    manifest["system_selection"] = {"selected": selected, "rejected": rejected, "output_dir": args.output_dir}
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"Selected {len(selected)} unique full score systems; rejected {len(rejected)} transitions/duplicates.")


if __name__ == "__main__":
    main()
