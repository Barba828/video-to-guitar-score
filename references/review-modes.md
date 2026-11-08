# Review modes and publication gates

Use the same extraction, provenance, and full-score machine validation in both modes. A mode controls the user-review burden; it never permits sampling the score or inventing unreadable notation.

## Finding states

- **Passed:** visual provenance exists and all structural, fingering, rhythm, technique, and round-trip checks agree.
- **Needs review:** the source is ambiguous, confidence is low, two checks disagree, or a symbol may have been lost during Guitar Pro writing or reopening.
- **Blocking:** provenance is missing, a measure is incomplete, string/fret or duration is invalid, an observed symbol is absent after round-trip, or an unobserved technique was added.

Techniques such as hammer-on, pull-off, slide, bend, harmonic, tremolo, and arpeggio require explicit visual evidence. Musical plausibility is not evidence. Record the relation between its endpoints, not only the displayed letter or glyph.

## Standard mode

1. Validate every measure against its cited source region.
2. Reopen the generated Guitar Pro file and compare measure count, timing, string/fret, chord labels, and techniques with `score.json`.
3. Render the reopened file and compare every measure with the source. Layout differences are allowed; musical-content differences are not.
4. Show the user only measures marked Needs review or Blocking, with the source crop, rendered crop, and a concise difference description.
5. Record each user correction or confirmation in `review-decisions.json` and update the affected measure to `user_confirmed`.

Publication requires zero Blocking findings. Measures without findings may remain `machine_passed`; every flagged measure must be `user_confirmed`.

## Strict mode

Perform every standard-mode check, then generate `review-booklet.pdf` containing every measure in score order:

- source video crop and timestamp;
- Guitar Pro render of the same measure;
- extracted string/fret and rhythm summary;
- chord label and every technique relation;
- Passed, Needs review, or Blocking status;
- a stable measure/revision identifier used by `review-decisions.json`.

Require an explicit user confirmation or correction for every measure. Mark each accepted measure `user_confirmed` with a `decision_id`. Until all measures are confirmed and validation has zero errors, use `candidate` in the filename and do not call the Guitar Pro file final.

## Correction and regression rules

After any correction:

1. Follow the occurrence-level correction and three-layer regression gates in [transcription-audit.md](transcription-audit.md).
2. Regenerate and reopen the Guitar Pro file.
3. Revalidate the changed measure, its immediate neighbors, and every cross-bar relation touching it.
4. Re-run whole-score invariants: measure count/order, total duration, per-measure duration, technique inventory, chord inventory, metadata, and instrument/tuning.
5. Produce `revision-diff.json` listing intended changes and every other changed musical event. Any unexplained change is Blocking.
6. In strict mode, invalidate confirmations only for measures whose musical content or relevant rendering changed; retain unaffected confirmations with their revision identifiers.

## `review-decisions.json`

Store append-only decisions with at least:

```json
{
  "decision_id": "m020-r3-001",
  "measure": 20,
  "revision": 3,
  "decision": "confirmed",
  "note": "Confirmed string 4 fret 0 hammer-on to fret 2.",
  "timestamp": "2026-11-07T15:00:00+08:00"
}
```

Use `decision: corrected` when the user supplies a change, and preserve the prior entry rather than overwriting it.
