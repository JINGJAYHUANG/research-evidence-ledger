from __future__ import annotations

from typing import Any

from .canonical import digest
from .replay import replay_decision


def _by_id(items: list[dict[str, Any]], id_key: str) -> dict[str, dict[str, Any]]:
    return {item[id_key]: item for item in items}


def _diff_collection(before: list[dict[str, Any]], after: list[dict[str, Any]], id_key: str) -> dict[str, Any]:
    left = _by_id(before, id_key)
    right = _by_id(after, id_key)
    added = sorted(set(right) - set(left))
    removed = sorted(set(left) - set(right))
    changed = []
    for item_id in sorted(set(left) & set(right)):
        left_digest = digest(left[item_id])
        right_digest = digest(right[item_id])
        if left_digest != right_digest:
            changed.append({
                "id": item_id,
                "before_digest": left_digest,
                "after_digest": right_digest,
            })
    return {"added": added, "removed": removed, "changed": changed}


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    if before["case_id"] != after["case_id"]:
        raise ValueError("snapshots must belong to the same case")
    if before["cutoff"] >= after["cutoff"]:
        raise ValueError("after cutoff must be later than before cutoff")

    original_rule_id = (before.get("decision") or {}).get("rule_version_id")
    original_replay_after = replay_decision(after, rule_version_id=original_rule_id) if original_rule_id else None
    latest_rule_id = max(
        after["decision_rules"],
        key=lambda item: (item["recorded_at"], item["rule_version_id"]),
    )["rule_version_id"]
    latest_replay_after = replay_decision(after, rule_version_id=latest_rule_id)
    before_replay = replay_decision(before)

    result: dict[str, Any] = {
        "schema_version": 1,
        "case_id": before["case_id"],
        "before_cutoff": before["cutoff"],
        "after_cutoff": after["cutoff"],
        "before_snapshot_fingerprint": before["snapshot_fingerprint"],
        "after_snapshot_fingerprint": after["snapshot_fingerprint"],
        "changes": {
            "sources": _diff_collection(before["sources"], after["sources"], "source_id"),
            "claims": _diff_collection(before["claims"], after["claims"], "claim_id"),
            "assumptions": _diff_collection(before["assumptions"], after["assumptions"], "assumption_id"),
            "forecasts": _diff_collection(before["forecasts"], after["forecasts"], "forecast_id"),
            "assessments": _diff_collection(before["assessments"], after["assessments"], "assessment_id"),
            "decision_rules": _diff_collection(before["decision_rules"], after["decision_rules"], "rule_version_id"),
            "outcomes": _diff_collection(before["outcomes"], after["outcomes"], "outcome_id"),
        },
        "counterfactuals": {
            "decision_time_original_rule": {
                "rule_version_id": before_replay["rule_version_id"],
                "selected_option_id": before_replay["selected_option_id"],
            },
            "later_evidence_original_rule": None if original_replay_after is None else {
                "rule_version_id": original_replay_after["rule_version_id"],
                "selected_option_id": original_replay_after["selected_option_id"],
            },
            "later_evidence_latest_rule": {
                "rule_version_id": latest_replay_after["rule_version_id"],
                "selected_option_id": latest_replay_after["selected_option_id"],
            },
        },
        "decision_flip_with_new_evidence_same_rule": (
            None if original_replay_after is None
            else before_replay["selected_option_id"] != original_replay_after["selected_option_id"]
        ),
        "decision_flip_from_rule_change": (
            None if original_replay_after is None
            else original_replay_after["selected_option_id"] != latest_replay_after["selected_option_id"]
        ),
        "claim_boundary": (
            "A decision flip shows sensitivity to new evidence or a prospective rule change. "
            "It does not prove that the later decision is universally correct."
        ),
    }
    result["diff_fingerprint"] = digest(result)
    return result
