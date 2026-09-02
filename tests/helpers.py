from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "examples/cases"
MUTANT_DIR = ROOT / "examples/mutants"
GENERATED_DIR = ROOT / "examples/generated"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cases():
    return [load(path) for path in sorted(CASE_DIR.glob("*.json"))]


def mutants():
    return [load(path) for path in sorted(MUTANT_DIR.glob("*.json"))]


def case(case_id: str):
    return load(CASE_DIR / f"{case_id}.json")
