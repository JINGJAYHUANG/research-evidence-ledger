# Data dictionary

## Case history

- `sources`: versioned evidence metadata.
- `claims`: statements linked to supporting, contradicting, and qualifying sources.
- `assumptions`: versioned uncertain premises with ranges and falsifiers.
- `forecasts`: timestamped intervals and optional event probabilities.
- `scenarios`: mutually declared states with probabilities.
- `options`: static option identity and reversibility.
- `assessments`: versioned scenario and distributional scores.
- `decision_rules`: versioned weights, gates, floors, and tie-breaks.
- `decision`: selected option, bound rule digest, approvals, rationale, and action state.
- `outcomes`: later realized synthetic utility and metrics.
- `review`: surprises, updates, prospective rules, and learning actions.

## Frozen snapshot

A snapshot contains the active knowable vintages plus a canonical fingerprint.
`freeze_metadata` lists excluded future source IDs and record counts.

## Replay

The replay contains option-level scenario scores, regret, gate status, selected
option, recorded match, process score, and claim boundary.
