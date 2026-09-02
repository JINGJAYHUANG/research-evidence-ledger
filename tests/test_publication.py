from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

from helpers import CASE_DIR, GENERATED_DIR, MUTANT_DIR, ROOT


def run_tool(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=env, text=True, capture_output=True)


def load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PublicationTests(unittest.TestCase):
    def test_required_files(self):
        required = [
            "README.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md",
            "GOVERNANCE.md", "SUPPORT.md", "CHANGELOG.md", "ROADMAP.md",
            "CITATION.cff", "ORIGIN_MANIFEST.json", "RELEASE_CHECKLIST.md",
            "docs/architecture.md", "docs/methodology.md", "docs/threat-model.md",
            "tools/release_gate.py", ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
        ]
        for relative in required:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_no_legacy_bootstrap_transport(self):
        self.assertFalse((ROOT / ".bootstrap").exists())
        self.assertFalse((ROOT / ".github/workflows/inspect-staged-payload.yml").exists())

    def test_exact_case_and_mutant_counts(self):
        self.assertEqual(len(list(CASE_DIR.glob("*.json"))), 3)
        self.assertEqual(len(list(MUTANT_DIR.glob("*.json"))), 7)

    def test_exact_schema_count(self):
        self.assertEqual(len(list((ROOT / "schemas").glob("*.json"))), 14)

    def test_rubric_weights_sum_to_100(self):
        rubric = json.loads((ROOT / "data/process-rubric.json").read_text())
        self.assertEqual(sum(item["weight"] for item in rubric["dimensions"]), 100)
        self.assertEqual(len(rubric["hard_gates"]), 8)

    def test_packaged_rubric_identical(self):
        self.assertEqual(
            (ROOT / "data/process-rubric.json").read_bytes(),
            (ROOT / "src/research_evidence_ledger/data/process-rubric.json").read_bytes(),
        )

    def test_version_sync_tool(self):
        result = run_tool("tools/check_versions.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_versions_are_010(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
        self.assertEqual(project, "0.1.0")
        self.assertIn('__version__ = "0.1.0"', (ROOT / "src/research_evidence_ledger/__init__.py").read_text())

    def test_generated_examples_current(self):
        result = run_tool("tools/generate_examples.py", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_generated_manifest_valid(self):
        result = run_tool("tools/audit_generated.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_schema_parity(self):
        result = run_tool("tools/check_schema_parity.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_docs_links(self):
        result = run_tool("tools/check_docs.py", ".")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_workflow_syntax(self):
        result = run_tool("tools/check_workflows.py", ".")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_public_audit(self):
        result = run_tool("tools/public_audit.py", ".")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_public_audit_detects_token(self):
        module = load_script("rel_public_audit", "tools/public_audit.py")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            token = "gh" + "p_" + "A" * 36
            (Path(tmp) / "sample.txt").write_text(token)
            _, findings = module.scan(Path(tmp))
            self.assertIn("github_token", {item.code for item in findings})

    def test_json_files_have_newline(self):
        for path in ROOT.rglob("*.json"):
            if not any(part in {".git", "build", "dist"} for part in path.parts):
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertTrue(path.read_bytes().endswith(b"\n"))

    def test_generated_lab_is_static(self):
        text = (GENERATED_DIR / "decision-time-machine-lab.html").read_text().lower()
        for forbidden in ("<script", "<iframe", "<form", "http://", "https://"):
            self.assertNotIn(forbidden, text)

    def test_case_labs_are_static(self):
        for path in GENERATED_DIR.glob("*/decision-lab.html"):
            text = path.read_text().lower()
            for forbidden in ("<script", "<iframe", "<form", "http://", "https://"):
                with self.subTest(path=path, forbidden=forbidden):
                    self.assertNotIn(forbidden, text)

    def test_generated_case_directories_complete(self):
        required = {
            "decision.snapshot.json", "review.snapshot.json", "replay.json", "review.json",
            "diff.json", "replay.md", "review.md", "options.csv", "decision-lab.html",
            "trace.jsonl", "checkpoint.json",
        }
        for case_path in CASE_DIR.glob("*.json"):
            directory = GENERATED_DIR / case_path.stem
            self.assertEqual({path.name for path in directory.iterdir() if path.is_file()}, required)

    def test_mutant_artifacts_match_expectation(self):
        for path in (GENERATED_DIR / "mutants").glob("*.process.json"):
            value = json.loads(path.read_text())
            self.assertTrue(value["matches_expected"], path)

    def test_ci_actions_pinned(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", text)
        self.assertIn("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", text)
        self.assertNotRegex(text, r"uses:\s*[^\s#]+@v\d")

    def test_release_is_dynamic_and_retry_safe(self):
        text = (ROOT / ".github/workflows/release.yml").read_text()
        self.assertIn("origin/main", text)
        self.assertIn("count_tests", text)
        self.assertIn("gh release upload", text)
        self.assertIn("--clobber", text)
        self.assertIn("sha256sum -c SHA256SUMS.txt", text)
        self.assertIn("version = os.environ['VERSION'].removeprefix('v')", text)
        self.assertNotIn("'test_count': 200", text)

    def test_readme_claim_boundaries(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("not a claim that a decision was correct", text)
        self.assertIn("synthetic examples only", text)
        self.assertIn("tamper-evident evidence, not a signature", text)

    def test_origin_manifest_excludes_private_content(self):
        value = json.loads((ROOT / "ORIGIN_MANIFEST.json").read_text())
        excluded = set(value["excluded"])
        self.assertIn("personal data", excluded)
        self.assertIn("credentials", excluded)
        self.assertIn("private decision records", excluded)

    def test_no_runtime_dependencies(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertNotIn("dependencies", project)

    def test_release_notes_exist(self):
        self.assertTrue((ROOT / "docs/release-notes/v0.1.0.md").is_file())

    def test_generated_manifest_count(self):
        value = json.loads((GENERATED_DIR / "generated-manifest.json").read_text())
        self.assertEqual(value["case_count"], 3)
        self.assertEqual(value["mutant_count"], 7)
        self.assertEqual(value["file_count"], len(value["files"]))


if __name__ == "__main__":
    unittest.main()
