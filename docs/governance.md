# Benchmark and method governance

Changes to timestamps, hard gates, scoring, confidence shrinkage, robust
aggregation, or outcome quadrants are methodology changes.

They require:

- a rationale tied to a failure mode;
- an updated positive reference case;
- an adversarial case that would fail without the change;
- regenerated deterministic artifacts;
- version and changelog review;
- full release gate execution.

Do not alter a historical case merely to make the recorded choice match the
current rule. Add a new source, assumption, assessment, or rule version with a
later timestamp.
