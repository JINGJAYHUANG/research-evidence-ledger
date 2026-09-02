from __future__ import annotations

import copy
import unittest

from research_evidence_ledger.freeze import freeze_case
from research_evidence_ledger.validation import validate_snapshot
from helpers import cases, case


class FreezeTests(unittest.TestCase):
    def test_decision_snapshot_is_deterministic(self):
        for value in cases():
            with self.subTest(case=value["case_id"]):
                first = freeze_case(value, value["decision"]["decision_cutoff"])
                second = freeze_case(value, value["decision"]["decision_cutoff"])
                self.assertEqual(first, second)

    def test_decision_snapshot_excludes_review(self):
        for value in cases():
            snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
            self.assertIsNone(snapshot["review"])
            self.assertEqual(snapshot["outcomes"], [])

    def test_decision_snapshot_strips_forecast_outcomes(self):
        for value in cases():
            snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
            self.assertTrue(snapshot["forecasts"])
            self.assertTrue(all(item["outcome"] is None for item in snapshot["forecasts"]))

    def test_review_snapshot_includes_outcomes(self):
        for value in cases():
            snapshot = freeze_case(value, value["review"]["reviewed_at"])
            self.assertTrue(snapshot["outcomes"])
            self.assertIsNotNone(snapshot["review"])

    def test_source_vintage_changes_after_review(self):
        value = case("synthetic-capacity-expansion")
        before = freeze_case(value, value["decision"]["decision_cutoff"])
        after = freeze_case(value, value["review"]["reviewed_at"])
        self.assertEqual(before["active_source_ids"]["demand-outlook"], "src-demand-v1")
        self.assertEqual(after["active_source_ids"]["demand-outlook"], "src-demand-v2")

    def test_assumption_vintage_changes_after_review(self):
        value = case("synthetic-capacity-expansion")
        before = freeze_case(value, value["decision"]["decision_cutoff"])
        after = freeze_case(value, value["review"]["reviewed_at"])
        self.assertEqual(before["active_assumption_ids"]["demand-growth"], "asm-demand-v1")
        self.assertEqual(after["active_assumption_ids"]["demand-growth"], "asm-demand-v2")

    def test_assessment_vintage_changes_after_review(self):
        value = case("synthetic-research-agent-adoption")
        before = freeze_case(value, value["decision"]["decision_cutoff"])
        after = freeze_case(value, value["review"]["reviewed_at"])
        self.assertEqual(before["active_assessment_ids"]["opt-sandbox"], "assess-sandbox-v1")
        self.assertEqual(after["active_assessment_ids"]["opt-sandbox"], "assess-sandbox-v2")

    def test_rule_vintage_changes_after_review(self):
        value = case("synthetic-research-agent-adoption")
        before = freeze_case(value, value["decision"]["decision_cutoff"])
        after = freeze_case(value, value["review"]["reviewed_at"])
        self.assertEqual(before["active_rule_ids"]["robust-mcda"], "rule-agent-v1")
        self.assertEqual(after["active_rule_ids"]["robust-mcda"], "rule-agent-v2")

    def test_future_source_list_is_explicit(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        self.assertIn("src-demand-v2", snapshot["freeze_metadata"]["excluded_future_source_ids"])

    def test_claim_sources_trimmed_to_cutoff(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        self.assertNotIn("claim-demand-revision", {item["claim_id"] for item in snapshot["claims"]})

    def test_cutoff_before_decision_omits_decision(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, "2026-03-01T00:00:00Z")
        self.assertIsNone(snapshot["decision"])

    def test_snapshot_validates(self):
        for value in cases():
            snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
            self.assertTrue(validate_snapshot(snapshot, strict=True).ok)

    def test_input_not_mutated(self):
        value = case("synthetic-capacity-expansion")
        original = copy.deepcopy(value)
        freeze_case(value, value["decision"]["decision_cutoff"])
        self.assertEqual(value, original)

    def test_invalid_case_rejected(self):
        value = case("synthetic-capacity-expansion")
        value["sources"][0]["content_hash"] = "bad"
        with self.assertRaises(ValueError):
            freeze_case(value)

    def test_invalid_cutoff_rejected(self):
        value = case("synthetic-capacity-expansion")
        with self.assertRaises(ValueError):
            freeze_case(value, "not-a-time")


def _make_source_visibility_test(case_id, source_id, expected):
    def test(self):
        value = case(case_id)
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        self.assertEqual(source_id in {item["source_id"] for item in snapshot["sources"]}, expected)
    return test


for _case_id, _source_id, _expected in [
    ("synthetic-capacity-expansion", "src-demand-v1", True),
    ("synthetic-capacity-expansion", "src-demand-v2", False),
    ("synthetic-capacity-expansion", "src-implementation-observation", False),
    ("synthetic-research-agent-adoption", "src-agent-eval", True),
    ("synthetic-research-agent-adoption", "src-integration-postmortem", False),
    ("synthetic-public-service-pilot", "src-pilot-eval", True),
    ("synthetic-public-service-pilot", "src-pilot-outcome", False),
]:
    setattr(FreezeTests, f"test_visibility_{_case_id}_{_source_id}".replace("-", "_"), _make_source_visibility_test(_case_id, _source_id, _expected))


if __name__ == "__main__":
    unittest.main()
