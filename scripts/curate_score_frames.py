#!/usr/bin/env python3
"""Filter near-black scene candidates and copy likely score frames to pages/.

This is deliberately conservative: it only removes frames with almost no visible
content. It preserves all other candidates for visual review and never merges
distinct score fragments without confirmation.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def luma_average(path: Path) -> float:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", "signalstats,metadata=print:file=-", "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    )
    match = re.search(r"lavfi\.signalstats\.YAVG=([0-9.]+)", result.stdout)
    if not match:
        raise RuntimeError(f"could not read luma from {path}")
    return float(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction", type=Path, help="directory created by extract_score_pages.py")
    parser.add_argument("--black-threshold", type=float, default=2.5,
                        help="frames at or below this mean luma are excluded")
    args = parser.parse_args()
    manifest_path = args.extraction / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    frames = args.extraction / "source-frames"
    pages = args.extraction / "pages"
    pages.mkdir(exist_ok=True)
    kept, excluded = [], []
    for candidate in manifest.get("candidates", []):
        source = frames / candidate["file"]
        luma = luma_average(source)
        item = {**candidate, "mean_luma": luma}
        if luma <= args.black_threshold:
            excluded.append(item)
            continue
        destination = pages / f"{len(kept) + 1:03d}-{source.name}"
        shutil.copy2(source, destination)
        kept.append({**item, "page_file": destination.name})
    manifest["curation"] = {"black_threshold": args.black_threshold, "kept": kept, "excluded": excluded,
                             "note": "Kept frames are candidate score fragments. Visually review before calling them pages."}
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"Kept {len(kept)} frames; excluded {len(excluded)} near-black frames.")


if __name__ == "__main__":
    main()
