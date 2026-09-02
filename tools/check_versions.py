#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    init = re.search(r'__version__ = "([^"]+)"', (root / "src/research_evidence_ledger/__init__.py").read_text(encoding="utf-8")).group(1)
    citation = re.search(r'^version: "([^"]+)"', (root / "CITATION.cff").read_text(encoding="utf-8"), re.M).group(1)
    rubric = json.loads((root / "data/process-rubric.json").read_text(encoding="utf-8"))["version"]
    values = {"project": project, "package": init, "citation": citation, "rubric": rubric}
    if len(set(values.values())) != 1:
        print(f"version mismatch: {values}")
        return 1
    if not (root / f"docs/release-notes/v{project}.md").is_file():
        print("release notes missing")
        return 1
    print(f"version check passed: {project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
