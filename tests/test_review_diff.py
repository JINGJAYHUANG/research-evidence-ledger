from __future__ import annotations

import copy
import unittest

from research_evidence_ledger.diffing import compare_snapshots
from research_evidence_ledger.freeze import freeze_case
from research_evidence_ledger.review import review_decision
from helpers import cases, case


EXPECTED_QUADRANTS = {
    "synthetic-capacity-expansion": "sound-and-fortunate",
    "synthetic-public-service-pilot": "sound-and-fortunate",
    "synthetic-research-agent-adoption": "sound-but-unlucky",
}


class ReviewTests(unittest.TestCase):
    def test_expected_quadrants(self):
        for case_id, quadrant in EXPECTED_QUADRANTS.items():
            with self.subTest(case=case_id):
                self.assertEqual(review_decision(case(case_id))["decision_quality_quadrant"], quadrant)

    def test_agent_case_regret(self):
        review = review_decision(case("synthetic-research-agent-adoption"))
        self.assertEqual(review["selected_option_id"], "opt-sandbox")
        self.assertEqual(review["best_ex_post_option_id"], "opt-manual")
        self.assertEqual(review["ex_post_regret"], 24.0)

    def test_fortunate_cases_have_zero_regret(self):
        for case_id in ("synthetic-capacity-expansion", "synthetic-public-service-pilot"):
            self.assertEqual(review_decision(case(case_id))["ex_post_regret"], 0.0)

    def test_forecast_metrics(self):
        for value in cases():
            review = review_decision(value)
            metrics = review["forecast_evaluation"]
            self.assertEqual(metrics["evaluated_forecast_count"], 1)
            self.assertEqual(metrics["interval_coverage"], 1.0)
            self.assertIsNotNone(metrics["mean_squared_error"])
            self.assertIsNotNone(metrics["multiclass_brier_score"])

    def test_learning_actions_are_assigned(self):
        for value in cases():
            review = review_decision(value)
            self.assertTrue(review["learning_completeness"]["learning_actions_assigned"])

    def test_rule_changes_are_prospective(self):
        for value in cases():
            review = review_decision(value)
            self.assertTrue(review["learning_completeness"]["rule_changes_prospective"])

    def test_review_before_outcome_rejected(self):
        value = case("synthetic-capacity-expansion")
        with self.assertRaises(ValueError):
            review_decision(value, review_cutoff="2026-04-01T00:00:00Z")

    def test_review_deterministic(self):
        for value in cases():
            self.assertEqual(review_decision(value), review_decision(value))


class DiffTests(unittest.TestCase):
    def compare(self, case_id):
        value = case(case_id)
        before = freeze_case(value, value["decision"]["decision_cutoff"])
        after = freeze_case(value, value["review"]["reviewed_at"])
        return compare_snapshots(before, after)

    def test_agent_evidence_flip(self):
        result = self.compare("synthetic-research-agent-adoption")
        self.assertTrue(result["decision_flip_with_new_evidence_same_rule"])
        self.assertFalse(result["decision_flip_from_rule_change"])

    def test_capacity_no_flip(self):
        result = self.compare("synthetic-capacity-expansion")
        self.assertFalse(result["decision_flip_with_new_evidence_same_rule"])
        self.assertFalse(result["decision_flip_from_rule_change"])

    def test_new_sources_detected(self):
        result = self.compare("synthetic-capacity-expansion")
        self.assertIn("src-demand-v2", result["changes"]["sources"]["added"])
        self.assertIn("src-implementation-observation", result["changes"]["sources"]["added"])

    def test_new_assumption_detected(self):
        result = self.compare("synthetic-capacity-expansion")
        self.assertIn("asm-demand-v2", result["changes"]["assumptions"]["added"])

    def test_new_rule_detected(self):
        result = self.compare("synthetic-capacity-expansion")
        self.assertIn("rule-robust-v2", result["changes"]["decision_rules"]["added"])

    def test_diff_is_deterministic(self):
        value = case("synthetic-capacity-expansion")
        before = freeze_case(value, value["decision"]["decision_cutoff"])
        after = freeze_case(value, value["review"]["reviewed_at"])
        self.assertEqual(compare_snapshots(before, after), compare_snapshots(before, after))

    def test_cross_case_rejected(self):
        left = case("synthetic-capacity-expansion")
        right = case("synthetic-public-service-pilot")
        with self.assertRaises(ValueError):
            compare_snapshots(freeze_case(left, left["decision"]["decision_cutoff"]), freeze_case(right, right["review"]["reviewed_at"]))

    def test_reverse_time_rejected(self):
        value = case("synthetic-capacity-expansion")
        before = freeze_case(value, value["decision"]["decision_cutoff"])
        after = freeze_case(value, value["review"]["reviewed_at"])
        with self.assertRaises(ValueError):
            compare_snapshots(after, before)


if __name__ == "__main__":
    unittest.main()
