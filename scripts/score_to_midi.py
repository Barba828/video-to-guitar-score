#!/usr/bin/env python3
"""Export validated canonical score JSON to a basic Standard MIDI File (format 0)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TPQ = 480


def varlen(value: int) -> bytes:
    encoded = [value & 0x7F]
    while value > 0x7F:
        value >>= 7
        encoded.append((value & 0x7F) | 0x80)
    return bytes(reversed(encoded))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.score.read_text())
    meta = data["metadata"]
    tuning = meta.get("tuning_midi", [40, 45, 50, 55, 59, 64])
    capo = int(meta.get("capo", 0))
    tempo = int(meta.get("tempo_bpm", 120))
    events: list[tuple[int, int, int, int]] = []  # tick, kind(0 off/1 on), pitch, velocity
    cursor = 0
    for measure in data["measures"]:
        numerator, denominator = measure["time_signature"]
        measure_ticks = TPQ * 4 * numerator // denominator
        for event in measure.get("events", []):
            start = cursor + round(float(event["beat"]) * TPQ)
            duration = event["duration"]
            duration_ticks = TPQ * 4 * int(duration[0]) // int(duration[1])
            for note in event.get("notes", []):
                pitch = note.get("pitch_midi")
                if pitch is None:
                    string = int(note["string"])
                    pitch = tuning[6 - string] + int(note["fret"]) + capo
                pitch = int(pitch)
                if not 0 <= pitch <= 127:
                    raise ValueError(f"invalid MIDI pitch: {pitch}")
                events.extend([(start, 1, pitch, 96), (start + duration_ticks, 0, pitch, 0)])
        cursor += measure_ticks
    events.sort(key=lambda item: (item[0], item[1]))  # note-offs before note-ons
    track = bytearray(b"\x00\xff\x51\x03" + round(60_000_000 / tempo).to_bytes(3, "big"))
    track.extend(b"\x00\xc0\x18")  # nylon guitar, General MIDI program 25 (zero based 24)
    last = 0
    for tick, kind, pitch, velocity in events:
        track.extend(varlen(tick - last)); last = tick
        track.extend(bytes([0x80 if kind == 0 else 0x90, pitch, velocity]))
    track.extend(b"\x00\xff\x2f\x00")
    midi = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + TPQ.to_bytes(2, "big")
    args.output.write_bytes(midi + b"MTrk" + len(track).to_bytes(4, "big") + track)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
