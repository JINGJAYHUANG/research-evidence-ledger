# Design decisions

## JSON and standard library only

The first release has no runtime dependencies. This keeps canonicalization,
validation, replay, and release behavior inspectable and portable.

## No hidden model judge

Process checks are explicit booleans. The system does not ask an LLM to assign a
quality score that cannot be reproduced.

## Unknown is not neutral evidence

Confidence shrinkage pulls uncertain option scores toward 50. Missing or weak
evidence cannot create an extreme advantage.

## Rules are data

Decision rules are versioned and hashed. Later changes are represented as new
records, not code edits that silently rewrite history.

## Audit is described conservatively

The local chain is tamper-evident, not tamper-proof. Checkpoints are unsigned.
