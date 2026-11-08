#!/usr/bin/env python3
"""Write verified pixel-anchored score JSON directly to Guitar Pro 5.

Requires PyGuitarPro. String and fret values are copied verbatim from the
verified transcription ledger; pitch-only data is never used to choose a
fingering. Guitar Pro 8 can open the resulting native .gp5 file.
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

import guitarpro
from guitarpro import models as gp


def duration_from_fraction(value: list[int]) -> gp.Duration:
    numerator, denominator = map(int, value)
    fraction = Fraction(numerator, denominator)
    for candidate in (1, 2, 4, 8, 16, 32, 64, 128):
        if fraction == Fraction(1, candidate):
            return gp.Duration(value=candidate)
        if fraction == Fraction(3, candidate * 2):
            return gp.Duration(value=candidate, isDotted=True)
    return gp.Duration.fromTime(int(fraction * gp.Duration.quarterTime * 4))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--track-name", default=None)
    parser.add_argument("--show-chord-diagrams", action="store_true")
    parser.add_argument("--encoding", default="cp1252")
    args = parser.parse_args()

    data = json.loads(args.score.read_text())
    metadata = data["metadata"]
    measures = data["measures"]
    if not measures:
        raise SystemExit("score contains no measures")

    song = gp.Song(versionTuple=(5, 1, 0))
    song.title = args.title or metadata.get("title", "Video TAB OCR")
    song.subtitle = "video-2-guitar-score skill project"
    song.artist = metadata.get("artist", "")
    song.music = metadata.get("artist", "")
    song.tab = "video-2-guitar-score skill project"
    song.copyright = metadata.get("source", {}).get("url", "")
    source_uploader = metadata.get("source_uploader", "")
    song.instructions = f"视频来源 / Source uploader: {source_uploader}" if source_uploader else ""
    song.tempoName = "Moderate"
    song.tempo = int(metadata.get("tempo_bpm", 120))
    key_names = {
        "C": gp.KeySignature.CMajor,
        "G": gp.KeySignature.GMajor,
        "D": gp.KeySignature.DMajor,
        "A": gp.KeySignature.AMajor,
        "E": gp.KeySignature.EMajor,
        "F": gp.KeySignature.FMajor,
        "Am": gp.KeySignature.AMinor,
        "Em": gp.KeySignature.EMinor,
        "Dm": gp.KeySignature.DMinor,
    }
    song.key = key_names.get(str(metadata.get("key", "C")), gp.KeySignature.CMajor)
    song.notice = [
        "String and fret values were transcribed from the displayed TAB.",
        "This file does not use MIDI or audio-derived fingering.",
    ]
    if source_uploader:
        song.notice.append(f"Source uploader: {source_uploader}")

    while len(song.measureHeaders) < len(measures):
        song.newMeasure()
    if len(song.measureHeaders) > len(measures):
        song.measureHeaders = song.measureHeaders[: len(measures)]
        for track in song.tracks:
            track.measures = track.measures[: len(measures)]

    track = song.tracks[0]
    instrument = metadata.get("instrument", "acoustic_guitar")
    instrument_names = {
        "acoustic_guitar": "Acoustic Guitar (steel)",
        "electric_guitar": "Electric Guitar (clean)",
        "piano": "Acoustic Grand Piano",
    }
    instrument_programs = {
        "acoustic_guitar": 25,
        "electric_guitar": 27,
        "piano": 0,
    }
    track.name = args.track_name or instrument_names.get(instrument, "Instrument")
    track.offset = int(metadata.get("capo", 0))
    track.indicateTuning = True
    track.settings.notation = True
    track.settings.tablature = True
    track.settings.showRhythm = True
    track.settings.diagramList = bool(args.show_chord_diagrams)
    track.settings.diagramsInScore = False
    track.settings.diagramsAreBelow = False
    track.channel.instrument = instrument_programs.get(instrument, 25)
    tuning = metadata.get("tuning_midi", [40, 45, 50, 55, 59, 64])
    if len(tuning) != 6:
        raise SystemExit("metadata.tuning_midi must contain six pitches")
    track.strings = [gp.GuitarString(number, int(tuning[6 - number])) for number in range(1, 7)]

    previous_end = gp.Duration.quarterTime
    seen_chord_diagrams: set[str] = set()
    for index, (source_measure, header, measure) in enumerate(
        zip(measures, song.measureHeaders, track.measures), start=1
    ):
        numerator, denominator = map(int, source_measure["time_signature"])
        header.number = int(source_measure.get("number", index))
        header.start = previous_end
        header.timeSignature = gp.TimeSignature(
            numerator=numerator,
            denominator=gp.Duration(value=denominator),
        )
        previous_end = header.end
        voice = measure.voices[0]
        voice.beats.clear()
        expected_beat = Fraction(0)
        for event_index, event in enumerate(source_measure.get("events", []), start=1):
            beat_position = Fraction(str(event["beat"]))
            if beat_position != expected_beat:
                raise ValueError(
                    f"measure {header.number}, event {event_index}: non-contiguous rhythm "
                    f"({beat_position} != {expected_beat}); add explicit rests before GP export"
                )
            duration = duration_from_fraction(event["duration"])
            beat = gp.Beat(voice=voice, duration=duration, status=gp.BeatStatus.normal)
            if event_index == 1 and source_measure.get("chord"):
                beat.text = str(source_measure["chord"])
            if event.get("chord_name"):
                beat.text = str(event["chord_name"])
            if event.get("chord"):
                source_chord = event["chord"]
                beat.text = str(source_chord["name"])
                chord = gp.Chord(length=6)
                chord.name = str(source_chord["name"])
                chord.strings = [int(value) for value in source_chord["strings"]]
                chord.firstFret = int(source_chord.get("first_fret", 1))
                chord.sharp = True
                chord.newFormat = True
                chord.show = True
                chord_signature = chord.name.strip().casefold()
                if chord_signature not in seen_chord_diagrams:
                    beat.effect.chord = chord
                    seen_chord_diagrams.add(chord_signature)
            beat_effects = set(event.get("effects", []))
            if "arpeggio_up" in beat_effects:
                beat.effect.stroke = gp.BeatStroke(
                    gp.BeatStrokeDirection.up, gp.Duration.sixteenth
                )
            if "arpeggio_down" in beat_effects:
                beat.effect.stroke = gp.BeatStroke(
                    gp.BeatStrokeDirection.down, gp.Duration.sixteenth
                )
            if "strum_down" in beat_effects:
                beat.effect.pickStroke = gp.BeatStrokeDirection.down
            if "strum_up" in beat_effects:
                beat.effect.pickStroke = gp.BeatStrokeDirection.up
            for source_note in event.get("notes", []):
                provenance = source_note.get("source", {})
                if provenance.get("method") != "visual" or provenance.get("status") != "verified":
                    raise ValueError(
                        f"measure {header.number}, event {event_index}: refusing unverified fingering"
                    )
                effects = set(source_note.get("effects", []))
                note_type = gp.NoteType.normal
                if "dead_note" in effects:
                    note_type = gp.NoteType.dead
                elif "tie_from_previous" in effects:
                    note_type = gp.NoteType.tie
                note = gp.Note(
                    beat=beat,
                    value=int(source_note["fret"]),
                    string=int(source_note["string"]),
                    velocity=gp.Velocities.default,
                    type=note_type,
                )
                if "hammer_or_pull_to_next" in effects:
                    note.effect.hammer = True
                if "shift_slide_to_next" in effects:
                    note.effect.slides.append(gp.SlideType.shiftSlideTo)
                beat.notes.append(note)
            if not beat.notes:
                beat.status = gp.BeatStatus.rest
            voice.beats.append(beat)
            expected_beat += Fraction(int(event["duration"][0]) * 4, int(event["duration"][1]))
        measure_length = Fraction(4 * numerator, denominator)
        if expected_beat != measure_length:
            raise ValueError(
                f"measure {header.number}: duration is {expected_beat} quarter notes, expected {measure_length}"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    guitarpro.write(song, args.output, version=(5, 1, 0), encoding=args.encoding)
    print(f"Wrote native Guitar Pro 5 score: {args.output}")


if __name__ == "__main__":
    main()
