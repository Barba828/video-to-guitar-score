#!/usr/bin/env python3
"""Reopen a GP5 file and compare its musical content with the verified score ledger."""
from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

import guitarpro
from guitarpro import models as gp


def expected_duration(value: list[int]) -> Fraction:
    return Fraction(int(value[0]), int(value[1]))


def gp_duration(duration: gp.Duration) -> Fraction:
    return Fraction(int(duration.time), gp.Duration.quarterTime * 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("gp5", type=Path)
    parser.add_argument("--encoding", default="cp1252")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.score.read_text())
    song = guitarpro.parse(args.gp5, encoding=args.encoding)
    track = song.tracks[0]
    errors: list[str] = []

    metadata = source["metadata"]
    if song.title != metadata.get("title", ""):
        errors.append(f"title differs: {song.title!r} != {metadata.get('title', '')!r}")
    if int(song.tempo) != int(metadata.get("tempo_bpm", 120)):
        errors.append(f"tempo differs: {song.tempo} != {metadata.get('tempo_bpm')}")
    if int(track.offset) != int(metadata.get("capo", 0)):
        errors.append(f"capo differs: {track.offset} != {metadata.get('capo', 0)}")
    expected_tuning = [int(value) for value in metadata.get("tuning_midi", [])]
    actual_tuning = [string.value for string in reversed(track.strings)]
    if actual_tuning != expected_tuning:
        errors.append(f"tuning differs: {actual_tuning} != {expected_tuning}")

    source_measures = source.get("measures", [])
    if len(track.measures) != len(source_measures):
        errors.append(f"measure count differs: {len(track.measures)} != {len(source_measures)}")

    for index, (expected_measure, actual_measure) in enumerate(
        zip(source_measures, track.measures), start=1
    ):
        number = int(expected_measure.get("number", index))
        if actual_measure.header.number != number:
            errors.append(
                f"measure {number}: reopened number is {actual_measure.header.number}"
            )
        expected_signature = tuple(map(int, expected_measure["time_signature"]))
        actual_signature = (
            int(actual_measure.header.timeSignature.numerator),
            int(actual_measure.header.timeSignature.denominator.value),
        )
        if actual_signature != expected_signature:
            errors.append(
                f"measure {number}: time signature differs: {actual_signature} != {expected_signature}"
            )
        expected_events = expected_measure.get("events", [])
        actual_beats = actual_measure.voices[0].beats
        if len(actual_beats) != len(expected_events):
            errors.append(
                f"measure {number}: event count differs: {len(actual_beats)} != {len(expected_events)}"
            )
        for event_index, (expected_event, actual_beat) in enumerate(
            zip(expected_events, actual_beats), start=1
        ):
            if gp_duration(actual_beat.duration) != expected_duration(expected_event["duration"]):
                errors.append(
                    f"measure {number}, event {event_index}: duration differs: "
                    f"{gp_duration(actual_beat.duration)} != {expected_duration(expected_event['duration'])}"
                )
            expected_text = expected_event.get("chord_name")
            actual_text = actual_beat.text or None
            if actual_text != expected_text:
                errors.append(
                    f"measure {number}, event {event_index}: chord text differs: {actual_text!r} != {expected_text!r}"
                )
            expected_arpeggio = "arpeggio_up" in expected_event.get("effects", [])
            actual_arpeggio = actual_beat.effect.stroke.direction == gp.BeatStrokeDirection.up
            if actual_arpeggio != expected_arpeggio:
                errors.append(
                    f"measure {number}, event {event_index}: arpeggio differs: {actual_arpeggio} != {expected_arpeggio}"
                )
            expected_effects = set(expected_event.get("effects", []))
            expected_pick = gp.BeatStrokeDirection.none
            if "strum_down" in expected_effects:
                expected_pick = gp.BeatStrokeDirection.down
            elif "strum_up" in expected_effects:
                expected_pick = gp.BeatStrokeDirection.up
            if actual_beat.effect.pickStroke != expected_pick:
                errors.append(
                    f"measure {number}, event {event_index}: pick direction differs: "
                    f"{actual_beat.effect.pickStroke} != {expected_pick}"
                )
            expected_notes = sorted(expected_event.get("notes", []), key=lambda item: int(item["string"]))
            actual_notes = sorted(actual_beat.notes, key=lambda item: int(item.string))
            if len(actual_notes) != len(expected_notes):
                errors.append(
                    f"measure {number}, event {event_index}: note count differs: {len(actual_notes)} != {len(expected_notes)}"
                )
            for expected_note, actual_note in zip(expected_notes, actual_notes):
                expected_pair = (int(expected_note["string"]), int(expected_note["fret"]))
                actual_pair = (int(actual_note.string), int(actual_note.value))
                if actual_pair != expected_pair:
                    errors.append(
                        f"measure {number}, event {event_index}: string/fret differs: {actual_pair} != {expected_pair}"
                    )
                effects = set(expected_note.get("effects", []))
                expected_tie = "tie_from_previous" in effects
                if (actual_note.type == gp.NoteType.tie) != expected_tie:
                    errors.append(
                        f"measure {number}, event {event_index}, string {expected_pair[0]}: tie differs"
                    )
                expected_dead = "dead_note" in effects
                if (actual_note.type == gp.NoteType.dead) != expected_dead:
                    errors.append(
                        f"measure {number}, event {event_index}, string {expected_pair[0]}: dead-note type differs"
                    )
                expected_hammer = "hammer_or_pull_to_next" in effects
                if bool(actual_note.effect.hammer) != expected_hammer:
                    errors.append(
                        f"measure {number}, event {event_index}, string {expected_pair[0]}: hammer differs"
                    )

    lines = [
        "# Guitar Pro round-trip report",
        "",
        f"- File: {args.gp5.name}",
        f"- Measures compared: {min(len(track.measures), len(source_measures))}",
        f"- Errors: {len(errors)}",
        "",
        "## Errors",
    ]
    lines.extend([f"- {item}" for item in errors] or ["- None"])
    args.report.write_text("\n".join(lines) + "\n")
    print(f"Round-trip report written to {args.report}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
