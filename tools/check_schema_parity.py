#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from research_evidence_ledger.validation import CERTAINTY, CLAIM_TYPES, GATE_STATES, LEVELS, SOURCE_TYPES


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load = lambda name: json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
    errors = []
    source = load("source.schema.json")
    claim = load("claim.schema.json")
    assessment = load("assessment.schema.json")
    if set(source["properties"]["source_type"]["enum"]) != SOURCE_TYPES:
        errors.append("source_type enum differs from validator")
    if set(claim["properties"]["claim_type"]["enum"]) != CLAIM_TYPES:
        errors.append("claim_type enum differs from validator")
    if set(claim["properties"]["certainty"]["enum"]) != CERTAINTY:
        errors.append("certainty enum differs from validator")
    if set(claim["properties"]["consequence"]["enum"]) != LEVELS:
        errors.append("consequence enum differs from validator")
    if set(assessment["properties"]["gates"]["additionalProperties"]["enum"]) != GATE_STATES:
        errors.append("gate state enum differs from validator")
    required = {"case.schema.json", "source.schema.json", "claim.schema.json", "assumption.schema.json", "forecast.schema.json", "assessment.schema.json", "decision-rule.schema.json", "snapshot.schema.json", "replay.schema.json", "review.schema.json", "diff.schema.json", "audit-record.schema.json", "checkpoint.schema.json", "artifact-manifest.schema.json"}
    actual = {path.name for path in (root / "schemas").glob("*.json")}
    if actual != required:
        errors.append(f"schema file set differs: expected={sorted(required)} actual={sorted(actual)}")
    for path in (root / "schemas").glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not value.get("$id", "").startswith("https://github.com/JINGJAYHUANG/research-evidence-ledger/"):
            errors.append(f"{path.name}: non-repository schema id")
    if errors:
        print("schema parity failed:")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print(f"schema parity passed: {len(actual)} schema(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
