#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import shutil
import tempfile
from pathlib import Path

from research_evidence_ledger.audit import AuditChain, create_checkpoint
from research_evidence_ledger.diffing import compare_snapshots
from research_evidence_ledger.freeze import freeze_case
from research_evidence_ledger.io import load_json
from research_evidence_ledger.process import assess_process
from research_evidence_ledger.replay import replay_decision
from research_evidence_ledger.reporting import render
from research_evidence_ledger.review import review_decision

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "examples" / "cases"
MUTANTS = ROOT / "examples" / "mutants"
GENERATED = ROOT / "examples" / "generated"


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _summary_csv(rows: list[dict[str, object]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[
        "case_id", "selected_option_id", "recorded_match", "process_score",
        "process_level", "quadrant", "ex_post_regret", "evidence_flip",
        "rule_flip",
    ])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def _lab_index(rows: list[dict[str, object]], mutant_rows: list[dict[str, object]]) -> str:
    case_cards = "".join(
        f"<article><p class='eyebrow'>{html.escape(str(row['process_level']))}</p>"
        f"<h2>{html.escape(str(row['case_id']))}</h2>"
        f"<dl><div><dt>Selected</dt><dd>{html.escape(str(row['selected_option_id']))}</dd></div>"
        f"<div><dt>Process</dt><dd>{float(row['process_score']):.2f}</dd></div>"
        f"<div><dt>Outcome</dt><dd>{html.escape(str(row['quadrant']))}</dd></div>"
        f"<div><dt>Ex-post regret</dt><dd>{float(row['ex_post_regret']):.2f}</dd></div></dl>"
        f"<a href='{html.escape(str(row['case_id']))}/decision-lab.html'>Open time machine</a></article>"
        for row in rows
    )
    mutant_items = "".join(
        f"<li><code>{html.escape(str(row['case_id']))}</code><span>{html.escape(', '.join(row['failed_hard_gates']))}</span></li>"
        for row in mutant_rows
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Research Evidence Ledger — Decision Time Machine Lab</title>
<style>
:root{{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#172033;background:#f3f6fb}}body{{margin:0}}main{{max-width:1180px;margin:auto;padding:30px 18px 70px}}header{{background:linear-gradient(135deg,#111d32,#173c52);color:white;padding:40px;border-radius:24px}}header p{{max-width:76ch;color:#d8e7ef}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:24px 0}}article{{background:white;border:1px solid #d9e2ee;border-radius:16px;padding:20px}}.eyebrow{{text-transform:uppercase;letter-spacing:.08em;font-size:.75rem;color:#24607b}}dl div{{display:flex;justify-content:space-between;border-top:1px solid #e8edf4;padding:8px 0}}dt{{color:#5d697a}}dd{{margin:0;font-weight:650}}a{{color:#124c68;font-weight:700}}ul{{list-style:none;padding:0}}li{{display:flex;justify-content:space-between;gap:16px;padding:10px 0;border-bottom:1px solid #dfe6ef}}small{{color:#5e6a79}}@media(max-width:620px){{header{{padding:24px}}li{{display:block}}}}
</style></head><body><main><header><p>POINT-IN-TIME DECISION ASSURANCE</p><h1>Research Evidence Ledger</h1><p>Freeze what was knowable, replay the stated rule, separate process quality from luck, and record what changed. All cases are fictional and synthetic.</p></header>
<section><h2>Reference decisions</h2><div class="grid">{case_cards}</div></section>
<section><h2>Adversarial integrity cases</h2><ul>{mutant_items}</ul></section>
<section><h2>Boundary</h2><p><small>This lab does not certify factual correctness, external action, legal compliance, or production safety. The audit checkpoint is unsigned and provides no authorship or external timestamp proof.</small></p></section>
</main></body></html>"""


def build_payloads() -> dict[Path, bytes]:
    payloads: dict[Path, bytes] = {}
    summary_rows: list[dict[str, object]] = []
    mutant_rows: list[dict[str, object]] = []

    for case_path in sorted(CASES.glob("*.json")):
        case = load_json(case_path)
        case_id = case["case_id"]
        before = freeze_case(case, case["decision"]["decision_cutoff"])
        after = freeze_case(case, case["review"]["reviewed_at"])
        replay = replay_decision(before)
        review = review_decision(case)
        comparison = compare_snapshots(before, after)
        base = Path(case_id)

        payloads[base / "decision.snapshot.json"] = _json(before).encode()
        payloads[base / "review.snapshot.json"] = _json(after).encode()
        payloads[base / "replay.json"] = _json(replay).encode()
        payloads[base / "review.json"] = _json(review).encode()
        payloads[base / "diff.json"] = _json(comparison).encode()
        payloads[base / "replay.md"] = render("replay", replay, format_name="markdown").encode()
        payloads[base / "review.md"] = render("review", review, format_name="markdown").encode()
        payloads[base / "options.csv"] = render("replay", replay, format_name="csv").encode()
        payloads[base / "decision-lab.html"] = render(
            "replay", replay, format_name="html", related=review, diff=comparison
        ).encode()

        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(trace_path)
            chain.append("decision.snapshot", before["cutoff"], {"fingerprint": before["snapshot_fingerprint"]})
            chain.append("decision.replay", case["decision"]["recorded_at"], {"fingerprint": replay["replay_fingerprint"], "selected": replay["selected_option_id"]})
            chain.append("decision.review", review["reviewed_at"], {"fingerprint": review["review_fingerprint"], "quadrant": review["decision_quality_quadrant"]})
            chain.append("decision.diff", after["cutoff"], {"fingerprint": comparison["diff_fingerprint"]})
            records = list(chain.read())
            payloads[base / "trace.jsonl"] = trace_path.read_bytes()
            payloads[base / "checkpoint.json"] = _json(create_checkpoint(records)).encode()

        summary_rows.append({
            "case_id": case_id,
            "selected_option_id": replay["selected_option_id"],
            "recorded_match": str(replay["recorded_decision_matches_replay"]).lower(),
            "process_score": replay["process_assessment"]["process_score"],
            "process_level": replay["process_assessment"]["process_level"],
            "quadrant": review["decision_quality_quadrant"],
            "ex_post_regret": review["ex_post_regret"],
            "evidence_flip": str(comparison["decision_flip_with_new_evidence_same_rule"]).lower(),
            "rule_flip": str(comparison["decision_flip_from_rule_change"]).lower(),
        })

    for mutant_path in sorted(MUTANTS.glob("*.json")):
        case = load_json(mutant_path)
        snapshot = freeze_case(case, case["decision"]["decision_cutoff"])
        process = assess_process(snapshot)
        value = {
            "schema_version": 1,
            "case_id": case["case_id"],
            "expected_failed_hard_gates": sorted(case["expected_failed_hard_gates"]),
            "actual_failed_hard_gates": sorted(process["failed_hard_gates"]),
            "matches_expected": sorted(case["expected_failed_hard_gates"]) == sorted(process["failed_hard_gates"]),
            "process_assessment": process,
        }
        payloads[Path("mutants") / f"{case['case_id']}.process.json"] = _json(value).encode()
        mutant_rows.append({"case_id": case["case_id"], "failed_hard_gates": sorted(process["failed_hard_gates"])})

    payloads[Path("case-summary.csv")] = _summary_csv(summary_rows).encode()
    payloads[Path("decision-time-machine-lab.html")] = _lab_index(summary_rows, mutant_rows).encode()

    manifest_files = {
        path.as_posix(): {"bytes": len(data), "sha256": _sha(data)}
        for path, data in sorted(payloads.items(), key=lambda item: item[0].as_posix())
    }
    manifest = {
        "schema_version": 1,
        "generator": "tools/generate_examples.py",
        "case_count": len(summary_rows),
        "mutant_count": len(mutant_rows),
        "file_count": len(manifest_files),
        "files": manifest_files,
    }
    payloads[Path("generated-manifest.json")] = _json(manifest).encode()
    return payloads


def write_payloads(payloads: dict[Path, bytes], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for relative, data in payloads.items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def check_payloads(payloads: dict[Path, bytes], directory: Path) -> list[str]:
    expected = {path.as_posix() for path in payloads}
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    }
    errors: list[str] = []
    for missing in sorted(expected - actual):
        errors.append(f"missing generated file: {missing}")
    for extra in sorted(actual - expected):
        errors.append(f"unexpected generated file: {extra}")
    for relative, data in payloads.items():
        target = directory / relative
        if target.is_file() and target.read_bytes() != data:
            errors.append(f"generated drift: {relative.as_posix()}")
    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", default=str(GENERATED))
    args = parser.parse_args()
    output = Path(args.output).resolve()
    payloads = build_payloads()
    if args.check:
        errors = check_payloads(payloads, output)
        if errors:
            print("generated artifact check failed:")
            print("\n".join(f"- {item}" for item in errors))
            return 1
        print(f"generated artifacts are current: {len(payloads)} file(s)")
        return 0
    if output.exists():
        shutil.rmtree(output)
    write_payloads(payloads, output)
    print(f"generated {len(payloads)} file(s) in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
