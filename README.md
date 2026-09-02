# Research Evidence Ledger

[![CI](https://github.com/JINGJAYHUANG/research-evidence-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/JINGJAYHUANG/research-evidence-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/JINGJAYHUANG/research-evidence-ledger)](https://github.com/JINGJAYHUANG/research-evidence-ledger/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.13-blue.svg)](pyproject.toml)

A zero-runtime-dependency **point-in-time decision replay and learning system**.
It freezes what was knowable when a choice was made, replays the declared rule,
separates process quality from outcome luck, records evidence and assumption
changes, and preserves a tamper-evident local audit trail.

**Maturity:** `reference-method-and-tooling-validated`  
**Boundary:** synthetic examples only; no external actions, personal data,
credentials, factual certification, or production-safety claim.

[中文说明](docs/README.zh-CN.md) ·
[Methodology](docs/methodology.md) ·
[Architecture](docs/architecture.md) ·
[Threat model](docs/threat-model.md) ·
[Decision Time Machine Lab](examples/generated/decision-time-machine-lab.html)

## The problem

Decision records usually preserve the final choice but lose the state of
knowledge that justified it. Later evidence, revised datasets, realized
outcomes, and hindsight narratives quietly overwrite the original context.
That makes it difficult to distinguish:

```text
sound process + good outcome
sound process + bad luck
fragile process + good luck
fragile process + poor outcome
```

Research Evidence Ledger treats a decision as a versioned evidence object:

```text
sources and vintages
  → claims and boundaries
  → assumptions and falsifiers
  → forecasts and intervals
  → options and scenario assessments
  → locked decision rule
  → approvals and action boundary
  → frozen point-in-time snapshot
  → deterministic replay
  → outcome review
  → prospective learning
```

## What the package does

### 1. Freeze

`rel freeze` includes only records that were published, observed, recorded, or
issued by the declared cutoff. It chooses the latest source, assumption,
assessment, and rule vintage that was actually knowable at that time, strips
future forecast outcomes, and produces a canonical SHA-256 snapshot.

### 2. Replay

`rel replay` applies the rule that was locked at the decision cutoff. Option
scores are confidence-shrunk toward neutral, aggregated across scenarios, and
combined through base, expected, worst-case, and maximum-regret terms. Failed
hard gates cannot be averaged away.

### 3. Review

`rel review` evaluates forecasts and realized option utilities while retaining
the original decision snapshot. It reports ex-post regret and places the case
in one of four quadrants:

| Process | Outcome | Classification |
|---|---|---|
| sound | favorable | `sound-and-fortunate` |
| sound | unfavorable | `sound-but-unlucky` |
| fragile | favorable | `lucky-but-fragile` |
| fragile | unfavorable | `poor-process-poor-outcome` |

### 4. Learn prospectively

Assumption updates and decision-rule changes are recorded after the outcome.
Rule changes must be marked `prospective_only`; the tool never rewrites the
original rule to make the historical decision appear better.

### 5. Audit

A local JSONL chain links each event to its predecessor and can produce an
unsigned Merkle checkpoint. This is tamper-evident evidence, not a signature,
authorship proof, or external timestamp.

## Quick start

```bash
python -m pip install --no-deps -e .

rel validate examples/cases/synthetic-capacity-expansion.json --strict
rel freeze examples/cases/synthetic-capacity-expansion.json \
  --output out/decision.snapshot.json
rel replay --snapshot out/decision.snapshot.json \
  --format markdown --output out/replay.md
rel review examples/cases/synthetic-capacity-expansion.json \
  --format markdown --output out/review.md
rel self-test --root .
```

Build a static decision time-machine page:

```bash
rel lab examples/cases/synthetic-research-agent-adoption.json \
  --output out/decision-lab.html
```

Create and verify a local evidence trace:

```bash
rel trace examples/cases/synthetic-capacity-expansion.json \
  --output out/trace.jsonl \
  --checkpoint out/checkpoint.json

rel audit out/trace.jsonl \
  --checkpoint out/checkpoint.json
```

## Eight process hard gates

| Gate | Prevented failure |
|---|---|
| `no-future-information` | hindsight leakage into the decision snapshot |
| `vintage-integrity` | replacing the knowable vintage with an older or later revision |
| `rule-immutability` | changing weights or rules after the outcome |
| `approval-integrity` | treating incomplete approval as authorization |
| `external-action-safety` | claiming an external action ran without a bound receipt |
| `graph-integrity` | circular assumptions and invalid dependency graphs |
| `high-consequence-corroboration` | counting one source family as independent confirmation |
| `hindsight-rationale-boundary` | writing the rationale after results were visible |

Any failed hard gate forces the process level to `unsafe`, regardless of the
arithmetic score.

## Process dimensions

| Dimension | Weight |
|---|---:|
| Temporal integrity | 20 |
| Provenance quality | 14 |
| Claim discipline | 14 |
| Uncertainty honesty | 11 |
| Option completeness | 10 |
| Decision-rule transparency | 10 |
| Approval and action safety | 8 |
| Distributional awareness | 5 |
| Monitoring and learning | 8 |

The score is a completeness and integrity diagnostic for the declared record.
It is not a claim that a decision was correct.

## Synthetic cases

| Case | Decision-time choice | Later review |
|---|---|---|
| Capacity expansion | phased modular capacity | sound and fortunate |
| Research-agent adoption | bounded sandbox pilot | sound but unlucky |
| Public-service pilot | assistance-only bounded pilot | sound and fortunate |

The research-agent case deliberately demonstrates a decision flip when later
evidence is replayed with the original rule. That does not retroactively make
the original decision irrational.

## Adversarial cases

Seven mutants prove that the system detects:

- future evidence leakage;
- known-vintage substitution;
- echo-chamber corroboration;
- decision-rule mutation;
- approval and execution bypass;
- circular assumptions;
- hindsight rationale rewriting.

## Repository map

```text
src/research_evidence_ledger/   freeze, replay, review, diff, audit, reports
src/.../data/                   packaged process rubric
examples/cases/                 three complete synthetic decision histories
examples/mutants/               seven adversarial histories
examples/generated/             deterministic reports and Decision Time Machine
schemas/                        fourteen public JSON contracts
tests/                          unit, mutation, CLI, artifact, and release tests
tools/                          generation, safety, schema, workflow, release gates
docs/                           method, governance, threat, and boundary documents
```

## Standards relationship

The project borrows vocabulary and design inspiration from the W3C PROV family,
NIST AI Risk Management Framework, SLSA provenance, and Datasheets for Datasets.
It is not an implementation certification, conformance statement, or
endorsement by those projects. See [reference-shelf.md](docs/reference-shelf.md).

## Public boundary

The repository contains no:

- real decision, organization, customer, account, or person;
- credential, token, cookie, webhook, email address, or phone number;
- private file, proprietary evidence, or hidden profile;
- external-action adapter;
- claim that hashes prove truth, identity, or real-world occurrence;
- claim that synthetic tests establish production safety.

Read [limitations.md](docs/limitations.md) before adapting the method.

## Development

```bash
python -m pip install --no-deps -e .
python tools/release_gate.py
```

Changes to scoring, hard gates, timestamps, or replay semantics require both a
positive case and an adversarial case.

## License

MIT. See [LICENSE](LICENSE).
