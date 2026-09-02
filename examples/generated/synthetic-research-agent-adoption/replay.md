# Decision Replay — synthetic-research-agent-adoption

- Cutoff: `2026-04-30T17:00:00Z`
- Rule: `rule-agent-v1`
- Selected option: **opt-sandbox**
- Recorded option: `opt-sandbox`
- Recorded decision matches replay: `true`
- Process score: **96.00/100**
- Process level: **exemplary**

> This is a reconstruction of a synthetic decision record, not a claim that the option is suitable for a real organization.

## Options

| Option | Robust | Expected | Worst | Max regret | Gate state |
|---|---:|---:|---:|---:|---|
| `opt-autonomous` | 44.19 | 46.29 | 27.21 | 44.52 | FAIL: distributional-floor, privacy, safety |
| `opt-manual` | 70.79 | 69.90 | 64.76 | 14.43 | pass |
| `opt-sandbox` | 75.75 | 74.59 | 65.99 | 5.74 | pass |

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
