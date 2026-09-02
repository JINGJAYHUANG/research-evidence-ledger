# Methodology

## 1. Preserve the decision-time information set

The primary unit is not the latest document. It is the information set available
at a declared cutoff. A source carries separate publication and observation
timestamps, a lineage, a version, and an optional supersession link.

## 2. Separate evidence from claims

A source does not automatically support every sentence near it. Claims list
supporting, contradicting, and qualifying source IDs. High-consequence confirmed
claims require at least two independent source families.

## 3. Make uncertainty explicit

Assumptions use low/base/high ranges, confidence, dependencies, falsifiers, and
monitor owners. Forecasts preserve issuance time, resolution time, intervals,
probabilities, and later outcomes.

## 4. Compare options before outcomes are known

Each option receives scenario-specific criterion scores and confidence. The
system shrinks uncertain scores toward 50:

```text
adjusted = 50 + confidence × (raw − 50)
```

The rule aggregates base, expected, worst-case, and regret components. Failed
hard gates make an option ineligible.

## 5. Lock the rule

The canonical rule payload is hashed. The recorded decision binds the exact rule
digest. A later rule version may be evaluated prospectively but cannot replace
the historical rule.

## 6. Review process and outcome separately

Ex-post regret compares the recorded choice with the best synthetic realized
utility. It is paired with the process score rather than replacing it.

## 7. Convert surprise into a future action

A review records surprises, assumption updates, prospective rule changes, and
owned learning actions. Hindsight is useful only when it improves the next
decision without rewriting the previous one.
