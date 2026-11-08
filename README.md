# Video to Guitar Score

An AI-agent skill for recovering guitar TAB or notation visibly shown in an authorized video and producing a reviewable, editable Guitar Pro score package.

It treats the displayed TAB pixels as the authority for string and fret choices, keeps per-event visual provenance, and uses full-score validation before a file can be called final.

## Contents

- `SKILL.md` — workflow, quality gates, and output contract
- `references/` — transcription ledger schema and review-mode requirements
- `scripts/` — extraction, OCR assistance, validation, MIDI/MusicXML, and Guitar Pro 5 utilities

## Scope

Use this only for videos that visibly display notation or TAB and that you are authorized to process. It is not an audio-only transcription tool.

## Install

Install or import this directory using your AI tool's skill, agent, or prompt-extension workflow. Then invoke it for an authorized video with legible displayed guitar notation.

## License

Released under the [MIT License](LICENSE).
