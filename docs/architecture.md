# Architecture

```text
versioned case history
        ↓
semantic validation
        ↓
point-in-time freeze
  ├─ latest knowable source vintage
  ├─ latest knowable assumption
  ├─ latest knowable option assessment
  ├─ locked decision rule
  └─ future outcomes removed
        ↓
canonical snapshot + SHA-256 fingerprint
        ↓
deterministic replay
  ├─ confidence shrinkage
  ├─ scenario aggregation
  ├─ worst case and regret
  ├─ option hard gates
  └─ stable tie-break
        ↓
process assurance
  ├─ 9 dimensions
  └─ 8 non-compensable gates
        ↓
outcome review
  ├─ forecast scoring
  ├─ ex-post utility and regret
  └─ process/outcome quadrant
        ↓
change and counterfactual replay
        ↓
hash-chain + unsigned Merkle checkpoint
```

## Module boundaries

- `validation.py`: structural and cross-reference integrity.
- `freeze.py`: temporal filtering and active-vintage selection.
- `process.py`: process dimensions and hard gates.
- `replay.py`: pure option scoring and deterministic selection.
- `review.py`: forecast and realized-outcome evaluation.
- `diffing.py`: evidence/rule change attribution.
- `audit.py`: local hash chain and Merkle checkpoint.
- `reporting.py`: escaped JSON, Markdown, CSV, and static HTML.
- `cli.py`: thin command interface; no external action adapter.

The scoring and replay modules have no network or clock dependency. The caller
must provide explicit timestamps.
