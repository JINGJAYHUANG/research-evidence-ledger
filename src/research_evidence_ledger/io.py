from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from .canonical import canonical_json


def load_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{target}: top-level JSON value must be an object")
    return value


def write_json(path: str | Path, value: Any, *, compact: bool = False) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = canonical_json(value) if compact else json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    target.write_text(text + "\n", encoding="utf-8", newline="\n")


def load_process_rubric(path: str | Path | None = None) -> dict[str, Any]:
    if path is not None:
        return load_json(path)
    text = (
        resources.files("research_evidence_ledger")
        .joinpath("data", "process-rubric.json")
        .read_text(encoding="utf-8")
    )
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("packaged process rubric must be an object")
    return value
