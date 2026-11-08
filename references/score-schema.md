# Canonical score schema

`score.json` is the editable transcription ledger of the score pixels. The displayed TAB remains the authority; every event in this file must preserve enough visual provenance to audit its string, fret, rhythm, and technique. Exporters must not re-infer guitar fingering from pitch.

```json
{
  "version": 1,
  "metadata": {
    "title": "",
    "artist": "",
    "arranger": "",
    "source_uploader": "",
    "project_credit": "video-2-guitar-score skill project",
    "source": {"video": "source.mp4", "url": null},
    "instrument": "acoustic_guitar",
    "show_chord_diagrams": false,
    "tuning_midi": [40, 45, 50, 55, 59, 64],
    "capo": 0,
    "tempo_bpm": 120,
    "review_mode": "standard"
  },
  "measures": [
    {
      "number": 1,
      "time_signature": [4, 4],
      "source": {"page": 1, "system": 1, "timestamp_seconds": 12.4, "bbox": [0.1, 0.2, 0.8, 0.1]},
      "review": {"status": "machine_passed", "decision_id": null},
      "events": [
        {
          "beat": 0,
          "duration": [1, 4],
          "source": {"bbox": [0.21, 0.63, 0.025, 0.14], "method": "visual", "status": "verified"},
          "notes": [
            {"string": 1, "fret": 3, "pitch_midi": 67, "source": {"bbox": [0.215, 0.635, 0.012, 0.025], "method": "visual", "status": "verified"}}
          ],
          "confidence": 0.98
        }
      ]
    }
  ]
}
```

String numbering is conventional guitar TAB numbering: `1` is the highest-pitched string; `6` is the lowest. `tuning_midi` is ordered low to high (string 6 through string 1). `bbox` is normalized `[x, y, width, height]` on the cited cleaned page/system. A final export requires it for every event and note. If the source is unavailable or unreadable, set `method: "inferred"`, `status: "needs_review"`; such an event blocks a final Guitar Pro export.

`metadata.review_mode` is `standard` or `strict`. In standard mode, a measure may remain `machine_passed` when it has no flagged ambiguity; a flagged measure must become `user_confirmed` after review. In strict mode, every measure must be `user_confirmed` before final publication. `decision_id` links to the corresponding entry in `review-decisions.json`; keep corrections and confirmations append-only so later revisions remain auditable.

Keep composer/artist, arranger/tab author, and source uploader as separate metadata roles. Preserve the title's source language. `show_chord_diagrams` defaults to `false`; when enabled, deduplicate the top diagram list by normalized chord name while retaining chord names at every musical occurrence. Preserve multiple same-name voicings only when the source explicitly distinguishes them and the user requests both. `instrument` controls the native playback sound and must come from explicit video/notation evidence or a user choice.

## Required validation

- Every event duration must fit the measure time signature; count rests too.
- `pitch_midi` must equal the open-string pitch for `string` plus `fret`, capo included.
- `string` and `fret` must be visually observed from the cited TAB region. Pitch/audio may validate the result but may not select or replace them.
- Fret numbers must be non-negative and practical unless explicitly marked as a special technique.
- Chords may contain one note per string only.
- Validate each measure against its cited image region. Use `confidence < 0.9` or `status: "needs_review"` for ambiguous digits, rhythm flags, ties, repeats, and techniques.

## Interchange mapping

- **MIDI:** stores timing, pitch, tempo, and velocity; it cannot faithfully retain page layout or every guitar technique.
- **MusicXML:** optional interchange format. Write explicit string/fret technical markings and round-trip-test them before relying on an importer.
- **Guitar Pro:** primary editable target. Target a known version through a tested exporter and verify every measure after reopening the native file. Preserve `score.json` and cited page images beside it for auditing.
