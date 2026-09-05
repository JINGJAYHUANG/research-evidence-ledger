# Revisit a decision without rewriting its history
## 复盘当时的决定，而不是事后重新编理由

[Full documentation](README.md) · [Public tool collection](https://github.com/JINGJAYHUANG/JINGJAYHUANG)

**For:** researchers, analysts and teams who need to explain why a choice made sense at a particular time.  
**Input:** a structured decision case with dated evidence, assumptions, options and a declared rule.  
**Output:** a frozen snapshot, a replay of the rule, and a review that keeps process quality separate from the outcome.

## Run the synthetic capacity-expansion example

Requires Python 3.11 or newer. Create and activate an isolated environment before installing from source.

```bash
git clone https://github.com/JINGJAYHUANG/research-evidence-ledger.git
cd research-evidence-ledger
python -m venv .venv
```

Activate with `source .venv/bin/activate` on macOS/Linux, or `.venv\Scripts\Activate.ps1` in Windows PowerShell. Then:

```bash
python -m pip install --no-deps -e .
rel validate examples/cases/synthetic-capacity-expansion.json --strict
rel freeze examples/cases/synthetic-capacity-expansion.json --output out/decision.snapshot.json
rel replay --snapshot out/decision.snapshot.json --format markdown --output out/replay.md
rel review examples/cases/synthetic-capacity-expansion.json --format markdown --output out/review.md
```

Inspect `out/decision.snapshot.json`, `out/replay.md` and `out/review.md` together. A useful question is: which facts were available at the cutoff, and which only became known later?

## A visual example

```bash
rel lab examples/cases/synthetic-research-agent-adoption.json --output out/decision-lab.html
```

Open `out/decision-lab.html` locally. The case deliberately separates a reasonable process from an unfavorable outcome; it is fictional, not a record of a real organization.

## What makes this useful

“结果好”不等于“当时的方法可靠”，“结果差”也不自动等于“当时判断错误”。保留证据时间、原始规则和后来变化，才有机会知道应该改进哪一步。

Possible applications include a software-adoption decision, a capacity plan or a bounded pilot. You must map your records into the project's schema; this is not a free-text chatbot that automatically reconstructs the truth.

## Boundaries

A hash is evidence of content integrity, not truth, authorship or an external timestamp. The tool does not execute decisions or certify the safety of real deployments. Keep confidential decisions outside public repositories; use synthetic fixtures when contributing.

Read the [README](README.md), methodology and threat model before adapting the scoring or hard gates. Commands here follow default-branch documentation reviewed on 2026-09-05; this guide does not claim a fresh full test run or production acceptance.
