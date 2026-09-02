from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from .canonical import digest
from .models import Finding, ValidationReport
from .timeutil import parse_timestamp

ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
LEVELS = {"low", "medium", "high", "critical"}
CERTAINTY = {"confirmed", "inferred", "conditional", "unknown"}
CLAIM_TYPES = {"fact", "inference", "forecast", "scenario", "policy", "decision", "scope-finding"}
SOURCE_TYPES = {"synthetic-record", "official-record", "research", "observation", "model-output", "other"}
GATE_STATES = {"pass", "fail", "unknown", "not-applicable"}


def _add(findings: list[Finding], severity: str, code: str, path: str, message: str) -> None:
    findings.append(Finding(severity, code, path, message))


def _timestamp(findings: list[Finding], value: Any, path: str, *, required: bool = True) -> None:
    if value is None and not required:
        return
    try:
        parse_timestamp(value)
    except (TypeError, ValueError) as exc:
        _add(findings, "error", "timestamp", path, str(exc))


def _unique_ids(items: Any, id_key: str, path: str, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(items, list):
        _add(findings, "error", "array", path, "must be an array")
        return result
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            _add(findings, "error", "object", item_path, "must be an object")
            continue
        item_id = item.get(id_key)
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            _add(findings, "error", "id", f"{item_path}.{id_key}", "must be a stable lowercase identifier")
            continue
        if item_id in result:
            _add(findings, "error", "duplicate-id", f"{item_path}.{id_key}", f"duplicate id {item_id}")
        result[item_id] = item
    return result


def _sum_to_one(mapping: Any, path: str, findings: list[Finding]) -> None:
    if not isinstance(mapping, dict) or not mapping:
        _add(findings, "error", "weights", path, "must be a non-empty object")
        return
    total = 0.0
    for key, value in mapping.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            _add(findings, "error", "weight", f"{path}.{key}", "must be a non-negative number")
        else:
            total += float(value)
    if abs(total - 1.0) > 1e-9:
        _add(findings, "error", "weight-sum", path, f"weights must sum to 1, found {total:.12g}")


def _check_refs(values: Any, allowed: set[str], path: str, findings: list[Finding]) -> None:
    if not isinstance(values, list):
        _add(findings, "error", "reference-array", path, "must be an array")
        return
    for index, value in enumerate(values):
        if value not in allowed:
            _add(findings, "error", "unknown-reference", f"{path}[{index}]", f"unknown reference {value!r}")


def _rule_payload(rule: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in rule.items() if key != "rule_digest"}


def validate_case(case: dict[str, Any], *, strict: bool = False) -> ValidationReport:
    findings: list[Finding] = []
    if case.get("schema_version") != 1:
        _add(findings, "error", "schema-version", "schema_version", "must be 1")
    if not isinstance(case.get("case_id"), str) or not ID_RE.fullmatch(case["case_id"]):
        _add(findings, "error", "case-id", "case_id", "must be a stable lowercase identifier")
    if not isinstance(case.get("title"), str) or len(case["title"].strip()) < 8:
        _add(findings, "error", "title", "title", "must be meaningful text")

    boundary = case.get("public_boundary")
    if not isinstance(boundary, dict):
        _add(findings, "error", "public-boundary", "public_boundary", "must be an object")
    else:
        for key in ("synthetic_only", "contains_personal_data", "contains_credentials", "external_actions_enabled"):
            if not isinstance(boundary.get(key), bool):
                _add(findings, "error", "public-boundary-field", f"public_boundary.{key}", "must be boolean")
        if boundary.get("synthetic_only") is not True:
            _add(findings, "error", "synthetic-only", "public_boundary.synthetic_only", "public examples must be synthetic-only")
        for key in ("contains_personal_data", "contains_credentials", "external_actions_enabled"):
            if boundary.get(key) is not False:
                _add(findings, "error", "unsafe-public-boundary", f"public_boundary.{key}", "must remain false")

    sources = _unique_ids(case.get("sources"), "source_id", "sources", findings)
    claims = _unique_ids(case.get("claims"), "claim_id", "claims", findings)
    assumptions = _unique_ids(case.get("assumptions"), "assumption_id", "assumptions", findings)
    forecasts = _unique_ids(case.get("forecasts"), "forecast_id", "forecasts", findings)
    options = _unique_ids(case.get("options"), "option_id", "options", findings)
    assessments = _unique_ids(case.get("assessments"), "assessment_id", "assessments", findings)
    rules = _unique_ids(case.get("decision_rules"), "rule_version_id", "decision_rules", findings)
    outcomes = _unique_ids(case.get("outcomes"), "outcome_id", "outcomes", findings)

    scenario_items = case.get("scenarios")
    scenarios = _unique_ids(scenario_items, "scenario_id", "scenarios", findings)
    if scenarios:
        probs = {key: value.get("probability") for key, value in scenarios.items()}
        _sum_to_one(probs, "scenarios.probabilities", findings)
        base_count = sum(bool(item.get("is_base")) for item in scenarios.values())
        if base_count != 1:
            _add(findings, "error", "base-scenario", "scenarios", f"exactly one base scenario required, found {base_count}")

    for source_id, source in sources.items():
        path = f"sources.{source_id}"
        for field in ("published_at", "observed_at"):
            _timestamp(findings, source.get(field), f"{path}.{field}")
        _timestamp(findings, source.get("effective_at"), f"{path}.effective_at", required=False)
        if source.get("source_type") not in SOURCE_TYPES:
            _add(findings, "error", "source-type", f"{path}.source_type", "unsupported source type")
        if not isinstance(source.get("lineage_id"), str) or not ID_RE.fullmatch(source["lineage_id"]):
            _add(findings, "error", "lineage-id", f"{path}.lineage_id", "invalid lineage id")
        supersedes = source.get("supersedes")
        if supersedes is not None and supersedes not in sources:
            _add(findings, "error", "source-supersedes", f"{path}.supersedes", f"unknown source {supersedes!r}")
        payload = {key: value for key, value in source.items() if key != "content_hash"}
        expected = digest(payload)
        if source.get("content_hash") != expected:
            _add(findings, "error", "source-hash", f"{path}.content_hash", "does not match canonical source payload")
        for field in ("title", "publisher", "independence_group", "authority", "access_class", "license", "summary"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                _add(findings, "error", "source-field", f"{path}.{field}", "must be non-empty text")

    source_ids = set(sources)
    for claim_id, claim in claims.items():
        path = f"claims.{claim_id}"
        _timestamp(findings, claim.get("recorded_at"), f"{path}.recorded_at")
        if claim.get("claim_type") not in CLAIM_TYPES:
            _add(findings, "error", "claim-type", f"{path}.claim_type", "unsupported claim type")
        if claim.get("certainty") not in CERTAINTY:
            _add(findings, "error", "claim-certainty", f"{path}.certainty", "unsupported certainty")
        if claim.get("consequence") not in LEVELS:
            _add(findings, "error", "claim-consequence", f"{path}.consequence", "unsupported consequence")
        for field in ("support_source_ids", "contradict_source_ids", "qualification_source_ids"):
            _check_refs(claim.get(field, []), source_ids, f"{path}.{field}", findings)
        if claim.get("claim_type") in {"inference", "forecast", "scenario"} and claim.get("certainty") == "confirmed":
            _add(findings, "error", "certainty-overclaim", f"{path}.certainty", "inference, forecast, and scenario claims cannot be confirmed")
        if not isinstance(claim.get("not_proven"), list) or not claim["not_proven"]:
            _add(findings, "warning", "not-proven-boundary", f"{path}.not_proven", "should state what the evidence does not prove")

    assumption_ids = set(assumptions)
    for assumption_id, assumption in assumptions.items():
        path = f"assumptions.{assumption_id}"
        for field in ("recorded_at", "valid_from"):
            _timestamp(findings, assumption.get(field), f"{path}.{field}")
        _timestamp(findings, assumption.get("valid_until"), f"{path}.valid_until", required=False)
        if not isinstance(assumption.get("lineage_id"), str) or not ID_RE.fullmatch(assumption["lineage_id"]):
            _add(findings, "error", "assumption-lineage", f"{path}.lineage_id", "invalid lineage id")
        supersedes = assumption.get("supersedes")
        if supersedes is not None and supersedes not in assumptions:
            _add(findings, "error", "assumption-supersedes", f"{path}.supersedes", f"unknown assumption {supersedes!r}")
        _check_refs(assumption.get("dependencies", []), assumption_ids, f"{path}.dependencies", findings)
        value = assumption.get("value")
        if not isinstance(value, dict) or not all(key in value for key in ("low", "base", "high", "unit")):
            _add(findings, "error", "assumption-value", f"{path}.value", "must define low, base, high, and unit")
        elif not (value["low"] <= value["base"] <= value["high"]):
            _add(findings, "error", "assumption-order", f"{path}.value", "must satisfy low <= base <= high")
        confidence = assumption.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            _add(findings, "error", "assumption-confidence", f"{path}.confidence", "must be between 0 and 1")
        if not isinstance(assumption.get("falsifiers"), list) or not assumption["falsifiers"]:
            _add(findings, "warning", "assumption-falsifier", f"{path}.falsifiers", "should define at least one falsifier")
        if not isinstance(assumption.get("monitor"), dict) or not assumption["monitor"].get("owner"):
            _add(findings, "warning", "assumption-monitor", f"{path}.monitor", "should define a monitor owner")

    for forecast_id, forecast in forecasts.items():
        path = f"forecasts.{forecast_id}"
        _timestamp(findings, forecast.get("issued_at"), f"{path}.issued_at")
        _timestamp(findings, forecast.get("resolve_by"), f"{path}.resolve_by")
        interval = forecast.get("interval")
        if not isinstance(interval, dict) or not all(key in interval for key in ("lower", "point", "upper", "confidence")):
            _add(findings, "error", "forecast-interval", f"{path}.interval", "must define lower, point, upper, and confidence")
        elif not (interval["lower"] <= interval["point"] <= interval["upper"]):
            _add(findings, "error", "forecast-order", f"{path}.interval", "must satisfy lower <= point <= upper")
        probabilities = forecast.get("probabilities")
        if probabilities is not None:
            _sum_to_one(probabilities, f"{path}.probabilities", findings)
        outcome = forecast.get("outcome")
        if outcome is not None:
            if not isinstance(outcome, dict):
                _add(findings, "error", "forecast-outcome", f"{path}.outcome", "must be an object")
            else:
                _timestamp(findings, outcome.get("observed_at"), f"{path}.outcome.observed_at")

    option_ids = set(options)
    for option_id, option in options.items():
        path = f"options.{option_id}"
        _timestamp(findings, option.get("recorded_at"), f"{path}.recorded_at")
        if not isinstance(option.get("title"), str) or not option["title"].strip():
            _add(findings, "error", "option-title", f"{path}.title", "must be non-empty")
        if not isinstance(option.get("reversible"), bool) or not isinstance(option.get("external_action"), bool):
            _add(findings, "error", "option-flags", path, "reversible and external_action must be booleans")

    assessment_by_option: Counter[str] = Counter()
    for assessment_id, assessment in assessments.items():
        path = f"assessments.{assessment_id}"
        _timestamp(findings, assessment.get("recorded_at"), f"{path}.recorded_at")
        option_id = assessment.get("option_id")
        if option_id not in option_ids:
            _add(findings, "error", "assessment-option", f"{path}.option_id", f"unknown option {option_id!r}")
        else:
            assessment_by_option[option_id] += 1
        supersedes = assessment.get("supersedes")
        if supersedes is not None and supersedes not in assessments:
            _add(findings, "error", "assessment-supersedes", f"{path}.supersedes", f"unknown assessment {supersedes!r}")
        scores = assessment.get("scenario_scores")
        if not isinstance(scores, dict) or set(scores) != set(scenarios):
            _add(findings, "error", "assessment-scenarios", f"{path}.scenario_scores", "must cover every scenario exactly")
        else:
            for scenario_id, criterion_scores in scores.items():
                if not isinstance(criterion_scores, dict) or not criterion_scores:
                    _add(findings, "error", "criterion-scores", f"{path}.scenario_scores.{scenario_id}", "must be a non-empty object")
                else:
                    for criterion, value in criterion_scores.items():
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
                            _add(findings, "error", "criterion-score", f"{path}.scenario_scores.{scenario_id}.{criterion}", "must be between 0 and 100")
        confidence = assessment.get("criterion_confidence")
        if not isinstance(confidence, dict) or not confidence:
            _add(findings, "error", "criterion-confidence", f"{path}.criterion_confidence", "must be a non-empty object")
        else:
            for criterion, value in confidence.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    _add(findings, "error", "criterion-confidence-value", f"{path}.criterion_confidence.{criterion}", "must be between 0 and 1")
        gates = assessment.get("gates")
        if not isinstance(gates, dict) or not gates:
            _add(findings, "error", "assessment-gates", f"{path}.gates", "must be a non-empty object")
        else:
            for gate_id, state in gates.items():
                if state not in GATE_STATES:
                    _add(findings, "error", "gate-state", f"{path}.gates.{gate_id}", "unsupported gate state")
        groups = assessment.get("distributional_scores")
        if not isinstance(groups, dict) or not groups:
            _add(findings, "error", "distributional-scores", f"{path}.distributional_scores", "must declare at least one group")
        _check_refs(assessment.get("source_ids", []), source_ids, f"{path}.source_ids", findings)
    for option_id in option_ids:
        if assessment_by_option[option_id] == 0:
            _add(findings, "error", "missing-assessment", f"options.{option_id}", "option has no assessment")

    for rule_id, rule in rules.items():
        path = f"decision_rules.{rule_id}"
        _timestamp(findings, rule.get("recorded_at"), f"{path}.recorded_at")
        _timestamp(findings, rule.get("effective_from"), f"{path}.effective_from")
        _sum_to_one(rule.get("criteria_weights"), f"{path}.criteria_weights", findings)
        _sum_to_one(rule.get("robust_weights"), f"{path}.robust_weights", findings)
        if rule.get("rule_digest") != digest(_rule_payload(rule)):
            _add(findings, "error", "rule-digest", f"{path}.rule_digest", "does not match canonical rule payload")
        if not isinstance(rule.get("tie_break"), list) or not rule["tie_break"]:
            _add(findings, "error", "tie-break", f"{path}.tie_break", "must be a non-empty array")
        if not isinstance(rule.get("hard_gate_ids"), list) or not rule["hard_gate_ids"]:
            _add(findings, "error", "rule-gates", f"{path}.hard_gate_ids", "must be a non-empty array")

    decision = case.get("decision")
    if not isinstance(decision, dict):
        _add(findings, "error", "decision", "decision", "must be an object")
    else:
        for field in ("decision_cutoff", "recorded_at", "rationale_recorded_at"):
            _timestamp(findings, decision.get(field), f"decision.{field}")
        if decision.get("selected_option_id") not in option_ids:
            _add(findings, "error", "decision-option", "decision.selected_option_id", "unknown option")
        if decision.get("rule_version_id") not in rules:
            _add(findings, "error", "decision-rule", "decision.rule_version_id", "unknown rule version")
        if not isinstance(decision.get("required_approval_roles"), list) or not isinstance(decision.get("approval_roles"), list):
            _add(findings, "error", "decision-approvals", "decision", "approval role fields must be arrays")
        _check_refs(decision.get("rationale_source_ids", []), source_ids, "decision.rationale_source_ids", findings)
        action = decision.get("action")
        if not isinstance(action, dict) or not all(isinstance(action.get(key), bool) for key in ("external", "executed")):
            _add(findings, "error", "decision-action", "decision.action", "must define boolean external and executed")

    for outcome_id, outcome in outcomes.items():
        path = f"outcomes.{outcome_id}"
        _timestamp(findings, outcome.get("observed_at"), f"{path}.observed_at")
        if outcome.get("realized_scenario_id") not in scenarios:
            _add(findings, "error", "outcome-scenario", f"{path}.realized_scenario_id", "unknown scenario")
        utilities = outcome.get("option_utilities")
        if not isinstance(utilities, dict) or set(utilities) != option_ids:
            _add(findings, "error", "outcome-utilities", f"{path}.option_utilities", "must cover every option exactly")

    review = case.get("review")
    if not isinstance(review, dict):
        _add(findings, "error", "review", "review", "must be an object")
    else:
        _timestamp(findings, review.get("reviewed_at"), "review.reviewed_at")
        for field in ("surprises", "assumption_updates", "prospective_rule_changes", "learning_actions"):
            if not isinstance(review.get(field), list):
                _add(findings, "error", "review-field", f"review.{field}", "must be an array")

    if strict:
        findings = [Finding("error", item.code, item.path, item.message) if item.severity == "warning" else item for item in findings]
    return ValidationReport(tuple(findings))


def validate_snapshot(snapshot: dict[str, Any], *, strict: bool = False) -> ValidationReport:
    findings: list[Finding] = []
    if snapshot.get("schema_version") != 1:
        _add(findings, "error", "snapshot-version", "schema_version", "must be 1")
    _timestamp(findings, snapshot.get("cutoff"), "cutoff")
    if not isinstance(snapshot.get("snapshot_fingerprint"), str):
        _add(findings, "error", "snapshot-fingerprint", "snapshot_fingerprint", "must be present")
    else:
        payload = {key: value for key, value in snapshot.items() if key != "snapshot_fingerprint"}
        if snapshot["snapshot_fingerprint"] != digest(payload):
            _add(findings, "error", "snapshot-fingerprint", "snapshot_fingerprint", "does not match canonical snapshot")
    if not isinstance(snapshot.get("active_source_ids"), dict):
        _add(findings, "error", "active-sources", "active_source_ids", "must be an object")
    if not isinstance(snapshot.get("active_assessment_ids"), dict):
        _add(findings, "error", "active-assessments", "active_assessment_ids", "must be an object")
    if strict:
        findings = [Finding("error", item.code, item.path, item.message) if item.severity == "warning" else item for item in findings]
    return ValidationReport(tuple(findings))


def assumption_cycle(assumptions: Iterable[dict[str, Any]]) -> list[str] | None:
    graph = {item["assumption_id"]: list(item.get("dependencies", [])) for item in assumptions}
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            index = stack.index(node)
            return stack[index:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for child in graph.get(node, []):
            cycle = visit(child)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in sorted(graph):
        cycle = visit(node)
        if cycle:
            return cycle
    return None
