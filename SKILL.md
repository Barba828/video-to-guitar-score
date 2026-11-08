---
name: video-to-guitar-score
description: OCR/OMR guitar TAB or notation visibly shown in an authorized video, preserve the displayed string/fret fingering in a native Guitar Pro score, and engrave new IMG/PDF pages with optional synchronized MIDI or MusicXML derivatives. Use for tutorial and play-through videos that display the score; do not use this for transcription from performance audio alone.
---

# Video to Guitar Score

Turn a video that *visibly contains guitar notation or TAB* into a reviewable, editable score package. The TAB pixels are the authority for guitar fingering. OCR/OMR first recovers the notes, strings, frets, rhythm, and techniques. A single verified transcription ledger then drives native Guitar Pro authoring and newly engraved IMG/PDF output. Source screenshots are evidence only, never final score pages.

## Review modes

Ask the user to choose a review mode before full-score transcription. If they do not choose, use **standard mode** and record the choice in `score.json` and `manifest.json`. Read [references/review-modes.md](references/review-modes.md) before validating or publishing a Guitar Pro file.

- **Standard mode:** run full-score machine validation and side-by-side visual comparison for every measure, but present only ambiguous or failed measures to the user. A final file requires zero blocking findings and explicit resolution of every flagged ambiguity.
- **Strict mode:** apply all standard checks, generate a measure-by-measure review booklet, and require recorded user confirmation for every measure before naming the Guitar Pro file final. Until then, label it as a candidate.

Both modes inspect every measure; the difference is how much review material the user must personally approve. Never describe standard mode as sampling or spot-checking.

## Source hierarchy

Use this precedence whenever sources disagree:

1. **Displayed TAB/notation:** authoritative for string, fret, chord voicing, position, techniques, repeats, and written rhythm.
2. **Displayed text and chord diagrams:** authoritative for tuning, capo, tempo markings, chord labels, and performance notes.
3. **Audio:** secondary evidence for timing and sounding-pitch anomaly detection only.
4. **Inferred fingering:** forbidden in a final Guitar Pro export. It may appear only in an explicitly marked draft when the displayed TAB is unreadable.

Never use MIDI, pitch recognition, chord names, or a generic guitar-position algorithm to choose a string/fret pair when TAB is visible. The same pitch has multiple possible fingerings; only the displayed TAB preserves the arrangement.

## Scope and authorization

- Prefer a user-supplied local video. For a URL, obtain media only when the user is authorized to download or process it and the host permits access. Do not bypass paywalls, DRM, logins, or platform controls.
- This skill extracts notation already displayed in the video. It does not infer a TAB from a musician's audio or hand movements; offer that as a separate, explicitly experimental workflow instead.
- Preserve source URL/path, extraction time, and source timestamps in `manifest.json`. Do not publish or distribute extracted copyrighted score pages unless the user is entitled to do so.

## Workflow

1. **Preflight and identity.** Confirm that the video contains legible notation. Ask for standard or strict review mode; default to standard if the user does not choose. Read the source-language title, composer/artist, arranger or tab author, uploader, instrument, tuning, capo, and tempo from on-screen text and public video metadata. Keep those roles separate; never substitute the uploader for the composer. Prefer the composition title over upload-only suffixes such as “完整版” when naming the score, and preserve the title's original language/script. Ask only for identity fields that remain ambiguous. Ask whether the user wants a deduplicated chord-diagram list; default to hidden if they do not answer. Ask for the instrument only when the video and notation do not identify it.
2. **Extract candidate pages.** Run `scripts/extract_score_pages.py` on a local video. It samples the opening frame and scene transitions, so long static score pages do not create thousands of duplicate images. Re-run with a lower `--scene-threshold` if pages are missed.
3. **Review and crop evidence frames.** Run `scripts/curate_score_frames.py` to remove truly near-black candidates and copy the remaining fragments to `evidence/`. Inspect them in temporal order. When the layout is stable, verify one crop visually, then apply it consistently with `scripts/clean_score_pages.py evidence --crop W:H:X:Y --output cleaned-evidence`. Keep uncropped frames in `source-frames/` for traceability. These images are OCR inputs and audit evidence, not deliverable score pages.
4. **Classify and reconstruct.** Run `scripts/classify_score_fragments.py` after cropping to remove title/progress cards based on repeated staff/TAB-line structure. Group fragments from the same page, order pages by timestamp, and only stitch adjacent crops when they overlap and their staff/TAB alignment agrees. Never silently invent an obscured measure; flag it in the manifest.
5. **Transcribe the displayed TAB.** Run `scripts/inspect_score_layout.py cleaned-pages --output layout.json` to create staff/TAB-line and barline candidates. For cross-platform OCR candidates, use `scripts/recognize_tab_fingering.py`; it uses Tesseract and runs on macOS, Windows, and Linux. On macOS, `scripts/vision_ocr.swift` is an optional Apple Vision accelerator whose candidates can be mapped with `scripts/map_tab_ocr.py`. Read each event from the TAB image into `score.json` using [references/score-schema.md](references/score-schema.md). Record page, system, measure, timestamp, and a tight bounding box for every event. OCR/vision may propose digits, but visually verify them against the original frame. A pitch without a visually observed string/fret is incomplete.
6. **Attach rhythm without changing fingering.** Read rhythm from the linked standard staff and TAB stems. Audio alignment may help locate beats or flag a sounding-pitch mismatch, but it must never rewrite the observed string or fret. Mark unreadable rhythm or technique symbols for review.
7. **Validate.** Run `scripts/validate_score.py score.json --mode <standard|strict> --report validation-report.md`. Check page order, consecutive measure numbering, measure duration, observed string/fret evidence, pitch derived from tuning+capo+fret, tied-note continuity, repeats, and unresolved symbols. Review every measure side-by-side with its cited image region. Treat missing visual provenance, inferred fingering, rhythmic errors, unconfirmed flagged ambiguities, and evidence-free techniques as blocking for a final export. In strict mode, generate `review-booklet.pdf` and keep the file candidate-only until every measure has recorded user confirmation.
8. **Author Guitar Pro directly.** Write validated TAB events into a tested native Guitar Pro format, preserving explicit string/fret, rhythm, repeats, and techniques. Populate the native title, composer/artist, arranger/tab author, and source-uploader fields where the format permits. Add the credit `video-2-guitar-score skill project` beneath the title or in the native tab/credits field. Reopen the file and compare every measure against the transcription ledger, then render it and perform the mode-specific review in [references/review-modes.md](references/review-modes.md). Never create the Guitar Pro master by importing MIDI or pitch-only MusicXML.
   - Preserve chord names at their musical positions. Deduplicate the top chord-diagram list by normalized chord name. Hide the diagram list by default. If the user opts in, show one verified diagram per chord name rather than repeating it at every occurrence; retain multiple diagrams for the same name only when the source explicitly distinguishes different voicings and the user wants both.
   - Set the playback instrument from explicit source evidence. Use acoustic guitar for acoustic/fingerstyle guitar, electric guitar for an explicitly electric source, and piano for an explicitly piano source. When the visible instrument and notation conflict, preserve the notation and ask which playback sound the user wants. Instrument choice changes the Guitar Pro track sound only; it must not rewrite observed TAB fingering.
9. **Engrave new pages.** Render fresh notation/TAB pages from the verified transcription or the reopened Guitar Pro score. Do not stitch, retouch, or deliver video screenshots as IMG/PDF. Apply consistent page size, margins, system spacing, staff/TAB pairing, measure numbers, title, tuning, capo, and tempo. Render the PDF back to images and visually inspect every page.
10. **Derive optional formats.** Export MIDI and MusicXML from Guitar Pro when available, or from the same verified transcription ledger. They are synchronized derivatives and must not feed back into string/fret decisions.

## Output contract

Create one output directory containing:

```text
manifest.json                 source metadata, timestamps, crop and provenance
source-frames/                uncropped transition frames used as evidence
evidence/                     ordered, cleaned OCR evidence images
score.json                    verified pixel-anchored transcription ledger
score.gp or score.gp5         primary editable Guitar Pro score
rendered-pages/               newly engraved page images
score.pdf                     newly engraved PDF, never a screenshot collage
score.mid                     optional derivative exported from GTP/ledger
score.musicxml                optional derivative exported from GTP/ledger
validation-report.md          findings, confidence, and user actions needed
review-booklet.pdf            strict mode: original/GTP measure comparison
review-decisions.json         user confirmations and corrections
```

Do not use `scripts/assemble_pdf.py` on evidence frames for final delivery. Final IMG/PDF must be engraved from the verified musical content. Use `scripts/score_to_midi.py` and `scripts/score_to_musicxml.py` only as fallbacks when Guitar Pro export is unavailable. `score.json` is a lossless transcription ledger of the displayed score, not an independent source allowed to contradict it. See [references/score-schema.md](references/score-schema.md).

## Quality gates

- Evidence images may be delivered for review, but they must be labeled as evidence and never presented as the requested redrawn IMG/PDF score.
- A final Guitar Pro output requires every playable note to have visually observed string/fret provenance and no unresolved rhythmic-duration or technique conflict. Spot-checking is insufficient: validate every measure.
- Standard mode may omit already-passed measures from the user-facing review, but every flagged ambiguity must have a recorded resolution. Strict mode requires a recorded user decision for every measure. Candidate files must not be named or described as final.
- Metadata quality is part of the final check: title uses the source language, composer and uploader are not conflated, project credit is present, chord diagrams follow the user's visibility choice, and the track sound matches the identified instrument.
- A draft may contain inferred items only when the user accepts a draft; label each inferred event and the filename prominently. Never present an audio-derived fingering draft as the extracted arrangement.
- MIDI and MusicXML are always downstream, synchronized derivatives. Prefer exporting them from the verified Guitar Pro score.
- Do not label a MusicXML file as `.gtp`, `.gp`, or `.gpx`; use a tested native Guitar Pro writer/exporter and state the target version.
