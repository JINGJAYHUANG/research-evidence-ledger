from __future__ import annotations

import copy
import unittest

from research_evidence_ledger.canonical import digest
from research_evidence_ledger.validation import validate_case, validate_snapshot
from research_evidence_ledger.freeze import freeze_case
from helpers import cases, case


class ReferenceValidationTests(unittest.TestCase):
    def test_all_reference_cases_strictly_valid(self):
        for value in cases():
            with self.subTest(case=value["case_id"]):
                report = validate_case(value, strict=True)
                self.assertTrue(report.ok, report.as_dict())

    def test_all_decision_snapshots_valid(self):
        for value in cases():
            with self.subTest(case=value["case_id"]):
                snapshot = freeze_case(value, value["decision"]["decision_cutoff"])
                self.assertTrue(validate_snapshot(snapshot, strict=True).ok)

    def test_public_boundary_is_safe(self):
        for value in cases():
            boundary = value["public_boundary"]
            self.assertTrue(boundary["synthetic_only"])
            self.assertFalse(boundary["contains_personal_data"])
            self.assertFalse(boundary["contains_credentials"])
            self.assertFalse(boundary["external_actions_enabled"])

    def test_reference_ids_unique(self):
        for value in cases():
            for key, id_key in [
                ("sources", "source_id"), ("claims", "claim_id"),
                ("assumptions", "assumption_id"), ("forecasts", "forecast_id"),
                ("options", "option_id"), ("assessments", "assessment_id"),
                ("decision_rules", "rule_version_id"), ("outcomes", "outcome_id"),
            ]:
                ids = [item[id_key] for item in value[key]]
                with self.subTest(case=value["case_id"], collection=key):
                    self.assertEqual(len(ids), len(set(ids)))


class MutationValidationTests(unittest.TestCase):
    def setUp(self):
        self.value = case("synthetic-capacity-expansion")

    def assert_code(self, value, code, *, strict=False):
        report = validate_case(value, strict=strict)
        self.assertIn(code, {item.code for item in report.findings}, report.as_dict())

    def test_bad_schema_version(self):
        self.value["schema_version"] = 2
        self.assert_code(self.value, "schema-version")

    def test_bad_case_id(self):
        self.value["case_id"] = "Bad ID"
        self.assert_code(self.value, "case-id")

    def test_short_title(self):
        self.value["title"] = "short"
        self.assert_code(self.value, "title")

    def test_non_synthetic_boundary(self):
        self.value["public_boundary"]["synthetic_only"] = False
        self.assert_code(self.value, "synthetic-only")

    def test_personal_data_boundary(self):
        self.value["public_boundary"]["contains_personal_data"] = True
        self.assert_code(self.value, "unsafe-public-boundary")

    def test_duplicate_source(self):
        self.value["sources"].append(copy.deepcopy(self.value["sources"][0]))
        self.assert_code(self.value, "duplicate-id")

    def test_bad_source_hash(self):
        self.value["sources"][0]["summary"] += " changed"
        self.assert_code(self.value, "source-hash")

    def test_unknown_source_type(self):
        source = self.value["sources"][0]
        source["source_type"] = "social-rumor"
        source["content_hash"] = digest({k: v for k, v in source.items() if k != "content_hash"})
        self.assert_code(self.value, "source-type")

    def test_unknown_claim_source(self):
        self.value["claims"][0]["support_source_ids"].append("missing-source")
        self.assert_code(self.value, "unknown-reference")

    def test_inference_cannot_be_confirmed(self):
        claim = self.value["claims"][0]
        claim["claim_type"] = "inference"
        claim["certainty"] = "confirmed"
        self.assert_code(self.value, "certainty-overclaim")

    def test_missing_not_proven_is_warning(self):
        self.value["claims"][0]["not_proven"] = []
        report = validate_case(self.value)
        self.assertTrue(report.ok)
        self.assertIn("not-proven-boundary", {item.code for item in report.findings})
        self.assertFalse(validate_case(self.value, strict=True).ok)

    def test_assumption_unknown_dependency(self):
        self.value["assumptions"][0]["dependencies"] = ["missing"]
        self.assert_code(self.value, "unknown-reference")

    def test_assumption_range_order(self):
        self.value["assumptions"][0]["value"] = {"low": 2, "base": 1, "high": 3, "unit": "x"}
        self.assert_code(self.value, "assumption-order")

    def test_assumption_confidence_bounds(self):
        self.value["assumptions"][0]["confidence"] = 1.2
        self.assert_code(self.value, "assumption-confidence")

    def test_forecast_interval_order(self):
        self.value["forecasts"][0]["interval"]["lower"] = 99
        self.assert_code(self.value, "forecast-order")

    def test_forecast_probabilities_sum(self):
        self.value["forecasts"][0]["probabilities"] = {"a": 0.2, "b": 0.2}
        self.assert_code(self.value, "weight-sum")

    def test_scenario_probabilities_sum(self):
        self.value["scenarios"][0]["probability"] = 0.10
        self.assert_code(self.value, "weight-sum")

    def test_requires_one_base_scenario(self):
        for item in self.value["scenarios"]:
            item["is_base"] = False
        self.assert_code(self.value, "base-scenario")

    def test_assessment_unknown_option(self):
        self.value["assessments"][0]["option_id"] = "missing"
        self.assert_code(self.value, "assessment-option")

    def test_assessment_must_cover_scenarios(self):
        self.value["assessments"][0]["scenario_scores"].pop("base")
        self.assert_code(self.value, "assessment-scenarios")

    def test_criterion_score_bounds(self):
        self.value["assessments"][0]["scenario_scores"]["base"]["value"] = 101
        self.assert_code(self.value, "criterion-score")

    def test_gate_state(self):
        self.value["assessments"][0]["gates"]["legal"] = "maybe"
        self.assert_code(self.value, "gate-state")

    def test_missing_distributional_scores(self):
        self.value["assessments"][0]["distributional_scores"] = {}
        self.assert_code(self.value, "distributional-scores")

    def test_rule_weight_sum(self):
        self.value["decision_rules"][0]["criteria_weights"]["value"] = 0.9
        self.assert_code(self.value, "weight-sum")

    def test_rule_digest(self):
        self.value["decision_rules"][0]["rule_digest"] = "sha256:" + "0" * 64
        self.assert_code(self.value, "rule-digest")

    def test_unknown_decision_option(self):
        self.value["decision"]["selected_option_id"] = "missing"
        self.assert_code(self.value, "decision-option")

    def test_unknown_outcome_scenario(self):
        self.value["outcomes"][0]["realized_scenario_id"] = "missing"
        self.assert_code(self.value, "outcome-scenario")

    def test_outcome_must_cover_options(self):
        self.value["outcomes"][0]["option_utilities"].pop("opt-defer")
        self.assert_code(self.value, "outcome-utilities")

    def test_naive_timestamp(self):
        source = self.value["sources"][0]
        source["observed_at"] = "2026-01-01T00:00:00"
        source["content_hash"] = digest({k: v for k, v in source.items() if k != "content_hash"})
        self.assert_code(self.value, "timestamp")

    def test_snapshot_fingerprint_detects_change(self):
        snapshot = freeze_case(self.value, self.value["decision"]["decision_cutoff"])
        snapshot["title"] += " changed"
        report = validate_snapshot(snapshot)
        self.assertIn("snapshot-fingerprint", {item.code for item in report.findings})


if __name__ == "__main__":
    unittest.main()
