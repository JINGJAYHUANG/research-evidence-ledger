from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Callable

from .canonical import digest
from .timeutil import at_or_before, parse_timestamp
from .validation import validate_case


def _latest_by(items: list[dict[str, Any]], key: Callable[[dict[str, Any]], str], timestamp: str, id_key: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[key(item)].append(item)
    selected: list[dict[str, Any]] = []
    active: dict[str, str] = {}
    for group_id in sorted(grouped):
        candidates = sorted(
            grouped[group_id],
            key=lambda item: (parse_timestamp(item[timestamp]), item[id_key]),
        )
        choice = candidates[-1]
        selected.append(choice)
        identifier = choice[id_key]
        active[group_id] = identifier
    return selected, active


def freeze_case(case: dict[str, Any], cutoff: str | None = None) -> dict[str, Any]:
    validation = validate_case(case)
    if not validation.ok:
        detail = "; ".join(f"{item.code}@{item.path}" for item in validation.findings if item.severity == "error")
        raise ValueError(f"case validation failed: {detail}")
    cutoff = cutoff or case["decision"]["decision_cutoff"]
    parse_timestamp(cutoff)

    known_sources = [
        deepcopy(item)
        for item in case["sources"]
        if at_or_before(item["published_at"], cutoff) and at_or_before(item["observed_at"], cutoff)
    ]
    source_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in known_sources:
        source_groups[source["lineage_id"]].append(source)
    active_sources: dict[str, str] = {}
    for lineage_id, items in source_groups.items():
        choice = max(items, key=lambda item: (parse_timestamp(item["observed_at"]), item["source_id"]))
        active_sources[lineage_id] = choice["source_id"]

    known_claims = [deepcopy(item) for item in case["claims"] if at_or_before(item["recorded_at"], cutoff)]
    known_assumptions = [deepcopy(item) for item in case["assumptions"] if at_or_before(item["recorded_at"], cutoff) and at_or_before(item["valid_from"], cutoff)]
    active_assumptions_list, active_assumptions = _latest_by(known_assumptions, lambda item: item["lineage_id"], "recorded_at", "assumption_id")

    known_options = [deepcopy(item) for item in case["options"] if at_or_before(item["recorded_at"], cutoff)]
    known_option_ids = {item["option_id"] for item in known_options}
    known_assessments = [deepcopy(item) for item in case["assessments"] if item["option_id"] in known_option_ids and at_or_before(item["recorded_at"], cutoff)]
    active_assessment_list, active_assessments = _latest_by(known_assessments, lambda item: item["option_id"], "recorded_at", "assessment_id")

    known_rules = [deepcopy(item) for item in case["decision_rules"] if at_or_before(item["recorded_at"], cutoff) and at_or_before(item["effective_from"], cutoff)]
    active_rules_list, active_rules = _latest_by(known_rules, lambda item: item["rule_id"], "recorded_at", "rule_version_id")

    forecasts = []
    for forecast in case["forecasts"]:
        if not at_or_before(forecast["issued_at"], cutoff):
            continue
        item = deepcopy(forecast)
        if item.get("outcome") and not at_or_before(item["outcome"]["observed_at"], cutoff):
            item["outcome"] = None
        forecasts.append(item)

    outcomes = [deepcopy(item) for item in case["outcomes"] if at_or_before(item["observed_at"], cutoff)]
    review = deepcopy(case["review"]) if at_or_before(case["review"]["reviewed_at"], cutoff) else None
    decision = deepcopy(case["decision"]) if at_or_before(case["decision"]["recorded_at"], cutoff) else None

    included_source_ids = {item["source_id"] for item in known_sources}
    for claim in known_claims:
        for field in ("support_source_ids", "contradict_source_ids", "qualification_source_ids"):
            claim[field] = [source_id for source_id in claim.get(field, []) if source_id in included_source_ids]

    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "case_id": case["case_id"],
        "title": case["title"],
        "cutoff": cutoff,
        "public_boundary": deepcopy(case["public_boundary"]),
        "sources": sorted(known_sources, key=lambda item: item["source_id"]),
        "active_source_ids": dict(sorted(active_sources.items())),
        "claims": sorted(known_claims, key=lambda item: item["claim_id"]),
        "assumptions": sorted(active_assumptions_list, key=lambda item: item["assumption_id"]),
        "active_assumption_ids": dict(sorted(active_assumptions.items())),
        "forecasts": sorted(forecasts, key=lambda item: item["forecast_id"]),
        "scenarios": deepcopy(case["scenarios"]),
        "options": sorted(known_options, key=lambda item: item["option_id"]),
        "assessments": sorted(active_assessment_list, key=lambda item: item["assessment_id"]),
        "active_assessment_ids": dict(sorted(active_assessments.items())),
        "decision_rules": sorted(known_rules, key=lambda item: item["rule_version_id"]),
        "active_rule_ids": dict(sorted(active_rules.items())),
        "decision": decision,
        "outcomes": sorted(outcomes, key=lambda item: item["outcome_id"]),
        "review": review,
        "freeze_metadata": {
            "known_source_count": len(known_sources),
            "excluded_future_source_ids": sorted({item["source_id"] for item in case["sources"]} - included_source_ids),
            "known_claim_count": len(known_claims),
            "known_forecast_count": len(forecasts),
            "outcome_count": len(outcomes),
            "review_available": review is not None,
        },
    }
    snapshot["snapshot_fingerprint"] = digest(snapshot)
    return snapshot
