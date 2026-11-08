#!/usr/bin/env python3
"""Validate rhythm, visual provenance, and guitar fingering invariants."""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("standard", "strict"), help="review mode; defaults to metadata.review_mode or standard")
    parser.add_argument("--allow-draft", action="store_true", help="downgrade inferred or missing visual provenance to warnings")
    args = parser.parse_args()
    score = json.loads(args.score.read_text())
    mode = args.mode or score.get("metadata", {}).get("review_mode", "standard")
    if mode not in {"standard", "strict"}:
        parser.error("review mode must be standard or strict")
    tuning = score.get("metadata", {}).get("tuning_midi", [])
    capo = int(score.get("metadata", {}).get("capo", 0))
    errors: list[str] = []
    warnings: list[str] = []
    if len(tuning) != 6 or any(not isinstance(pitch, int) for pitch in tuning):
        errors.append("metadata.tuning_midi must contain six integer open-string MIDI pitches, low to high.")
    measures = score.get("measures", [])
    previous_number: int | None = None
    for index, measure in enumerate(measures, start=1):
        label = f"Measure {measure.get('number', index)}"
        measure_needs_review = False
        try:
            measure_number = int(measure.get("number", index))
            if previous_number is not None and measure_number != previous_number + 1:
                errors.append(f"{label}: measure numbering is not consecutive after {previous_number}.")
            previous_number = measure_number
        except (TypeError, ValueError):
            errors.append(f"{label}: invalid measure number.")
        measure_source = measure.get("source", {})
        if not all(key in measure_source for key in ("page", "timestamp_seconds", "bbox")):
            measure_needs_review = True
            (warnings if args.allow_draft else errors).append(f"{label}: missing page/timestamp/bbox visual provenance.")
        try:
            numerator, denominator = measure["time_signature"]
            measure_length = Fraction(4 * int(numerator), int(denominator))
        except (KeyError, ValueError, ZeroDivisionError):
            errors.append(f"{label}: invalid time_signature.")
            continue
        latest = Fraction(0)
        for event_index, event in enumerate(measure.get("events", []), start=1):
            event_source = event.get("source", {})
            source_problem = (
                "bbox" not in event_source
                or event_source.get("method") != "visual"
                or event_source.get("status") != "verified"
            )
            if source_problem:
                measure_needs_review = True
                (warnings if args.allow_draft else errors).append(
                    f"{label}, event {event_index}: missing verified visual event provenance."
                )
            try:
                start = Fraction(str(event["beat"]))
                duration = Fraction(int(event["duration"][0]) * 4, int(event["duration"][1]))
            except (KeyError, ValueError, ZeroDivisionError):
                errors.append(f"{label}, event {event_index}: invalid beat or duration.")
                continue
            if start < latest:
                errors.append(f"{label}, event {event_index}: overlaps the preceding event.")
            if start + duration > measure_length:
                errors.append(f"{label}, event {event_index}: extends beyond {numerator}/{denominator}.")
            latest = max(latest, start + duration)
            used_strings: set[int] = set()
            for note in event.get("notes", []):
                try:
                    string, fret = int(note["string"]), int(note["fret"])
                except (KeyError, ValueError):
                    errors.append(f"{label}, event {event_index}: note is missing string or fret.")
                    continue
                if not 1 <= string <= 6 or fret < 0:
                    errors.append(f"{label}, event {event_index}: invalid string/fret {string}/{fret}.")
                if string in used_strings:
                    errors.append(f"{label}, event {event_index}: more than one note on string {string}.")
                used_strings.add(string)
                expected = tuning[6 - string] + fret + capo if len(tuning) == 6 else None
                note_source = note.get("source", {})
                note_source_problem = (
                    "bbox" not in note_source
                    or note_source.get("method") != "visual"
                    or note_source.get("status") != "verified"
                )
                if note_source_problem:
                    measure_needs_review = True
                    (warnings if args.allow_draft else errors).append(
                        f"{label}, event {event_index}: string/fret {string}/{fret} lacks verified TAB-pixel provenance."
                    )
                if "pitch_midi" in note and expected is not None and int(note["pitch_midi"]) != expected:
                    errors.append(f"{label}, event {event_index}: pitch_midi disagrees with string/fret ({note['pitch_midi']} vs {expected}).")
                if float(note.get("confidence", event.get("confidence", 1))) < 0.9:
                    measure_needs_review = True
                    warnings.append(f"{label}, event {event_index}: low-confidence notation needs image review.")
        if latest < measure_length:
            measure_needs_review = True
            warnings.append(f"{label}: rhythm is incomplete by {measure_length - latest} quarter-note units (may be an intentional rest).")
        review = measure.get("review", {})
        review_status = review.get("status", "unreviewed")
        if mode == "strict" and review_status != "user_confirmed":
            errors.append(f"{label}: strict mode requires recorded user confirmation.")
        elif mode == "standard":
            if review_status not in {"machine_passed", "user_confirmed"}:
                errors.append(f"{label}: standard mode requires machine_passed or user_confirmed review status.")
            elif measure_needs_review and review_status != "user_confirmed":
                errors.append(f"{label}: flagged ambiguity requires recorded user confirmation in standard mode.")
        if review_status == "user_confirmed" and not review.get("decision_id"):
            errors.append(f"{label}: user_confirmed review is missing decision_id.")
    lines = ["# Score validation report", "", f"- Review mode: {mode}", f"- Measures: {len(measures)}", f"- Errors: {len(errors)}", f"- Warnings: {len(warnings)}", "", "## Errors"]
    lines.extend([f"- {item}" for item in errors] or ["- None"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {item}" for item in warnings] or ["- None"])
    args.report.write_text("\n".join(lines) + "\n")
    print(f"Validation report written to {args.report}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
