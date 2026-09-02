from __future__ import annotations

from collections import defaultdict
from typing import Any

from .canonical import digest
from .io import load_process_rubric
from .timeutil import at_or_before, parse_timestamp
from .validation import assumption_cycle


def _rule_payload(rule: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in rule.items() if key != "rule_digest"}


def _source_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["source_id"]: item for item in snapshot["sources"]}


def _claim_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["claim_id"]: item for item in snapshot["claims"]}


def _timestamp_items(snapshot: dict[str, Any]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for item in snapshot["sources"]:
        result.extend([
            (f"sources.{item['source_id']}.published_at", item["published_at"]),
            (f"sources.{item['source_id']}.observed_at", item["observed_at"]),
        ])
    for item in snapshot["claims"]:
        result.append((f"claims.{item['claim_id']}.recorded_at", item["recorded_at"]))
    for item in snapshot["assumptions"]:
        result.extend([
            (f"assumptions.{item['assumption_id']}.recorded_at", item["recorded_at"]),
            (f"assumptions.{item['assumption_id']}.valid_from", item["valid_from"]),
        ])
    for item in snapshot["forecasts"]:
        result.append((f"forecasts.{item['forecast_id']}.issued_at", item["issued_at"]))
        if item.get("outcome"):
            result.append((f"forecasts.{item['forecast_id']}.outcome.observed_at", item["outcome"]["observed_at"]))
    for item in snapshot["assessments"]:
        result.append((f"assessments.{item['assessment_id']}.recorded_at", item["recorded_at"]))
    for item in snapshot["decision_rules"]:
        result.extend([
            (f"decision_rules.{item['rule_version_id']}.recorded_at", item["recorded_at"]),
            (f"decision_rules.{item['rule_version_id']}.effective_from", item["effective_from"]),
        ])
    for item in snapshot["outcomes"]:
        result.append((f"outcomes.{item['outcome_id']}.observed_at", item["observed_at"]))
    if snapshot.get("review"):
        result.append(("review.reviewed_at", snapshot["review"]["reviewed_at"]))
    if snapshot.get("decision"):
        result.extend([
            ("decision.recorded_at", snapshot["decision"]["recorded_at"]),
            ("decision.rationale_recorded_at", snapshot["decision"]["rationale_recorded_at"]),
        ])
    return result


def assess_process(snapshot: dict[str, Any], rubric: dict[str, Any] | None = None) -> dict[str, Any]:
    rubric = rubric or load_process_rubric()
    cutoff = snapshot["cutoff"]
    sources = _source_map(snapshot)
    claims = _claim_map(snapshot)
    decision = snapshot.get("decision")
    active_source_ids = set(snapshot.get("active_source_ids", {}).values())
    active_assessment_ids = set(snapshot.get("active_assessment_ids", {}).values())

    gate_details: dict[str, dict[str, Any]] = {}

    future_items = [path for path, timestamp in _timestamp_items(snapshot) if not at_or_before(timestamp, cutoff)]
    missing_rationale_sources = []
    if decision:
        missing_rationale_sources = [source_id for source_id in decision.get("rationale_source_ids", []) if source_id not in sources]
    gate_details["no-future-information"] = {
        "status": "pass" if not future_items and not missing_rationale_sources else "fail",
        "details": future_items + [f"decision rationale source unavailable at cutoff: {item}" for item in missing_rationale_sources],
    }

    stale_vintages: list[str] = []
    if decision:
        for source_id in decision.get("rationale_source_ids", []):
            source = sources.get(source_id)
            if source and source_id not in active_source_ids:
                stale_vintages.append(f"decision rationale uses superseded known vintage {source_id}")
    for claim in claims.values():
        if not claim.get("used_for_decision"):
            continue
        for source_id in claim.get("support_source_ids", []):
            if source_id in sources and source_id not in active_source_ids:
                stale_vintages.append(f"claim {claim['claim_id']} uses superseded known vintage {source_id}")
    gate_details["vintage-integrity"] = {
        "status": "pass" if not stale_vintages else "fail",
        "details": stale_vintages,
    }

    rule_failures: list[str] = []
    if not decision:
        rule_failures.append("decision unavailable at cutoff")
    else:
        rule = next((item for item in snapshot["decision_rules"] if item["rule_version_id"] == decision.get("rule_version_id")), None)
        if rule is None:
            rule_failures.append("recorded rule version unavailable at cutoff")
        else:
            actual = digest(_rule_payload(rule))
            if rule.get("rule_digest") != actual:
                rule_failures.append("rule self-digest mismatch")
            if decision.get("rule_digest") != actual:
                rule_failures.append("decision does not bind the recorded rule digest")
            if parse_timestamp(rule["recorded_at"]) > parse_timestamp(decision["decision_cutoff"]):
                rule_failures.append("rule was recorded after the decision cutoff")
    gate_details["rule-immutability"] = {
        "status": "pass" if not rule_failures else "fail",
        "details": rule_failures,
    }

    approval_failures: list[str] = []
    if decision:
        required = set(decision.get("required_approval_roles", []))
        present = set(decision.get("approval_roles", []))
        missing = sorted(required - present)
        if missing:
            approval_failures.append("missing approval roles: " + ", ".join(missing))
    else:
        approval_failures.append("decision unavailable at cutoff")
    gate_details["approval-integrity"] = {
        "status": "pass" if not approval_failures else "fail",
        "details": approval_failures,
    }

    action_failures: list[str] = []
    if decision:
        action = decision.get("action", {})
        if action.get("external") and action.get("executed"):
            receipt = action.get("execution_receipt")
            if not isinstance(receipt, dict):
                action_failures.append("external action reported executed without execution receipt")
            else:
                if receipt.get("approved") is not True:
                    action_failures.append("execution receipt is not approved")
                if receipt.get("decision_id") != decision.get("decision_id"):
                    action_failures.append("execution receipt is bound to another decision")
                required = set(decision.get("required_approval_roles", []))
                if not required.issubset(set(decision.get("approval_roles", []))):
                    action_failures.append("external action executed without complete approvals")
    gate_details["external-action-safety"] = {
        "status": "pass" if not action_failures else "fail",
        "details": action_failures,
    }

    cycle = assumption_cycle(snapshot["assumptions"])
    gate_details["graph-integrity"] = {
        "status": "pass" if cycle is None else "fail",
        "details": [] if cycle is None else ["assumption dependency cycle: " + " -> ".join(cycle)],
    }

    corroboration_failures: list[str] = []
    for claim in claims.values():
        if not claim.get("used_for_decision") or claim.get("certainty") != "confirmed" or claim.get("consequence") not in {"high", "critical"}:
            continue
        groups = {
            sources[source_id]["independence_group"]
            for source_id in claim.get("support_source_ids", [])
            if source_id in sources
        }
        if len(groups) < 2:
            corroboration_failures.append(
                f"claim {claim['claim_id']} has {len(groups)} independent support group(s); at least 2 required"
            )
    gate_details["high-consequence-corroboration"] = {
        "status": "pass" if not corroboration_failures else "fail",
        "details": corroboration_failures,
    }

    rationale_failures: list[str] = []
    if not decision:
        rationale_failures.append("decision unavailable at cutoff")
    elif not at_or_before(decision["rationale_recorded_at"], decision["decision_cutoff"]):
        rationale_failures.append("rationale was recorded after the decision cutoff")
    gate_details["hindsight-rationale-boundary"] = {
        "status": "pass" if not rationale_failures else "fail",
        "details": rationale_failures,
    }

    # Dimension checks. Each check is deliberately inspectable rather than model-judged.
    source_hashes = all(item.get("content_hash", "").startswith("sha256:") for item in sources.values())
    source_identity = all(item.get("publisher") and item.get("title") and item.get("lineage_id") for item in sources.values())
    access_rights = all(item.get("access_class") and item.get("license") for item in sources.values())
    independence_declared = all(item.get("independence_group") for item in sources.values())
    claim_support = all(
        (claim.get("support_source_ids") or claim.get("claim_type") in {"scenario", "scope-finding"})
        for claim in claims.values()
        if claim.get("used_for_decision")
    )
    certainty_boundaries = all(
        not (claim.get("claim_type") in {"inference", "forecast", "scenario"} and claim.get("certainty") == "confirmed")
        for claim in claims.values()
    )
    not_proven = all(bool(claim.get("not_proven")) for claim in claims.values() if claim.get("used_for_decision"))
    assumption_ranges = all(
        item["value"]["low"] <= item["value"]["base"] <= item["value"]["high"]
        for item in snapshot["assumptions"]
    )
    forecast_intervals = all(
        item["interval"]["lower"] <= item["interval"]["point"] <= item["interval"]["upper"]
        for item in snapshot["forecasts"]
    )
    scenario_probabilities = abs(sum(float(item["probability"]) for item in snapshot["scenarios"]) - 1.0) <= 1e-9
    confidence_explicit = all("confidence" in item for item in snapshot["assumptions"]) and all(
        bool(item.get("criterion_confidence")) for item in snapshot["assessments"]
    )
    status_quo = any(item.get("is_status_quo") for item in snapshot["options"])
    reversible = any(item.get("reversible") for item in snapshot["options"])
    assessment_coverage = {item["option_id"] for item in snapshot["assessments"]} == {item["option_id"] for item in snapshot["options"]} and len(active_assessment_ids) == len(snapshot["options"])
    distributional_scores = all(bool(item.get("distributional_scores")) for item in snapshot["assessments"])
    active_rule = None
    if decision:
        active_rule = next((item for item in snapshot["decision_rules"] if item["rule_version_id"] == decision.get("rule_version_id")), None)
    weights_normalized = bool(active_rule) and abs(sum(active_rule["criteria_weights"].values()) - 1.0) <= 1e-9
    robust_normalized = bool(active_rule) and abs(sum(active_rule["robust_weights"].values()) - 1.0) <= 1e-9
    tie_break = bool(active_rule and active_rule.get("tie_break"))
    rule_locked = gate_details["rule-immutability"]["status"] == "pass"
    approvals_complete = gate_details["approval-integrity"]["status"] == "pass"
    action_boundary = gate_details["external-action-safety"]["status"] == "pass"
    override_documented = not decision or not decision.get("override") or all(
        decision["override"].get(key) for key in ("reason", "recorded_at", "approved_by")
    )
    groups_declared = all(bool(item.get("distributional_scores")) for item in snapshot["assessments"])
    floor_enforced = bool(active_rule and isinstance(active_rule.get("distributional_floor"), (int, float)))
    assumption_falsifiers = all(bool(item.get("falsifiers")) for item in snapshot["assumptions"])
    monitors_assigned = all(bool(item.get("monitor", {}).get("owner")) for item in snapshot["assumptions"])
    review_timely = snapshot.get("review") is not None
    learning_actions = bool(snapshot.get("review", {}).get("learning_actions")) if snapshot.get("review") else False

    check_values = {
        "cutoff-complete": bool(decision and decision.get("decision_cutoff") == cutoff),
        "no-future-evidence": gate_details["no-future-information"]["status"] == "pass",
        "correct-vintage": gate_details["vintage-integrity"]["status"] == "pass",
        "rationale-timely": gate_details["hindsight-rationale-boundary"]["status"] == "pass",
        "source-identity": source_identity,
        "content-hashes": source_hashes,
        "access-rights": access_rights,
        "independence-groups": independence_declared,
        "claim-support": claim_support,
        "consequence-corroboration": gate_details["high-consequence-corroboration"]["status"] == "pass",
        "certainty-boundary": certainty_boundaries,
        "not-proven-boundary": not_proven,
        "assumption-ranges": assumption_ranges,
        "forecast-intervals": forecast_intervals,
        "scenario-probabilities": scenario_probabilities,
        "confidence-explicit": confidence_explicit,
        "status-quo-option": status_quo,
        "reversible-option": reversible,
        "assessment-coverage": assessment_coverage,
        "distributional-scores": distributional_scores,
        "weights-normalized": weights_normalized,
        "robust-weights-normalized": robust_normalized,
        "tie-break-explicit": tie_break,
        "rule-locked": rule_locked,
        "approvals-complete": approvals_complete,
        "external-action-boundary": action_boundary,
        "override-documented": override_documented,
        "groups-declared": groups_declared,
        "floor-enforced": floor_enforced,
        "assumption-falsifiers": assumption_falsifiers,
        "monitors-assigned": monitors_assigned,
        "review-timely": review_timely,
        "learning-actions": learning_actions,
    }

    dimensions = []
    score = 0.0
    for dimension in rubric["dimensions"]:
        checks = [{"id": check_id, "passed": bool(check_values.get(check_id, False))} for check_id in dimension["checks"]]
        fraction = sum(item["passed"] for item in checks) / len(checks)
        earned = dimension["weight"] * fraction
        score += earned
        dimensions.append({
            "dimension_id": dimension["id"],
            "weight": dimension["weight"],
            "earned": round(earned, 4),
            "score": round(fraction * 100, 2),
            "checks": checks,
        })

    failed_gates = [gate_id for gate_id, value in gate_details.items() if value["status"] == "fail"]
    process_level = "unsafe"
    if not failed_gates:
        for level in rubric["process_levels"]:
            if level["label"] == "unsafe":
                continue
            if score >= level["minimum_score"]:
                process_level = level["label"]
                break

    return {
        "schema_version": 1,
        "case_id": snapshot["case_id"],
        "cutoff": cutoff,
        "snapshot_fingerprint": snapshot["snapshot_fingerprint"],
        "process_score": round(score, 2),
        "process_level": process_level,
        "hard_gates": gate_details,
        "failed_hard_gates": failed_gates,
        "dimensions": dimensions,
        "check_values": dict(sorted(check_values.items())),
        "claim_boundary": (
            "The score describes the completeness and integrity of this synthetic decision record. "
            "It is not a certification that the decision was correct or that a real system is safe."
        ),
    }
