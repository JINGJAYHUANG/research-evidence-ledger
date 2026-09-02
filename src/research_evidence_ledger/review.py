from __future__ import annotations

from typing import Any

from .canonical import digest
from .freeze import freeze_case
from .replay import replay_decision


def _forecast_metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    evaluated = []
    squared_errors = []
    interval_hits = []
    brier_terms = []
    for forecast in snapshot["forecasts"]:
        outcome = forecast.get("outcome")
        if not outcome:
            continue
        actual = float(outcome["value"])
        interval = forecast["interval"]
        point_error = float(interval["point"]) - actual
        hit = float(interval["lower"]) <= actual <= float(interval["upper"])
        squared_errors.append(point_error ** 2)
        interval_hits.append(1.0 if hit else 0.0)
        event = outcome.get("event")
        probability = None
        if event is not None and forecast.get("probabilities") and event in forecast["probabilities"]:
            probability = float(forecast["probabilities"][event])
            brier = (probability - 1.0) ** 2 + sum(
                float(value) ** 2
                for key, value in forecast["probabilities"].items()
                if key != event
            )
            brier_terms.append(brier)
        evaluated.append(
            {
                "forecast_id": forecast["forecast_id"],
                "metric": forecast["metric"],
                "actual": actual,
                "point_error": round(point_error, 4),
                "interval_hit": hit,
                "realized_event": event,
                "realized_event_probability": probability,
            }
        )
    return {
        "evaluated_forecast_count": len(evaluated),
        "mean_squared_error": None
        if not squared_errors
        else round(sum(squared_errors) / len(squared_errors), 4),
        "interval_coverage": None
        if not interval_hits
        else round(sum(interval_hits) / len(interval_hits), 4),
        "multiclass_brier_score": None
        if not brier_terms
        else round(sum(brier_terms) / len(brier_terms), 4),
        "forecasts": evaluated,
    }


def review_decision(
    case: dict[str, Any], *, review_cutoff: str | None = None
) -> dict[str, Any]:
    decision_snapshot = freeze_case(case, case["decision"]["decision_cutoff"])
    replay = replay_decision(decision_snapshot)
    cutoff = review_cutoff or case["review"]["reviewed_at"]
    snapshot = freeze_case(case, cutoff)
    if not snapshot.get("review") or not snapshot.get("outcomes"):
        raise ValueError("review cutoff must include a review and at least one outcome")
    decision = case["decision"]
    latest_outcome = max(
        snapshot["outcomes"],
        key=lambda item: (item["observed_at"], item["outcome_id"]),
    )
    utilities = {
        key: float(value) for key, value in latest_outcome["option_utilities"].items()
    }
    selected_option = decision["selected_option_id"]
    selected_utility = utilities[selected_option]
    best_option = max(sorted(utilities), key=lambda option_id: utilities[option_id])
    best_utility = utilities[best_option]
    regret = best_utility - selected_utility
    process_score = float(replay["process_assessment"]["process_score"])
    if process_score >= 80 and regret <= 10:
        quadrant = "sound-and-fortunate"
    elif process_score >= 80:
        quadrant = "sound-but-unlucky"
    elif regret <= 10:
        quadrant = "lucky-but-fragile"
    else:
        quadrant = "poor-process-poor-outcome"

    review = snapshot["review"]
    learning_completeness = {
        "surprises_recorded": bool(review.get("surprises")),
        "assumption_updates_recorded": bool(review.get("assumption_updates")),
        "rule_changes_prospective": all(
            item.get("prospective_only") is True
            for item in review.get("prospective_rule_changes", [])
        ),
        "learning_actions_assigned": all(
            item.get("owner") and item.get("due_at")
            for item in review.get("learning_actions", [])
        ),
    }
    output: dict[str, Any] = {
        "schema_version": 1,
        "case_id": snapshot["case_id"],
        "reviewed_at": review["reviewed_at"],
        "decision_cutoff": decision["decision_cutoff"],
        "decision_snapshot_fingerprint": decision_snapshot["snapshot_fingerprint"],
        "review_snapshot_fingerprint": snapshot["snapshot_fingerprint"],
        "selected_option_id": selected_option,
        "best_ex_post_option_id": best_option,
        "selected_ex_post_utility": round(selected_utility, 4),
        "best_ex_post_utility": round(best_utility, 4),
        "ex_post_regret": round(regret, 4),
        "process_score": process_score,
        "process_level": replay["process_assessment"]["process_level"],
        "decision_quality_quadrant": quadrant,
        "forecast_evaluation": _forecast_metrics(snapshot),
        "surprises": review["surprises"],
        "assumption_updates": review["assumption_updates"],
        "prospective_rule_changes": review["prospective_rule_changes"],
        "learning_actions": review["learning_actions"],
        "learning_completeness": learning_completeness,
        "claim_boundary": (
            "A favorable outcome does not prove a sound process, and an unfavorable outcome does not prove a poor process. "
            "The quadrant separates decision quality from realized luck in this synthetic case."
        ),
    }
    output["review_fingerprint"] = digest(output)
    return output
