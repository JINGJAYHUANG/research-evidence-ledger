from __future__ import annotations

import csv
import html
import io
import json
from typing import Any


def _safe_csv(value: Any) -> Any:
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else value


def replay_markdown(replay: dict[str, Any]) -> str:
    process = replay["process_assessment"]
    lines = [
        f"# Decision Replay — {replay['case_id']}",
        "",
        f"- Cutoff: `{replay['cutoff']}`",
        f"- Rule: `{replay['rule_version_id']}`",
        f"- Selected option: **{replay['selected_option_id']}**",
        f"- Recorded option: `{replay['recorded_option_id']}`",
        f"- Recorded decision matches replay: `{str(replay['recorded_decision_matches_replay']).lower()}`",
        f"- Process score: **{process['process_score']:.2f}/100**",
        f"- Process level: **{process['process_level']}**",
        "",
        "> This is a reconstruction of a synthetic decision record, not a claim that the option is suitable for a real organization.",
        "",
        "## Options",
        "",
        "| Option | Robust | Expected | Worst | Max regret | Gate state |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for option in replay["options"]:
        gate_state = "FAIL: " + ", ".join(option["failed_gates"]) if option["failed_gates"] else "REVIEW: " + ", ".join(option["unknown_gates"]) if option["unknown_gates"] else "pass"
        lines.append(
            f"| `{option['option_id']}` | {option['robust_score']:.2f} | {option['expected_score']:.2f} | "
            f"{option['worst_score']:.2f} | {option['max_regret']:.2f} | {gate_state} |"
        )
    lines += ["", "## Hard process gates", ""]
    for gate_id, gate in process["hard_gates"].items():
        detail = "; ".join(gate["details"]) if gate["details"] else "No finding."
        lines.append(f"- `{gate_id}`: **{gate['status']}** — {detail}")
    lines += ["", "## Claim boundary", "", replay["claim_boundary"]]
    return "\n".join(lines) + "\n"


def review_markdown(review: dict[str, Any]) -> str:
    lines = [
        f"# Decision Review — {review['case_id']}",
        "",
        f"- Selected option: `{review['selected_option_id']}`",
        f"- Best ex-post option: `{review['best_ex_post_option_id']}`",
        f"- Ex-post regret: **{review['ex_post_regret']:.2f}**",
        f"- Process score: **{review['process_score']:.2f}**",
        f"- Decision-quality quadrant: **{review['decision_quality_quadrant']}**",
        "",
        "## Forecast evaluation",
        "",
        f"- Evaluated forecasts: {review['forecast_evaluation']['evaluated_forecast_count']}",
        f"- Mean squared error: {review['forecast_evaluation']['mean_squared_error']}",
        f"- Interval coverage: {review['forecast_evaluation']['interval_coverage']}",
        f"- Multiclass Brier score: {review['forecast_evaluation']['multiclass_brier_score']}",
        "",
        "## Surprises",
        "",
    ]
    lines.extend(f"- {item['description']}" for item in review["surprises"])
    lines += ["", "## Learning actions", ""]
    lines.extend(f"- `{item['owner']}` by `{item['due_at']}`: {item['action']}" for item in review["learning_actions"])
    lines += ["", "## Claim boundary", "", review["claim_boundary"]]
    return "\n".join(lines) + "\n"


def replay_csv(replay: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["option_id", "title", "robust_score", "expected_score", "worst_score", "max_regret", "eligible", "failed_gates", "unknown_gates"])
    for option in replay["options"]:
        writer.writerow([_safe_csv(value) for value in [
            option["option_id"], option["title"], option["robust_score"], option["expected_score"], option["worst_score"], option["max_regret"], option["eligible"], ";".join(option["failed_gates"]), ";".join(option["unknown_gates"]),
        ]])
    return output.getvalue()


def replay_html(replay: dict[str, Any], review: dict[str, Any] | None = None, diff: dict[str, Any] | None = None) -> str:
    process = replay["process_assessment"]
    option_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(item['option_id'])}</code></td>"
        f"<td>{html.escape(item['title'])}</td>"
        f"<td>{item['robust_score']:.2f}</td>"
        f"<td>{item['expected_score']:.2f}</td>"
        f"<td>{item['worst_score']:.2f}</td>"
        f"<td>{item['max_regret']:.2f}</td>"
        f"<td>{'eligible' if item['eligible'] else 'ineligible'}</td>"
        "</tr>"
        for item in replay["options"]
    )
    gate_cards = "".join(
        f"<article><h3>{html.escape(gate_id)}</h3><p class='{html.escape(gate['status'])}'>{html.escape(gate['status'])}</p>"
        f"<small>{html.escape('; '.join(gate['details']) if gate['details'] else 'No finding.')}</small></article>"
        for gate_id, gate in process["hard_gates"].items()
    )
    review_section = ""
    if review:
        review_section = f"""
<section id="review"><h2>Outcome review</h2><div class="metrics">
<article><strong>{html.escape(review['decision_quality_quadrant'])}</strong><small>decision-quality quadrant</small></article>
<article><strong>{review['ex_post_regret']:.2f}</strong><small>ex-post regret</small></article>
<article><strong>{html.escape(review['best_ex_post_option_id'])}</strong><small>best ex-post option</small></article>
<article><strong>{review['forecast_evaluation']['interval_coverage']}</strong><small>interval coverage</small></article>
</div></section>"""
    diff_section = ""
    if diff:
        diff_section = f"""
<section id="change"><h2>What changed</h2><div class="metrics">
<article><strong>{len(diff['changes']['sources']['added'])}</strong><small>new sources</small></article>
<article><strong>{len(diff['changes']['claims']['added'])}</strong><small>new claims</small></article>
<article><strong>{str(diff['decision_flip_with_new_evidence_same_rule']).lower()}</strong><small>flip from evidence</small></article>
<article><strong>{str(diff['decision_flip_from_rule_change']).lower()}</strong><small>flip from rule change</small></article>
</div></section>"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Decision Time Machine — {html.escape(replay['case_id'])}</title>
<style>
:root{{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#172132;background:#f4f7fb}}body{{margin:0}}main{{max-width:1180px;margin:auto;padding:28px 18px 64px}}header{{background:#111d32;color:white;border-radius:22px;padding:34px}}header p{{max-width:74ch;color:#d7e2f1}}.metrics,.gates{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}}article{{background:white;border:1px solid #dbe3ee;border-radius:14px;padding:16px}}article strong{{display:block;font-size:1.35rem}}article small{{display:block;color:#59677a;margin-top:8px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:10px;border-bottom:1px solid #e1e7f0;text-align:left}}.table-wrap{{overflow-x:auto;border:1px solid #dbe3ee;border-radius:14px}}.pass,.eligible{{color:#11633c}}.fail,.ineligible{{color:#9d2c2c}}section{{margin-top:34px}}code{{overflow-wrap:anywhere}}@media(max-width:600px){{main{{padding:12px}}header{{padding:22px}}th,td{{font-size:13px}}}}@media print{{body{{background:white}}header{{color:black;background:white;border:1px solid #999}}}}
</style></head><body><main>
<header><p>POINT-IN-TIME DECISION REPLAY</p><h1>{html.escape(replay['case_id'])}</h1><p>{html.escape(replay['claim_boundary'])}</p></header>
<section><div class="metrics">
<article><strong>{html.escape(replay['selected_option_id'])}</strong><small>replayed selection</small></article>
<article><strong>{process['process_score']:.2f}</strong><small>process score</small></article>
<article><strong>{html.escape(process['process_level'])}</strong><small>process level</small></article>
<article><strong>{len(process['failed_hard_gates'])}</strong><small>failed hard gates</small></article>
</div></section>
<section id="options"><h2>Options at the decision cutoff</h2><div class="table-wrap"><table><thead><tr><th>Option</th><th>Title</th><th>Robust</th><th>Expected</th><th>Worst</th><th>Regret</th><th>State</th></tr></thead><tbody>{option_rows}</tbody></table></div></section>
<section id="gates"><h2>Process hard gates</h2><div class="gates">{gate_cards}</div></section>
{review_section}{diff_section}
<section><h2>Evidence boundary</h2><p>This static page contains only synthetic decision records. It does not certify factual correctness, commercial suitability, legal compliance, or external execution.</p></section>
</main></body></html>"""


def render(kind: str, value: dict[str, Any], *, format_name: str, related: dict[str, Any] | None = None, diff: dict[str, Any] | None = None) -> str:
    if format_name == "json":
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if kind == "replay" and format_name == "markdown":
        return replay_markdown(value)
    if kind == "review" and format_name == "markdown":
        return review_markdown(value)
    if kind == "replay" and format_name == "csv":
        return replay_csv(value)
    if kind == "replay" and format_name == "html":
        return replay_html(value, review=related, diff=diff) + "\n"
    raise ValueError(f"unsupported render combination: {kind}/{format_name}")
