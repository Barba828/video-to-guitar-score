#!/usr/bin/env python3
"""Map macOS Vision digit candidates onto TAB strings and derive pitches.

Vision bounding boxes use a bottom-left origin. TAB line locations use image
pixels from the top. Only digit-only OCR items close to one of the six detected
TAB lines are accepted; everything else remains outside the fingering ledger.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def image_size(path: Path) -> tuple[int, int]:
    output = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    width = int(next(line.split(":", 1)[1] for line in output.splitlines() if "pixelWidth" in line))
    height = int(next(line.split(":", 1)[1] for line in output.splitlines() if "pixelHeight" in line))
    return width, height


def cluster(notes: list[dict], tolerance: float) -> list[dict]:
    groups: list[list[dict]] = []
    for note in sorted(notes, key=lambda item: item["source"]["center_x"]):
        x = note["source"]["center_x"]
        if not groups or abs(x - sum(n["source"]["center_x"] for n in groups[-1]) / len(groups[-1])) > tolerance:
            groups.append([note])
        else:
            groups[-1].append(note)
    return [
        {
            "x": sum(note["source"]["center_x"] for note in group) / len(group),
            "notes": sorted(group, key=lambda note: note["string"]),
            "confidence": min(note["confidence"] for note in group),
            "status": "needs_visual_verification",
        }
        for group in groups
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ocr", type=Path)
    parser.add_argument("line_manifest", type=Path)
    parser.add_argument("--systems", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capo", type=int, default=0)
    parser.add_argument("--tuning", default="40,45,50,55,59,64")
    parser.add_argument("--line-tolerance", type=float, default=0.028, help="maximum normalized distance from a TAB line")
    parser.add_argument("--event-tolerance", type=float, default=0.012)
    args = parser.parse_args()

    tuning = [int(value) for value in args.tuning.split(",")]
    if len(tuning) != 6:
        raise SystemExit("--tuning must contain six MIDI pitches, low to high")
    ocr = json.loads(args.ocr.read_text())
    lines = json.loads(args.line_manifest.read_text())
    line_by_name = {item["system"]: item for item in lines["systems"] if item.get("status") == "ok"}
    output_systems = []
    total = 0
    for page in ocr["pages"]:
        name = Path(page["file"]).name
        line_item = line_by_name.get(name)
        if not line_item:
            output_systems.append({"file": name, "status": "needs_review", "events": []})
            continue
        width, height = image_size(args.systems / name)
        normalized_lines = [value / height for value in line_item["line_y"]]
        notes = []
        for item in page["items"]:
            text = item["text"].strip()
            if not re.fullmatch(r"\d{1,2}", text):
                continue
            x, y, w, h = [float(value) for value in item["bbox"]]
            center_y_top = 1.0 - (y + h / 2)
            string_index = min(range(6), key=lambda index: abs(normalized_lines[index] - center_y_top))
            distance = abs(normalized_lines[string_index] - center_y_top)
            if distance > args.line_tolerance:
                continue
            string = string_index + 1
            fret = int(text)
            notes.append(
                {
                    "string": string,
                    "fret": fret,
                    "pitch_midi": tuning[6 - string] + args.capo + fret,
                    "confidence": float(item["confidence"]),
                    "source": {
                        "file": name,
                        "bbox": [x, 1.0 - (y + h), w, h],
                        "center_x": x + w / 2,
                        "method": "vision_candidate",
                        "status": "needs_visual_verification",
                    },
                }
            )
        total += len(notes)
        output_systems.append(
            {
                "file": name,
                "line_y": line_item["line_y"],
                "status": "candidate",
                "events": cluster(notes, args.event_tolerance),
            }
        )
    result = {
        "version": 1,
        "authority": "candidate_only_requires_visual_verification",
        "metadata": {"tuning_midi": tuning, "capo": args.capo},
        "systems": output_systems,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Mapped {total} Vision OCR digits to TAB strings -> {args.output}")


if __name__ == "__main__":
    main()
