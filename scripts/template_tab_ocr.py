#!/usr/bin/env python3
"""Recognize TAB digits at rhythmic stem positions using visual templates.

The recognizer learns the score's own digit font from high-confidence Vision
OCR candidates plus optional visually verified seed labels. It detects rhythmic
stems, samples all six TAB strings at each stem, removes staff/stem lines, and
classifies only patches with sufficient digit ink. Output remains candidate data
until a human/vision pass marks it verified.

Requires OpenCV and NumPy.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


def glyph_feature(gray: np.ndarray, x: int, y: int) -> tuple[np.ndarray | None, int]:
    # TAB lines in the source are about 32 px apart. Keep the crop inside one
    # string lane so a chord digit on an adjacent string cannot contaminate the
    # classifier.
    top, bottom = max(0, y - 15), min(gray.shape[0], y + 16)
    left, right = max(0, x - 18), min(gray.shape[1], x + 19)
    patch = (gray[top:bottom, left:right] > 150).astype(np.uint8)
    center_y = min(15, patch.shape[0] // 2)
    patch[max(0, center_y - 2):min(patch.shape[0], center_y + 3), :] = 0
    vertical = cv2.morphologyEx(patch, cv2.MORPH_OPEN, np.ones((13, 1), np.uint8))
    patch = np.clip(patch - vertical, 0, 1)
    rows, columns = np.where(patch > 0)
    ink = len(columns)
    if ink < 20:
        return None, ink
    glyph = patch[rows.min():rows.max() + 1, columns.min():columns.max() + 1]
    scale = min(28 / glyph.shape[1], 32 / glyph.shape[0])
    width = max(1, round(glyph.shape[1] * scale))
    height = max(1, round(glyph.shape[0] * scale))
    glyph = cv2.resize(glyph, (width, height), interpolation=cv2.INTER_NEAREST)
    normalized = np.zeros((36, 32), np.uint8)
    offset_x = (32 - width) // 2
    offset_y = (36 - height) // 2
    normalized[offset_y:offset_y + height, offset_x:offset_x + width] = glyph
    return normalized, ink


def detect_event_x(gray: np.ndarray, line_y: list[int]) -> list[int]:
    top = max(0, line_y[0] - 15)
    bottom = min(gray.shape[0], line_y[-1] + 105)
    binary = (gray[top:bottom] > 150).astype(np.uint8)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((35, 1), np.uint8))
    below_last_string = max(0, line_y[-1] + 20 - top)
    active = np.flatnonzero(vertical[below_last_string:, :].any(axis=0))
    groups: list[list[int]] = []
    for value in active.tolist():
        if value < gray.shape[1] * 0.05 or value > gray.shape[1] * 0.95:
            continue
        if not groups or value > groups[-1][-1] + 2:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [round(sum(group) / len(group)) for group in groups if len(group) <= 8]


def similarity(first: np.ndarray, second: np.ndarray) -> float:
    intersection = np.logical_and(first, second).sum()
    union = np.logical_or(first, second).sum()
    return float(intersection / union) if union else 0.0


def classify(feature: np.ndarray, training: list[tuple[int, np.ndarray]], neighbors: int = 7) -> tuple[int, float, float]:
    scored = sorted(((similarity(feature, sample), label) for label, sample in training), reverse=True)
    votes: dict[int, float] = {}
    for score, label in scored[:neighbors]:
        votes[label] = votes.get(label, 0.0) + score ** 3
    ranked = sorted(votes.items(), key=lambda item: item[1], reverse=True)
    label, best_vote = ranked[0]
    second_vote = ranked[1][1] if len(ranked) > 1 else 0.0
    return label, scored[0][0], best_vote - second_vote


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("systems", type=Path)
    parser.add_argument("line_manifest", type=Path)
    parser.add_argument("vision_candidates", type=Path)
    parser.add_argument("--seed-labels", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotated-dir", type=Path)
    parser.add_argument("--capo", type=int, default=0)
    parser.add_argument("--tuning", default="40,45,50,55,59,64")
    parser.add_argument("--presence-threshold", type=int, default=45)
    parser.add_argument("--training-confidence", type=float, default=0.9)
    args = parser.parse_args()

    tuning = [int(value) for value in args.tuning.split(",")]
    if len(tuning) != 6:
        raise SystemExit("--tuning must contain six MIDI pitches, low to high")
    line_data = json.loads(args.line_manifest.read_text())
    lines = {item["system"]: item for item in line_data["systems"] if item.get("status") == "ok"}
    vision = json.loads(args.vision_candidates.read_text())
    vision_by_file = {item["file"]: item for item in vision["systems"]}
    seeds = json.loads(args.seed_labels.read_text()) if args.seed_labels else {"labels": []}

    images: dict[str, np.ndarray] = {}
    training: list[tuple[int, np.ndarray]] = []
    for filename, system in vision_by_file.items():
        if filename not in lines:
            continue
        gray = images.setdefault(filename, cv2.imread(str(args.systems / filename), cv2.IMREAD_GRAYSCALE))
        width = gray.shape[1]
        for event in system.get("events", []):
            for note in event.get("notes", []):
                if float(note.get("confidence", 0)) < args.training_confidence:
                    continue
                x = round(float(note["source"]["center_x"]) * width)
                y = lines[filename]["line_y"][int(note["string"]) - 1]
                feature, ink = glyph_feature(gray, x, y)
                if feature is not None and ink >= args.presence_threshold:
                    training.append((int(note["fret"]), feature))
    for seed in seeds.get("labels", []):
        filename = seed["file"]
        gray = images.setdefault(filename, cv2.imread(str(args.systems / filename), cv2.IMREAD_GRAYSCALE))
        y = lines[filename]["line_y"][int(seed["string"]) - 1]
        feature, _ = glyph_feature(gray, int(seed["x"]), y)
        if feature is None:
            raise ValueError(f"seed label has no glyph ink: {seed}")
        # Verified seeds deliberately carry more voting weight than OCR labels.
        training.extend([(int(seed["fret"]), feature)] * int(seed.get("weight", 5)))
    if not training:
        raise SystemExit("no training glyphs found")

    output_systems = []
    if args.annotated_dir:
        args.annotated_dir.mkdir(parents=True, exist_ok=True)
    for filename in sorted(lines):
        gray = images.setdefault(filename, cv2.imread(str(args.systems / filename), cv2.IMREAD_GRAYSCALE))
        color = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        line_y = lines[filename]["line_y"]
        x_positions = detect_event_x(gray, line_y)
        events = []
        for event_index, x in enumerate(x_positions, start=1):
            notes = []
            for string, y in enumerate(line_y, start=1):
                feature, ink = glyph_feature(gray, x, y)
                if feature is None or ink < args.presence_threshold:
                    continue
                fret, score, margin = classify(feature, training)
                confidence = max(0.0, min(1.0, 0.55 * score + 0.45 * min(1.0, margin)))
                notes.append(
                    {
                        "string": string,
                        "fret": fret,
                        "pitch_midi": tuning[6 - string] + args.capo + fret,
                        "confidence": confidence,
                        "source": {
                            "file": filename,
                            "bbox": [(x - 18) / gray.shape[1], (y - 15) / gray.shape[0], 37 / gray.shape[1], 31 / gray.shape[0]],
                            "center_x": x / gray.shape[1],
                            "method": "template_candidate",
                            "status": "needs_visual_verification",
                            "ink": ink,
                            "template_similarity": score,
                            "vote_margin": margin,
                        },
                    }
                )
                if args.annotated_dir:
                    cv2.rectangle(color, (x - 15, y - 18), (x + 15, y + 18), (0, 180, 255), 1)
                    cv2.putText(color, str(fret), (x - 8, y - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
            events.append(
                {
                    "index": event_index,
                    "x": x / gray.shape[1],
                    "notes": notes,
                    "confidence": min((note["confidence"] for note in notes), default=0.0),
                    "status": "needs_visual_verification",
                }
            )
        if args.annotated_dir:
            cv2.imwrite(str(args.annotated_dir / filename), color, [cv2.IMWRITE_JPEG_QUALITY, 94])
        output_systems.append(
            {
                "file": filename,
                "line_y": line_y,
                "event_x": [x / gray.shape[1] for x in x_positions],
                "events": events,
                "status": "needs_visual_verification",
            }
        )

    result = {
        "version": 1,
        "authority": "candidate_only_requires_visual_verification",
        "metadata": {"tuning_midi": tuning, "capo": args.capo},
        "training_counts": dict(sorted(Counter(label for label, _ in training).items())),
        "systems": output_systems,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Recognized {sum(len(event['notes']) for system in output_systems for event in system['events'])} "
        f"TAB digits in {sum(len(system['events']) for system in output_systems)} events -> {args.output}"
    )


if __name__ == "__main__":
    main()
