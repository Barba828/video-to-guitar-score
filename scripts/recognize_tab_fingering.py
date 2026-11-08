#!/usr/bin/env python3
"""OCR TAB digits into pixel-anchored string/fret and sounding-pitch candidates.

This is a candidate generator, not an automatic finalizer. It reads the per-string
images made by extract_tab_strings.py, runs Tesseract with a digit-only alphabet,
maps every result back to the original system image, groups simultaneous digits,
and derives pitch only from the visually observed string/fret plus tuning and capo.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import subprocess
from pathlib import Path


STANDARD_TUNING_LOW_TO_HIGH = [40, 45, 50, 55, 59, 64]


def tesseract_words(image: Path, executable: str, psm: int) -> list[dict]:
    command = [
        executable,
        str(image),
        "stdout",
        "--psm",
        str(psm),
        "-c",
        "tessedit_char_whitelist=0123456789",
        "tsv",
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    rows = csv.DictReader(io.StringIO(completed.stdout), delimiter="\t")
    out = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text.isdigit():
            continue
        confidence = float(row.get("conf", -1))
        if confidence < 0:
            continue
        out.append(
            {
                "text": text,
                "confidence": confidence / 100.0,
                "left": int(row["left"]),
                "top": int(row["top"]),
                "width": int(row["width"]),
                "height": int(row["height"]),
            }
        )
    return out


def cluster_events(notes: list[dict], tolerance: float) -> list[dict]:
    clusters: list[list[dict]] = []
    for note in sorted(notes, key=lambda item: item["source"]["center_x"]):
        center = note["source"]["center_x"]
        if not clusters:
            clusters.append([note])
            continue
        previous_center = sum(item["source"]["center_x"] for item in clusters[-1]) / len(clusters[-1])
        if abs(center - previous_center) <= tolerance:
            clusters[-1].append(note)
        else:
            clusters.append([note])
    events = []
    for cluster in clusters:
        # A valid guitar chord cannot contain two notes on the same string. Keep
        # both OCR candidates visible, but mark the event for review.
        strings = [item["string"] for item in cluster]
        status = "candidate" if len(strings) == len(set(strings)) else "needs_review"
        events.append(
            {
                "x": sum(item["source"]["center_x"] for item in cluster) / len(cluster),
                "notes": sorted(cluster, key=lambda item: item["string"]),
                "status": status,
                "confidence": min(item["confidence"] for item in cluster),
            }
        )
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("strips", type=Path, help="directory made by extract_tab_strings.py")
    parser.add_argument("--systems", type=Path, required=True, help="original selected system images")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--psm", type=int, default=11)
    parser.add_argument("--scale", type=float, default=3.0)
    parser.add_argument("--border", type=float, default=30.0)
    parser.add_argument("--capo", type=int, default=0)
    parser.add_argument("--tuning", default="40,45,50,55,59,64")
    parser.add_argument("--event-tolerance", type=float, default=0.012, help="normalized x grouping tolerance")
    args = parser.parse_args()

    executable = shutil.which(args.tesseract)
    if not executable:
        raise SystemExit(f"Tesseract executable not found: {args.tesseract}")
    tuning = [int(value) for value in args.tuning.split(",")]
    if len(tuning) != 6:
        raise SystemExit("--tuning must contain six MIDI pitches, low to high")

    manifest = json.loads((args.strips / "manifest.json").read_text())
    output_systems = []
    total_notes = 0
    for system in manifest["systems"]:
        if system.get("status") != "ok":
            output_systems.append({"file": system["system"], "status": "needs_review", "events": []})
            continue
        source_path = args.systems / system["system"]
        # OpenCV is intentionally not required here; dimensions are available
        # through the system image header via sips on macOS.
        size = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(source_path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        width = int(next(line.split(":", 1)[1] for line in size.splitlines() if "pixelWidth" in line))
        height = int(next(line.split(":", 1)[1] for line in size.splitlines() if "pixelHeight" in line))
        notes = []
        for strip in system["strips"]:
            string = int(strip["string"])
            strip_path = args.strips / strip["file"]
            for item in tesseract_words(strip_path, executable, args.psm):
                fret = int(item["text"])
                center_strip_x = item["left"] + item["width"] / 2
                source_center_x = center_strip_x / args.scale - args.border
                source_y = float(strip["source_y"]) * height
                source_width = item["width"] / args.scale
                source_height = item["height"] / args.scale
                bbox = [
                    max(0.0, (source_center_x - source_width / 2) / width),
                    max(0.0, (source_y - source_height / 2) / height),
                    min(1.0, source_width / width),
                    min(1.0, source_height / height),
                ]
                notes.append(
                    {
                        "string": string,
                        "fret": fret,
                        "pitch_midi": tuning[6 - string] + args.capo + fret,
                        "confidence": item["confidence"],
                        "source": {
                            "file": system["system"],
                            "bbox": bbox,
                            "center_x": source_center_x / width,
                            "method": "tesseract_candidate",
                            "status": "needs_visual_verification",
                        },
                    }
                )
        events = cluster_events(notes, args.event_tolerance)
        total_notes += len(notes)
        output_systems.append(
            {
                "file": system["system"],
                "line_y": system["line_y"],
                "status": "candidate",
                "events": events,
            }
        )

    result = {
        "version": 1,
        "authority": "candidate_only_requires_visual_verification",
        "metadata": {"tuning_midi": tuning, "capo": args.capo},
        "systems": output_systems,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Recognized {total_notes} TAB digit candidates across {len(output_systems)} systems -> {args.output}")


if __name__ == "__main__":
    main()
