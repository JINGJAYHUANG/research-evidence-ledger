from __future__ import annotations

import copy
import unittest

from research_evidence_ledger.canonical import digest
from research_evidence_ledger.freeze import freeze_case
from research_evidence_ledger.replay import replay_decision
from helpers import cases, case


EXPECTED = {
    "synthetic-capacity-expansion": "opt-phased",
    "synthetic-research-agent-adoption": "opt-sandbox",
    "synthetic-public-service-pilot": "opt-bounded-pilot",
}


class ReplayTests(unittest.TestCase):
    def replay(self, case_id):
        value = case(case_id)
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        return replay_decision(snapshot)

    def test_expected_selections(self):
        for case_id, expected in EXPECTED.items():
            with self.subTest(case=case_id):
                result = self.replay(case_id)
                self.assertEqual(result["selected_option_id"], expected)
                self.assertTrue(result["recorded_decision_matches_replay"])

    def test_reference_process_levels(self):
        for value in cases():
            result = replay_decision(freeze_case(value, value["decision"]["decision_cutoff"]))
            self.assertEqual(result["process_assessment"]["process_level"], "exemplary")
            self.assertEqual(result["process_assessment"]["failed_hard_gates"], [])

    def test_replay_is_deterministic(self):
        for value in cases():
            snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
            self.assertEqual(replay_decision(snapshot), replay_decision(snapshot))

    def test_replay_fingerprint_changes_with_assessment(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        first = replay_decision(snapshot)
        snapshot["assessments"][0]["scenario_scores"]["base"]["value"] += 1
        snapshot["snapshot_fingerprint"] = digest({k: v for k, v in snapshot.items() if k != "snapshot_fingerprint"})
        second = replay_decision(snapshot)
        self.assertNotEqual(first["replay_fingerprint"], second["replay_fingerprint"])

    def test_confidence_shrinks_toward_neutral(self):
        result = self.replay("synthetic-capacity-expansion")
        option = next(item for item in result["options"] if item["option_id"] == "opt-full")
        detail = option["criterion_details"]["base"]["value"]
        self.assertLess(detail["adjusted"], detail["raw"])
        self.assertGreater(detail["adjusted"], 50)

    def test_regret_is_nonnegative(self):
        for value in cases():
            result = replay_decision(freeze_case(value, value["decision"]["decision_cutoff"]))
            for option in result["options"]:
                self.assertGreaterEqual(option["max_regret"], 0)
                self.assertTrue(all(value >= 0 for value in option["scenario_regret"].values()))

    def test_external_full_rollout_is_ineligible(self):
        result = self.replay("synthetic-public-service-pilot")
        option = next(item for item in result["options"] if item["option_id"] == "opt-full-rollout")
        self.assertFalse(option["eligible"])
        self.assertIn("legal", option["failed_gates"])
        self.assertIn("safety", option["failed_gates"])

    def test_autonomous_agent_is_ineligible(self):
        result = self.replay("synthetic-research-agent-adoption")
        option = next(item for item in result["options"] if item["option_id"] == "opt-autonomous")
        self.assertFalse(option["eligible"])
        self.assertIn("privacy", option["failed_gates"])

    def test_distributional_floor_can_disqualify(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        assessment = next(item for item in snapshot["assessments"] if item["option_id"] == "opt-defer")
        assessment["distributional_scores"]["customers"] = 1
        snapshot["snapshot_fingerprint"] = digest({k: v for k, v in snapshot.items() if k != "snapshot_fingerprint"})
        result = replay_decision(snapshot)
        option = next(item for item in result["options"] if item["option_id"] == "opt-defer")
        self.assertIn("distributional-floor", option["failed_gates"])

    def test_unknown_gate_produces_review_state(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        assessment = next(item for item in snapshot["assessments"] if item["option_id"] == "opt-phased")
        assessment["gates"]["legal"] = "unknown"
        snapshot["snapshot_fingerprint"] = digest({k: v for k, v in snapshot.items() if k != "snapshot_fingerprint"})
        result = replay_decision(snapshot)
        option = next(item for item in result["options"] if item["option_id"] == "opt-phased")
        self.assertEqual(option["decision_state"], "review")

    def test_all_options_ineligible_has_explicit_status(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        for assessment in snapshot["assessments"]:
            assessment["gates"]["legal"] = "fail"
        snapshot["snapshot_fingerprint"] = digest({k: v for k, v in snapshot.items() if k != "snapshot_fingerprint"})
        result = replay_decision(snapshot)
        self.assertEqual(result["selection_status"], "no-fully-eligible-option")

    def test_input_order_does_not_change_selection(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        first = replay_decision(snapshot)
        snapshot["options"] = list(reversed(snapshot["options"]))
        snapshot["assessments"] = list(reversed(snapshot["assessments"]))
        snapshot["scenarios"] = list(reversed(snapshot["scenarios"]))
        snapshot["snapshot_fingerprint"] = digest({k: v for k, v in snapshot.items() if k != "snapshot_fingerprint"})
        second = replay_decision(snapshot)
        self.assertEqual(first["selected_option_id"], second["selected_option_id"])

    def test_later_evidence_flips_agent_choice_under_original_rule(self):
        value = case("synthetic-research-agent-adoption")
        later = freeze_case(value, value["review"]["reviewed_at"])
        result = replay_decision(later, rule_version_id="rule-agent-v1")
        self.assertEqual(result["selected_option_id"], "opt-manual")

    def test_rule_override_can_be_selected_explicitly(self):
        value = case("synthetic-capacity-expansion")
        later = freeze_case(value, value["review"]["reviewed_at"])
        result = replay_decision(later, rule_version_id="rule-robust-v2")
        self.assertEqual(result["rule_version_id"], "rule-robust-v2")

    def test_unknown_rule_rejected(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        with self.assertRaises(ValueError):
            replay_decision(snapshot, rule_version_id="missing")

    def test_tampered_snapshot_rejected(self):
        value = case("synthetic-capacity-expansion")
        snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
        snapshot["title"] += " tampered"
        with self.assertRaises(ValueError):
            replay_decision(snapshot)


def _make_option_metrics_test(case_id, option_id):
    def test(self):
        result = self.replay(case_id)
        option = next(item for item in result["options"] if item["option_id"] == option_id)
        self.assertEqual(set(option["scenario_scores"]), {"base", "upside", "downside", "disruption"})
        self.assertGreaterEqual(option["robust_score"], 0)
        self.assertLessEqual(option["robust_score"], 100)
    return test


for _case in cases():
    for _option in _case["options"]:
        setattr(
            ReplayTests,
            f"test_metrics_{_case['case_id']}_{_option['option_id']}".replace("-", "_"),
            _make_option_metrics_test(_case["case_id"], _option["option_id"]),
        )


if __name__ == "__main__":
    unittest.main()
