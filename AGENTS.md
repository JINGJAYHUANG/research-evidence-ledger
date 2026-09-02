# Repository agent instructions

Before changing decision semantics, read `docs/methodology.md`,
`docs/point-in-time.md`, `docs/threat-model.md`, and `docs/design-decisions.md`.

Preserve these invariants:

- no future information enters a decision snapshot;
- source vintages are selected by knowable observation time;
- rules are versioned, hashed, and prospective;
- failed hard gates cannot be averaged away;
- process quality remains separate from outcome luck;
- external actions remain disabled;
- examples remain fictional and synthetic;
- hashes are never described as proof of truth, identity, or occurrence.

Run `python tools/release_gate.py` before committing.
