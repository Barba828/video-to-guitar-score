#!/usr/bin/env python3
"""Assemble visually reviewed TAB candidates into a complete score ledger.

The displayed TAB supplies every string/fret pair. Horizontal rhythm-stem
spacing supplies attack times, including 16th-note triplets. Manual visual
corrections are explicit data, not hidden in this program.
"""
from __future__ import annotations

import argparse
import copy
import json
import statistics
from fractions import Fraction
from pathlib import Path


TUNING_LOW_TO_HIGH = [40, 45, 50, 55, 59, 64]
LEGAL_SLOT_CHUNKS = (Fraction(8), Fraction(6), Fraction(4), Fraction(3), Fraction(2), Fraction(1), Fraction(1, 3))


def frac_text(value: Fraction) -> int | str:
    return value.numerator if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def whole_fraction_from_slots(slots: Fraction) -> list[int]:
    value = slots / 8
    return [value.numerator, value.denominator]


def approximate_note_bbox(event: dict, string: int, line_y: list[int]) -> list[float]:
    x = float(event["x"])
    y = line_y[string - 1] / 980
    return [x - 0.010, y - 0.016, 0.020, 0.032]


def apply_corrections(system: dict, operations: list[dict]) -> list[dict]:
    events = copy.deepcopy(system["events"])
    by_index = {int(event["index"]): event for event in events}
    dropped: set[int] = set()
    for operation in operations:
        if operation["op"] == "insert_event":
            event_index = int(operation["event"])
            event = {
                "index": event_index,
                "x": float(operation["x"]),
                "notes": [
                    {
                        "string": int(note["string"]),
                        "fret": int(note["fret"]),
                        "confidence": 1.0,
                        "manual_correction": operation["reason"],
                    }
                    for note in operation["notes"]
                ],
                "manual_corrections": [operation],
            }
            events.append(event)
            by_index[event_index] = event
            continue
        event_index = int(operation["event"])
        event = by_index[event_index]
        op = operation["op"]
        if op == "drop_event":
            dropped.add(event_index)
            continue
        string = int(operation["string"])
        matches = [note for note in event["notes"] if int(note["string"]) == string]
        if op == "remove":
            event["notes"] = [note for note in event["notes"] if int(note["string"]) != string]
        elif op == "set":
            if matches:
                matches[0]["fret"] = int(operation["fret"])
                matches[0]["manual_correction"] = operation["reason"]
            else:
                event["notes"].append(
                    {
                        "string": string,
                        "fret": int(operation["fret"]),
                        "confidence": 1.0,
                        "manual_correction": operation["reason"],
                        "source": {
                            "file": system["file"],
                            "bbox": approximate_note_bbox(event, string, system["line_y"]),
                        },
                    }
                )
        else:
            raise ValueError(f"unsupported correction operation: {op}")
        event.setdefault("manual_corrections", []).append(operation)
    return sorted(
        [event for event in events if int(event["index"]) not in dropped],
        key=lambda event: float(event["x"]),
    )


def estimate_base_gap(events: list[dict]) -> float:
    gaps = [float(b["x"]) - float(a["x"]) for a, b in zip(events, events[1:])]
    normal = [gap for gap in gaps if 0.030 <= gap <= 0.070]
    if not normal:
        raise ValueError("cannot estimate eighth-note spacing")
    return statistics.median(normal)


def quantize_gap_to_slots(gap: float, base: float) -> Fraction:
    ratio = gap / base
    if ratio < 0.65:
        return Fraction(1, 3)
    return Fraction(max(1, round(ratio)))


def split_slots(value: Fraction) -> list[Fraction]:
    if value <= 0:
        raise ValueError(f"non-positive duration: {value}")
    result: list[Fraction] = []
    remaining = value
    while remaining:
        chunk = next((candidate for candidate in LEGAL_SLOT_CHUNKS if candidate <= remaining), None)
        if chunk is None:
            raise ValueError(f"cannot decompose duration of {value} eighth-note slots")
        result.append(chunk)
        remaining -= chunk
    return result


def effect_for(techniques: dict, system_file: str, event_index: int, string: int) -> list[str]:
    return list(techniques.get(system_file, {}).get(f"{event_index}:{string}", []))


def verified_note(note: dict, system: dict, event: dict, techniques: dict) -> dict:
    string = int(note["string"])
    fret = int(note["fret"])
    source = copy.deepcopy(note.get("source", {}))
    source["file"] = system["file"]
    source.setdefault("bbox", approximate_note_bbox(event, string, system["line_y"]))
    source["method"] = "visual"
    source["status"] = "verified"
    source["ocr_method"] = source.pop("method_candidate", "same_score_template_ocr")
    if "manual_correction" in note:
        source["manual_correction"] = note["manual_correction"]
    result = {
        "string": string,
        "fret": fret,
        "pitch_midi": TUNING_LOW_TO_HIGH[6 - string] + 2 + fret,
        "confidence": 1.0,
        "source": source,
    }
    effects = effect_for(techniques, system["file"], int(event["index"]), string)
    if effects:
        result["effects"] = effects
    return result


def build_measure(system: dict, events: list[dict], measure_number: int, measure_in_system: int, timestamp: float, chord_annotations: list[dict], techniques: dict) -> dict:
    base = estimate_base_gap(events)
    durations = [quantize_gap_to_slots(float(b["x"]) - float(a["x"]), base) for a, b in zip(events, events[1:])]
    used = sum(durations, Fraction(0))
    last = Fraction(8) - used
    if last <= 0:
        raise ValueError(f"{system['file']} measure {measure_in_system}: attacks exceed 4/4 ({used} eighth slots before last event)")
    durations.append(last)

    output_events: list[dict] = []
    measure_chords = [
        chord for chord in chord_annotations
        if (float(chord["x"]) < 0.5) == (measure_in_system == 1)
    ]
    chord_by_event: dict[int, dict] = {}
    for chord in measure_chords:
        nearest = min(events, key=lambda candidate: abs(float(candidate["x"]) - float(chord["x"])))
        diagram = list(chord.get("strings", []))
        if not diagram:
            notes = nearest.get("notes", [])
            diagram = [-1] * 6
            for note in notes:
                diagram[int(note["string"]) - 1] = int(note["fret"])
        positive = [fret for fret in diagram if fret > 0]
        chord_by_event[int(nearest["index"])] = {
            "name": chord["name"],
            "strings": diagram,
            "first_fret": 1 if not positive or max(positive) <= 5 else min(positive),
            "source": {"file": system["file"], "method": "visual", "status": "verified"},
        }
    beat = Fraction(0)
    y0 = max(0, system["line_y"][0] - 24) / 980
    y1 = min(980, system["line_y"][-1] + 24) / 980
    for event, slots in zip(events, durations):
        chunks = split_slots(slots)
        x = float(event["x"])
        notes = [verified_note(note, system, event, techniques) for note in sorted(event["notes"], key=lambda item: int(item["string"]))]
        first_chunk = True
        for chunk in chunks:
            event_source = {
                "file": system["file"],
                "bbox": [x - 0.012, y0, 0.024, y1 - y0],
                "method": "visual",
                "status": "verified",
                "rhythm_method": "tab_stem_spacing",
                "source_event_index": int(event["index"]),
            }
            output_event = {
                    "beat": frac_text(beat),
                    "duration": whole_fraction_from_slots(chunk),
                    "source": event_source,
                    "notes": notes if first_chunk else [],
                    "confidence": 1.0,
                }
            if first_chunk:
                beat_effects = effect_for(
                    techniques, system["file"], int(event["index"]), 0
                )
                if beat_effects:
                    output_event["effects"] = beat_effects
            if first_chunk and int(event["index"]) in chord_by_event:
                output_event["chord"] = chord_by_event[int(event["index"])]
            output_events.append(output_event)
            first_chunk = False
            beat += chunk / 2
    if beat != 4:
        raise AssertionError(f"measure {measure_number} assembled to {beat} quarter notes")

    left, right = (0.06, 0.50) if measure_in_system == 1 else (0.50, 0.93)
    return {
        "number": measure_number,
        "time_signature": [4, 4],
        "source": {
            "page": system.get("page", system["file"].split(".")[0]),
            "system": system.get("page", system["file"].split(".")[0]),
            "timestamp_seconds": timestamp,
            "bbox": [left, y0, right - left, y1 - y0],
            "file": system["file"],
        },
        "events": output_events,
    }


def timestamp_map(manifest: dict) -> dict[str, float]:
    if "systems" in manifest:
        return {item["file"]: float(item.get("representative_frame", 0)) for item in manifest["systems"]}
    kept = {item["page_file"]: float(item["timestamp_seconds"]) for item in manifest["curation"]["kept"]}
    return {
        item["selected_file"]: kept[item["file"]]
        for item in manifest["system_selection"]["selected"]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--corrections", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--insertions", type=Path)
    parser.add_argument("--chords", type=Path)
    parser.add_argument("--techniques", type=Path)
    parser.add_argument("--system-prefix")
    parser.add_argument("--title", default="Video TAB transcription")
    parser.add_argument("--artist", default="")
    parser.add_argument("--source-uploader", default="")
    parser.add_argument(
        "--instrument",
        choices=("acoustic_guitar", "electric_guitar", "piano"),
        default="acoustic_guitar",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candidate_data = json.loads(args.candidates.read_text())
    correction_data = json.loads(args.corrections.read_text())
    manifest = json.loads(args.manifest.read_text())
    corrections_by_system: dict[str, list[dict]] = {}
    for operation in correction_data["operations"]:
        corrections_by_system.setdefault(operation["system"], []).append(operation)
    timestamps = timestamp_map(manifest)
    chord_data = json.loads(args.chords.read_text()) if args.chords else {"systems": {}}
    technique_data = json.loads(args.techniques.read_text()) if args.techniques else {"systems": {}}
    systems = list(candidate_data["systems"])
    if args.system_prefix:
        systems = [system for system in systems if system["file"].startswith(args.system_prefix)]
    if args.insertions:
        insertion_data = json.loads(args.insertions.read_text())
        for insertion in insertion_data.get("insertions", []):
            position = next(i for i, system in enumerate(systems) if system["file"] == insertion["after_system"])
            systems.insert(position + 1, insertion["system"])

    measures: list[dict] = []
    correction_count = 0
    for system in systems:
        operations = corrections_by_system.get(system["file"], [])
        correction_count += len(operations)
        events = apply_corrections(system, operations)
        first = [event for event in events if float(event["x"]) < 0.5]
        second = [event for event in events if float(event["x"]) >= 0.5]
        measure_parts = [first] + ([second] if second else [])
        if not first:
            raise ValueError(f"{system['file']}: first measure is empty")
        for measure_in_system, measure_events in enumerate(measure_parts, start=1):
            measures.append(
                build_measure(
                    system,
                    measure_events,
                    len(measures) + 1,
                    measure_in_system,
                    float(system.get("timestamp_seconds", timestamps.get(system["file"], 0))),
                    chord_data.get("systems", {}).get(system["file"], []),
                    technique_data.get("systems", {}),
                )
            )

    result = {
        "version": 1,
        "metadata": {
            "title": args.title,
            "artist": args.artist,
            "source_uploader": args.source_uploader,
            "project_credit": "video-2-guitar-score skill project",
            "show_chord_diagrams": False,
            "source": {
                "video": Path(manifest.get("source_video", "BV1vyLR6REJU.mp4")).name,
                "url": "https://www.bilibili.com/video/BV1vyLR6REJU",
            },
            "instrument": args.instrument,
            "tuning_midi": TUNING_LOW_TO_HIGH,
            "capo": 2,
            "tempo_bpm": 77,
            "authority": "displayed_video_tab",
            "systems": len(systems),
            "manual_corrections_applied": correction_count,
            "rhythm_reconstruction": "TAB rhythm-stem attack spacing quantized to eighths and 16th-note triplets",
        },
        "measures": measures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    notes = sum(len(event["notes"]) for measure in measures for event in measure["events"])
    print(f"Wrote {len(measures)} measures and {notes} visually sourced notes to {args.output}")


if __name__ == "__main__":
    main()
