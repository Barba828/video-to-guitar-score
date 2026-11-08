#!/usr/bin/env python3
"""Export validated canonical score JSON to a basic MusicXML 4.0 guitar part."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

DIVISIONS = 480
PITCH_NAMES = [("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0),
               ("F", 1), ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0)]


def element(parent: ET.Element, name: str, text: object | None = None, **attrs: str) -> ET.Element:
    child = ET.SubElement(parent, name, {key: str(value) for key, value in attrs.items()})
    if text is not None:
        child.text = str(text)
    return child


def add_note(parent: ET.Element, note: dict, duration: int, chord: bool = False) -> None:
    out = element(parent, "note")
    if chord:
        element(out, "chord")
    if not note:
        element(out, "rest")
    else:
        midi = int(note.get("pitch_midi", 0))
        if not 0 <= midi <= 127:
            raise ValueError(f"invalid MIDI pitch: {midi}")
        step, alter = PITCH_NAMES[midi % 12]
        pitch = element(out, "pitch")
        element(pitch, "step", step)
        if alter:
            element(pitch, "alter", alter)
        element(pitch, "octave", midi // 12 - 1)
    element(out, "duration", duration)
    element(out, "voice", 1)
    element(out, "type", "quarter")
    if note and "string" in note and "fret" in note:
        notation = element(out, "notations")
        technical = element(notation, "technical")
        element(technical, "string", note["string"])
        element(technical, "fret", note["fret"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.score.read_text())
    metadata = data["metadata"]
    root = ET.Element("score-partwise", version="4.0")
    title = metadata.get("title")
    if title:
        work = element(root, "work"); element(work, "work-title", title)
    part_list = element(root, "part-list")
    score_part = element(part_list, "score-part", id="P1")
    element(score_part, "part-name", "Guitar")
    part = element(root, "part", id="P1")
    for index, source_measure in enumerate(data["measures"], start=1):
        measure = element(part, "measure", number=source_measure.get("number", index))
        numerator, denominator = source_measure["time_signature"]
        if index == 1:
            attributes = element(measure, "attributes")
            element(attributes, "divisions", DIVISIONS)
            time = element(attributes, "time")
            element(time, "beats", numerator); element(time, "beat-type", denominator)
            clef = element(attributes, "clef")
            element(clef, "sign", "G"); element(clef, "line", 2); element(clef, "clef-octave-change", -1)
            direction = element(measure, "direction", placement="above")
            sound = element(direction, "sound", tempo=str(metadata.get("tempo_bpm", 120)))
        for event in source_measure.get("events", []):
            duration = DIVISIONS * 4 * int(event["duration"][0]) // int(event["duration"][1])
            notes = event.get("notes", [])
            if not notes:
                add_note(measure, {}, duration)
            for note_index, note in enumerate(notes):
                add_note(measure, note, duration, chord=note_index > 0)
    ET.indent(root, space="  ")
    args.output.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8"))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
