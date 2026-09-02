from __future__ import annotations

import csv
import io
import unittest

from research_evidence_ledger.diffing import compare_snapshots
from research_evidence_ledger.freeze import freeze_case
from research_evidence_ledger.replay import replay_decision
from research_evidence_ledger.reporting import render, replay_html
from research_evidence_ledger.review import review_decision
from helpers import case


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.case = case("synthetic-capacity-expansion")
        self.before = freeze_case(self.case, self.case["decision"]["decision_cutoff"])
        self.after = freeze_case(self.case, self.case["review"]["reviewed_at"])
        self.replay = replay_decision(self.before)
        self.review = review_decision(self.case)
        self.diff = compare_snapshots(self.before, self.after)

    def test_replay_json_parseable(self):
        import json
        self.assertEqual(json.loads(render("replay", self.replay, format_name="json"))["selected_option_id"], "opt-phased")

    def test_review_json_parseable(self):
        import json
        self.assertEqual(json.loads(render("review", self.review, format_name="json"))["decision_quality_quadrant"], "sound-and-fortunate")

    def test_markdown_has_gate_section(self):
        text = render("replay", self.replay, format_name="markdown")
        self.assertIn("## Hard process gates", text)
        self.assertIn("no-future-information", text)

    def test_markdown_has_claim_boundary(self):
        text = render("replay", self.replay, format_name="markdown")
        self.assertIn("not a claim", text)

    def test_review_markdown_has_learning(self):
        text = render("review", self.review, format_name="markdown")
        self.assertIn("## Learning actions", text)
        self.assertIn("sound-and-fortunate", text)

    def test_csv_parseable(self):
        text = render("replay", self.replay, format_name="csv")
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["option_id"] for row in rows}, {"opt-defer", "opt-full", "opt-phased"})

    def test_csv_formula_hardening(self):
        replay = replay_decision(self.before)
        replay["options"][0]["title"] = "=HYPERLINK('x')"
        text = render("replay", replay, format_name="csv")
        self.assertIn("'=HYPERLINK", text)

    def test_html_has_no_script(self):
        text = replay_html(self.replay, review=self.review, diff=self.diff)
        self.assertNotIn("<script", text.lower())
        self.assertNotIn("<iframe", text.lower())
        self.assertNotIn("<form", text.lower())

    def test_html_escapes_case_id(self):
        replay = dict(self.replay)
        replay["case_id"] = "<img src=x onerror=alert(1)>"
        text = replay_html(replay)
        self.assertNotIn("<img src=x", text)
        self.assertIn("&lt;img", text)

    def test_html_contains_review(self):
        text = replay_html(self.replay, review=self.review, diff=self.diff)
        self.assertIn("Outcome review", text)
        self.assertIn("sound-and-fortunate", text)

    def test_html_contains_diff(self):
        text = replay_html(self.replay, review=self.review, diff=self.diff)
        self.assertIn("What changed", text)
        self.assertIn("flip from evidence", text)

    def test_html_contains_print_style(self):
        self.assertIn("@media print", replay_html(self.replay))

    def test_unsupported_render_rejected(self):
        with self.assertRaises(ValueError):
            render("review", self.review, format_name="csv")


if __name__ == "__main__":
    unittest.main()
