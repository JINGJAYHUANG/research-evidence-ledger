from __future__ import annotations

import unittest

from research_evidence_ledger.freeze import freeze_case
from research_evidence_ledger.process import assess_process
from helpers import cases, mutants


class ProcessTests(unittest.TestCase):
    def test_reference_cases_have_no_failed_gates(self):
        for value in cases():
            snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
            process = assess_process(snapshot)
            self.assertEqual(process["failed_hard_gates"], [])
            self.assertEqual(process["process_level"], "exemplary")
            self.assertEqual(process["process_score"], 96.0)

    def test_mutants_fail_exact_expected_gates(self):
        for value in mutants():
            with self.subTest(mutant=value["case_id"]):
                snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
                process = assess_process(snapshot)
                self.assertEqual(sorted(process["failed_hard_gates"]), sorted(value["expected_failed_hard_gates"]))
                self.assertEqual(process["process_level"], "unsafe")

    def test_dimension_weights_sum_to_100(self):
        value = cases()[0]
        process = assess_process(freeze_case(value, value["decision"]["decision_cutoff"]))
        self.assertEqual(sum(item["weight"] for item in process["dimensions"]), 100)

    def test_dimension_scores_bounded(self):
        value = cases()[0]
        process = assess_process(freeze_case(value, value["decision"]["decision_cutoff"]))
        for item in process["dimensions"]:
            self.assertGreaterEqual(item["score"], 0)
            self.assertLessEqual(item["score"], 100)
            self.assertGreaterEqual(item["earned"], 0)
            self.assertLessEqual(item["earned"], item["weight"])

    def test_claim_boundary_is_conservative(self):
        value = cases()[0]
        process = assess_process(freeze_case(value, value["decision"]["decision_cutoff"]))
        self.assertIn("not a certification", process["claim_boundary"])


def _make_mutant_test(mutant_value):
    def test(self):
        snapshot = freeze_case(mutant_value, mutant_value["decision"]["decision_cutoff"])
        process = assess_process(snapshot)
        for expected in mutant_value["expected_failed_hard_gates"]:
            self.assertEqual(process["hard_gates"][expected]["status"], "fail")
            self.assertTrue(process["hard_gates"][expected]["details"])
    return test


for _mutant in mutants():
    setattr(ProcessTests, f"test_mutant_{_mutant['case_id']}".replace("-", "_"), _make_mutant_test(_mutant))


if __name__ == "__main__":
    unittest.main()
