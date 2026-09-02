#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from research_evidence_ledger.io import load_json
from research_evidence_ledger.validation import validate_case

ROOT = Path(__file__).resolve().parents[1]


def run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    for path in sorted((ROOT / "examples/cases").glob("*.json")):
        report = validate_case(load_json(path), strict=True)
        if not report.ok:
            raise SystemExit(report.as_dict())
    run(sys.executable, "-m", "compileall", "-q", "src", "tools", "tests")
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    run(sys.executable, "tools/generate_examples.py", "--check")
    run(sys.executable, "tools/audit_generated.py")
    run(sys.executable, "tools/check_versions.py")
    run(sys.executable, "tools/check_schema_parity.py")
    run(sys.executable, "tools/check_docs.py", ".")
    run(sys.executable, "tools/check_workflows.py", ".")
    run(sys.executable, "tools/public_audit.py", ".")
    run(sys.executable, "-m", "research_evidence_ledger", "self-test", "--root", ".")
    print("release gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
