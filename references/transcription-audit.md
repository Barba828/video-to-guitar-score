# Source transcription and regression audit

Use this audit before assigning `machine_passed`, after every correction, and before calling a Guitar Pro file final. It separates three different claims that must never be conflated.

## Three validation layers

1. **Source-transcription correctness:** the ledger matches the displayed score pixels measure by measure.
2. **Score-structure correctness:** durations, pitches, measure order, ties, and metadata are internally legal and consistent.
3. **Native-file consistency:** reopening and rendering the Guitar Pro file preserves the ledger.

A pass at layer 2 or 3 says nothing about whether the original pixels were transcribed correctly. Report results by layer, for example: “18/18 measures source-compared; structural validator: 0 errors; GP5 round trip: 0 differences.” Do not shorten this to “the score is correct” unless all required source comparisons passed.

## Occurrence-level transcription

Treat every printed occurrence as independent evidence, even when it resembles an earlier chord or rhythm.

- Establish the six TAB-line coordinates for each system before reading digits. Number them top-to-bottom as strings 1–6.
- For every event, record the digits on each occupied line. Check open bass notes separately; never assume string 5 or 6 from a reusable chord name or shape.
- Reuse a chord/rhythm helper only as a writing convenience after each occurrence has its own verified bounding box and matches every string, fret, duration, and technique. A helper must not become the evidence.
- Read rhythm left-to-right from stems, flags, beams, dots, tuplets, and rests. The measure-total check is only a later invariant.
- Distinguish patterns that have the same total duration, such as `8+16+16+4` and `4+8+16+16`.
- Inspect both sides of every barline for ties, held notes, repeats, and pickup/ending behavior. Encode a tied destination as tied, not newly attacked.
- Inventory visible techniques independently: hammer-on, pull-off, slide, bend, harmonic, arpeggio, strum direction, dead note, let-ring, and any text marking. Do not add a plausible technique without a visible glyph.
- Use audio only to flag a possible pitch/timing anomaly. It cannot override visible string/fret evidence.

For each measure, `source-comparison-report.md` must state the source crop/timestamp and the result for:

```text
event count | string/fret | rhythm sequence | rests | ties across barlines |
techniques | chord text/voicing | pass/needs-review/blocking
```

Do not set `review.status: machine_passed` merely because `validate_score.py` succeeded. Set it only after the measure has been visually compared with its source crop and has no unresolved field above.

## Correction and regression control

When the user corrects a note, rhythm, or technique:

1. Change only the cited occurrence first.
2. Search for similar occurrences, but modify each one only after independently confirming it in its own source region.
3. Regenerate the native file and create `revision-diff.json` containing every changed musical event, including measure, beat, before, after, reason, and source region.
4. Any changed event not explained by the requested correction or an independently verified source finding is Blocking.
5. Recheck the corrected measure, both neighboring measures, every cross-bar relation touching it, and all measures intentionally changed through a confirmed repeated pattern.
6. Re-run whole-score structural validation and native round-trip validation.

Never fix an occurrence by changing a shared helper globally unless the revision diff proves that every affected occurrence was source-verified. Prefer explicit per-measure data when similar-looking passages differ.

## Publication wording

Use precise claims:

- “Source comparison passed for 18/18 measures” means layer 1 passed.
- “Structural validation found 0 errors” means layer 2 passed.
- “GP5 round trip found 0 differences” means layer 3 passed.

If layer 1 is incomplete, label the file candidate/draft even when layers 2 and 3 pass. Do not present internal consistency as transcription accuracy.
