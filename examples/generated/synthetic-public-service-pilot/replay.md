# Decision Replay — synthetic-public-service-pilot

- Cutoff: `2026-05-31T17:00:00Z`
- Rule: `rule-public-v1`
- Selected option: **opt-bounded-pilot**
- Recorded option: `opt-bounded-pilot`
- Recorded decision matches replay: `true`
- Process score: **96.00/100**
- Process level: **exemplary**

> This is a reconstruction of a synthetic decision record, not a claim that the option is suitable for a real organization.

## Options

| Option | Robust | Expected | Worst | Max regret | Gate state |
|---|---:|---:|---:|---:|---|
| `opt-bounded-pilot` | 76.32 | 74.48 | 65.44 | 0.51 | pass |
| `opt-full-rollout` | 42.35 | 43.46 | 24.62 | 41.32 | FAIL: distributional-floor, legal, privacy, safety |
| `opt-status-quo` | 68.20 | 66.22 | 63.37 | 15.44 | FAIL: distributional-floor |

## Hard process gates

- `no-future-information`: **pass** — No finding.
- `vintage-integrity`: **pass** — No finding.
- `rule-immutability`: **pass** — No finding.
- `approval-integrity`: **pass** — No finding.
- `external-action-safety`: **pass** — No finding.
- `graph-integrity`: **pass** — No finding.
- `high-consequence-corroboration`: **pass** — No finding.
- `hindsight-rationale-boundary`: **pass** — No finding.

## Claim boundary

This replay reconstructs the stated synthetic decision rule using information in the frozen snapshot. It does not prove the selected option was objectively best or suitable for a real decision.
