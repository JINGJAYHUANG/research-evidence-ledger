from __future__ import annotations

from collections import defaultdict
from typing import Any

from .canonical import digest
from .process import assess_process
from .validation import validate_snapshot


def _adjust(raw: float, confidence: float) -> float:
    return 50.0 + confidence * (raw - 50.0)


def _active_rule(snapshot: dict[str, Any], rule_version_id: str | None = None) -> dict[str, Any]:
    decision = snapshot.get("decision") or {}
    requested = rule_version_id or decision.get("rule_version_id")
    if requested:
        for rule in snapshot["decision_rules"]:
            if rule["rule_version_id"] == requested:
                return rule
        raise ValueError(f"requested rule version is unavailable in snapshot: {requested}")
    if not snapshot["decision_rules"]:
        raise ValueError("snapshot has no active decision rule")
    return max(snapshot["decision_rules"], key=lambda item: (item["recorded_at"], item["rule_version_id"]))


def replay_decision(snapshot: dict[str, Any], *, rule_version_id: str | None = None) -> dict[str, Any]:
    validation = validate_snapshot(snapshot)
    if not validation.ok:
        detail = "; ".join(f"{item.code}@{item.path}" for item in validation.findings)
        raise ValueError(f"snapshot validation failed: {detail}")
    rule = _active_rule(snapshot, rule_version_id)
    criteria = list(rule["criteria_weights"])
    scenarios = {item["scenario_id"]: item for item in snapshot["scenarios"]}
    base_scenario = next(item["scenario_id"] for item in snapshot["scenarios"] if item.get("is_base"))
    assessments = {item["option_id"]: item for item in snapshot["assessments"]}
    options = {item["option_id"]: item for item in snapshot["options"]}

    option_results: dict[str, dict[str, Any]] = {}
    scenario_best: dict[str, float] = defaultdict(lambda: float("-inf"))
    for option_id in sorted(options):
        assessment = assessments[option_id]
        scenario_scores: dict[str, float] = {}
        criterion_details: dict[str, dict[str, dict[str, float]]] = {}
        for scenario_id in scenarios:
            criterion_details[scenario_id] = {}
            total = 0.0
            for criterion in criteria:
                raw = float(assessment["scenario_scores"][scenario_id][criterion])
                confidence = float(assessment["criterion_confidence"][criterion])
                adjusted = _adjust(raw, confidence)
                weighted = adjusted * float(rule["criteria_weights"][criterion])
                total += weighted
                criterion_details[scenario_id][criterion] = {
                    "raw": round(raw, 4),
                    "confidence": round(confidence, 4),
                    "adjusted": round(adjusted, 4),
                    "weighted": round(weighted, 4),
                }
            scenario_scores[scenario_id] = round(total, 4)
            scenario_best[scenario_id] = max(scenario_best[scenario_id], total)

        expected = sum(float(scenarios[scenario_id]["probability"]) * score for scenario_id, score in scenario_scores.items())
        worst = min(scenario_scores.values())
        base = scenario_scores[base_scenario]
        required_gates = {gate_id: assessment["gates"].get(gate_id, "unknown") for gate_id in rule["hard_gate_ids"]}
        failed_gates = sorted(gate_id for gate_id, status in required_gates.items() if status == "fail")
        unknown_gates = sorted(gate_id for gate_id, status in required_gates.items() if status == "unknown")
        minimum_group_score = min(float(value) for value in assessment["distributional_scores"].values())
        if minimum_group_score < float(rule["distributional_floor"]):
            failed_gates.append("distributional-floor")
        option_results[option_id] = {
            "option_id": option_id,
            "title": options[option_id]["title"],
            "scenario_scores": scenario_scores,
            "criterion_details": criterion_details,
            "base_score": round(base, 4),
            "expected_score": round(expected, 4),
            "worst_score": round(worst, 4),
            "required_gates": required_gates,
            "failed_gates": sorted(set(failed_gates)),
            "unknown_gates": unknown_gates,
            "minimum_distributional_score": round(minimum_group_score, 4),
            "reversible": options[option_id]["reversible"],
            "external_action": options[option_id]["external_action"],
        }

    for option_id, result in option_results.items():
        regrets = {
            scenario_id: round(scenario_best[scenario_id] - result["scenario_scores"][scenario_id], 4)
            for scenario_id in scenarios
        }
        max_regret = max(regrets.values())
        robust = (
            float(rule["robust_weights"]["base"]) * result["base_score"]
            + float(rule["robust_weights"]["expected"]) * result["expected_score"]
            + float(rule["robust_weights"]["worst"]) * result["worst_score"]
            + float(rule["robust_weights"]["regret"]) * (100.0 - max_regret)
        )
        result["scenario_regret"] = regrets
        result["max_regret"] = round(max_regret, 4)
        result["robust_score"] = round(robust, 4)
        result["eligible"] = not result["failed_gates"]
        result["decision_state"] = "review" if result["eligible"] and result["unknown_gates"] else "eligible" if result["eligible"] else "ineligible"

    eligible = [value for value in option_results.values() if value["eligible"]]
    if not eligible:
        candidates = sorted(
            option_results.values(),
            key=lambda item: (len(item["failed_gates"]), -item["robust_score"], item["option_id"]),
        )
        selected = candidates[0]
        selection_status = "no-fully-eligible-option"
    else:
        selected = sorted(
            eligible,
            key=lambda item: (
                item["decision_state"] != "eligible",
                -item["robust_score"],
                -item["worst_score"],
                item["max_regret"],
                item["option_id"],
            ),
        )[0]
        selection_status = "review-required" if selected["decision_state"] == "review" else "selected"

    process = assess_process(snapshot)
    recorded = snapshot.get("decision")
    recorded_match = None if not recorded else recorded.get("selected_option_id") == selected["option_id"]
    override = None if not recorded else recorded.get("override")
    replay: dict[str, Any] = {
        "schema_version": 1,
        "case_id": snapshot["case_id"],
        "cutoff": snapshot["cutoff"],
        "snapshot_fingerprint": snapshot["snapshot_fingerprint"],
        "rule_version_id": rule["rule_version_id"],
        "rule_digest": rule["rule_digest"],
        "selection_status": selection_status,
        "selected_option_id": selected["option_id"],
        "recorded_option_id": recorded.get("selected_option_id") if recorded else None,
        "recorded_decision_matches_replay": recorded_match,
        "recorded_override": override,
        "options": [option_results[key] for key in sorted(option_results)],
        "process_assessment": process,
        "claim_boundary": (
            "This replay reconstructs the stated synthetic decision rule using information in the frozen snapshot. "
            "It does not prove the selected option was objectively best or suitable for a real decision."
        ),
    }
    replay["replay_fingerprint"] = digest(replay)
    return replay
