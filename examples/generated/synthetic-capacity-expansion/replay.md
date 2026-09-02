# Decision Replay — synthetic-capacity-expansion

- Cutoff: `2026-03-31T17:00:00Z`
- Rule: `rule-robust-v1`
- Selected option: **opt-phased**
- Recorded option: `opt-phased`
- Recorded decision matches replay: `true`
- Process score: **96.00/100**
- Process level: **exemplary**

> This is a reconstruction of a synthetic decision record, not a claim that the option is suitable for a real organization.

## Options

| Option | Robust | Expected | Worst | Max regret | Gate state |
|---|---:|---:|---:|---:|---|
| `opt-defer` | 63.59 | 63.10 | 55.78 | 21.59 | pass |
| `opt-full` | 47.94 | 49.76 | 29.61 | 36.83 | pass |
| `opt-phased` | 76.22 | 74.00 | 66.44 | -0.00 | pass |

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
