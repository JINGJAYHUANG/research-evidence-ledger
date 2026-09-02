from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT


def run_cli(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "research_evidence_ledger", *args], cwd=ROOT, env=env, text=True, capture_output=True)


class CliTests(unittest.TestCase):
    def test_version(self):
        result = run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("0.1.0", result.stdout)

    def test_validate_case(self):
        result = run_cli("validate", "examples/cases/synthetic-capacity-expansion.json", "--strict")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_validate_json(self):
        result = run_cli("validate", "examples/cases/synthetic-capacity-expansion.json", "--strict", "--json")
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_freeze_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "snapshot.json"
            result = run_cli("freeze", "examples/cases/synthetic-capacity-expansion.json", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            self.assertEqual(run_cli("validate", str(output), "--kind", "snapshot", "--strict").returncode, 0)

    def test_replay_case_json(self):
        result = run_cli("replay", "--case", "examples/cases/synthetic-capacity-expansion.json", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["selected_option_id"], "opt-phased")

    def test_replay_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "replay.md"
            result = run_cli("replay", "--case", "examples/cases/synthetic-capacity-expansion.json", "--format", "markdown", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Decision Replay", output.read_text())

    def test_review_json(self):
        result = run_cli("review", "examples/cases/synthetic-research-agent-adoption.json", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision_quality_quadrant"], "sound-but-unlucky")

    def test_review_markdown(self):
        result = run_cli("review", "examples/cases/synthetic-capacity-expansion.json", "--format", "markdown")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Decision Review", result.stdout)

    def test_diff(self):
        result = run_cli("diff", "examples/cases/synthetic-research-agent-adoption.json", "--before", "2026-04-30T17:00:00Z", "--after", "2026-09-01T18:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["decision_flip_with_new_evidence_same_rule"])

    def test_trace_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.jsonl"
            checkpoint = Path(tmp) / "checkpoint.json"
            create = run_cli("trace", "examples/cases/synthetic-capacity-expansion.json", "--output", str(trace), "--checkpoint", str(checkpoint))
            self.assertEqual(create.returncode, 0, create.stderr)
            audit = run_cli("audit", str(trace), "--checkpoint", str(checkpoint), "--json")
            self.assertEqual(audit.returncode, 0, audit.stderr)
            self.assertTrue(json.loads(audit.stdout)["ok"])

    def test_lab(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "lab.html"
            result = run_cli("lab", "examples/cases/synthetic-capacity-expansion.json", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Decision Time Machine", output.read_text())

    def test_fingerprint(self):
        result = run_cli("fingerprint", "examples/cases/synthetic-capacity-expansion.json")
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout.strip(), r"^sha256:[0-9a-f]{64}$")

    def test_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "scaffold.json"
            result = run_cli("scaffold", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(output.read_text())["public_boundary"]["synthetic_only"])

    def test_self_test(self):
        result = run_cli("self-test", "--root", ".", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["case_count"], 3)
        self.assertEqual(payload["mutant_count"], 7)

    def test_missing_file_returns_two(self):
        result = run_cli("validate", "missing.json")
        self.assertEqual(result.returncode, 2)

    def test_invalid_review_cutoff_returns_two(self):
        result = run_cli("review", "examples/cases/synthetic-capacity-expansion.json", "--cutoff", "2026-01-01T00:00:00Z")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
