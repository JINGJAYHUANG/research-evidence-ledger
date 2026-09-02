from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .audit import AuditChain, create_checkpoint, verify_checkpoint
from .canonical import digest
from .diffing import compare_snapshots
from .freeze import freeze_case
from .io import load_json, write_json
from .process import assess_process
from .replay import replay_decision
from .reporting import render
from .review import review_decision
from .validation import validate_case, validate_snapshot


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))


def _write_or_print(value: str, output: str | None) -> None:
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8", newline="\n")
        print(target)
    else:
        print(value, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rel",
        description=(
            "Freeze, replay, review, and compare point-in-time decision evidence. "
            "The CLI reads synthetic/local records and never executes external actions."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate a case or frozen snapshot.")
    validate.add_argument("path")
    validate.add_argument("--kind", choices=["case", "snapshot"], default="case")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true")

    freeze = sub.add_parser("freeze", help="Create a deterministic point-in-time snapshot.")
    freeze.add_argument("case")
    freeze.add_argument("--cutoff")
    freeze.add_argument("--output")

    replay = sub.add_parser("replay", help="Replay a recorded decision from its frozen evidence.")
    source = replay.add_mutually_exclusive_group(required=True)
    source.add_argument("--case")
    source.add_argument("--snapshot")
    replay.add_argument("--cutoff")
    replay.add_argument("--rule-version-id")
    replay.add_argument("--format", choices=["json", "markdown", "html", "csv"], default="json")
    replay.add_argument("--output")

    review = sub.add_parser("review", help="Separate decision-process quality from realized outcome.")
    review.add_argument("case")
    review.add_argument("--cutoff")
    review.add_argument("--format", choices=["json", "markdown"], default="json")
    review.add_argument("--output")

    diff = sub.add_parser("diff", help="Compare two point-in-time snapshots of one case.")
    diff.add_argument("case")
    diff.add_argument("--before", required=True)
    diff.add_argument("--after", required=True)
    diff.add_argument("--output")

    trace = sub.add_parser("trace", help="Create a local hash-chained decision evidence trace.")
    trace.add_argument("case")
    trace.add_argument("--output", required=True)
    trace.add_argument("--checkpoint")

    audit = sub.add_parser("audit", help="Verify a local hash chain and optional checkpoint.")
    audit.add_argument("path")
    audit.add_argument("--checkpoint")
    audit.add_argument("--json", action="store_true")

    lab = sub.add_parser("lab", help="Build a static decision time-machine page.")
    lab.add_argument("case")
    lab.add_argument("--output", required=True)

    fingerprint = sub.add_parser("fingerprint", help="Print a canonical SHA-256 fingerprint.")
    fingerprint.add_argument("path")

    scaffold = sub.add_parser("scaffold", help="Create a minimal synthetic case scaffold.")
    scaffold.add_argument("--output", required=True)

    self_test = sub.add_parser("self-test", help="Run end-to-end synthetic cases and adversarial mutants.")
    self_test.add_argument("--root", default=".")
    self_test.add_argument("--json", action="store_true")
    return parser


def _snapshot_from_args(case_path: str | None, snapshot_path: str | None, cutoff: str | None) -> dict[str, Any]:
    if snapshot_path:
        return load_json(snapshot_path)
    assert case_path
    case = load_json(case_path)
    return freeze_case(case, cutoff or case["decision"]["decision_cutoff"])


def _scaffold() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "case_id": "synthetic-new-decision",
        "title": "Replace with a synthetic decision title",
        "case_as_of": "2026-09-02T00:00:00Z",
        "public_boundary": {
            "synthetic_only": True,
            "contains_personal_data": False,
            "contains_credentials": False,
            "external_actions_enabled": False,
            "statement": "Replace all placeholders before validation.",
        },
        "sources": [],
        "claims": [],
        "assumptions": [],
        "forecasts": [],
        "scenarios": [],
        "options": [],
        "assessments": [],
        "decision_rules": [],
        "decision": {},
        "outcomes": [],
        "review": {},
    }


def _self_test(root: Path) -> dict[str, Any]:
    case_paths = sorted((root / "examples/cases").glob("*.json"))
    mutant_paths = sorted((root / "examples/mutants").glob("*.json"))
    cases = []
    mutants = []
    for path in case_paths:
        case = load_json(path)
        validation = validate_case(case, strict=True)
        if not validation.ok:
            raise ValueError(f"reference case failed strict validation: {path}")
        decision_snapshot = freeze_case(case, case["decision"]["decision_cutoff"])
        replay = replay_decision(decision_snapshot)
        review = review_decision(case)
        later = freeze_case(case, case["review"]["reviewed_at"])
        comparison = compare_snapshots(decision_snapshot, later)
        cases.append(
            {
                "case_id": case["case_id"],
                "selected_option_id": replay["selected_option_id"],
                "recorded_match": replay["recorded_decision_matches_replay"],
                "process_level": replay["process_assessment"]["process_level"],
                "quadrant": review["decision_quality_quadrant"],
                "decision_flip_from_evidence": comparison["decision_flip_with_new_evidence_same_rule"],
            }
        )
    for path in mutant_paths:
        case = load_json(path)
        validation = validate_case(case)
        if not validation.ok:
            raise ValueError(f"mutant is structurally invalid: {path}")
        snapshot = freeze_case(case, case["decision"]["decision_cutoff"])
        process = assess_process(snapshot)
        expected = sorted(case["expected_failed_hard_gates"])
        actual = sorted(process["failed_hard_gates"])
        if expected != actual:
            raise ValueError(f"mutant gate mismatch {path}: expected={expected}, actual={actual}")
        mutants.append({"case_id": case["case_id"], "failed_hard_gates": actual})
    return {
        "ok": True,
        "case_count": len(cases),
        "mutant_count": len(mutants),
        "cases": cases,
        "mutants": mutants,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            value = load_json(args.path)
            report = validate_case(value, strict=args.strict) if args.kind == "case" else validate_snapshot(value, strict=args.strict)
            if args.json:
                _print_json(report.as_dict())
            else:
                print(f"validation: {'PASS' if report.ok else 'FAIL'} | errors={report.errors} warnings={report.warnings}")
                for item in report.findings:
                    print(f"{item.severity.upper()} {item.code} {item.path}: {item.message}")
            return 0 if report.ok else 1

        if args.command == "freeze":
            case = load_json(args.case)
            snapshot = freeze_case(case, args.cutoff)
            if args.output:
                write_json(args.output, snapshot)
                print(args.output)
            else:
                _print_json(snapshot)
            return 0

        if args.command == "replay":
            snapshot = _snapshot_from_args(args.case, args.snapshot, args.cutoff)
            result = replay_decision(snapshot, rule_version_id=args.rule_version_id)
            review = None
            diff = None
            if args.format == "html" and args.case:
                case = load_json(args.case)
                if case.get("review"):
                    review = review_decision(case)
                    later = freeze_case(case, case["review"]["reviewed_at"])
                    diff = compare_snapshots(freeze_case(case, case["decision"]["decision_cutoff"]), later)
            _write_or_print(render("replay", result, format_name=args.format, related=review, diff=diff), args.output)
            return 0

        if args.command == "review":
            case = load_json(args.case)
            result = review_decision(case, review_cutoff=args.cutoff)
            _write_or_print(render("review", result, format_name=args.format), args.output)
            return 0

        if args.command == "diff":
            case = load_json(args.case)
            result = compare_snapshots(freeze_case(case, args.before), freeze_case(case, args.after))
            if args.output:
                write_json(args.output, result)
                print(args.output)
            else:
                _print_json(result)
            return 0

        if args.command == "trace":
            case = load_json(args.case)
            decision_snapshot = freeze_case(case, case["decision"]["decision_cutoff"])
            replay = replay_decision(decision_snapshot)
            later_snapshot = freeze_case(case, case["review"]["reviewed_at"])
            review = review_decision(case)
            comparison = compare_snapshots(decision_snapshot, later_snapshot)
            target = Path(args.output)
            target.unlink(missing_ok=True)
            chain = AuditChain(target)
            chain.append("decision.snapshot", decision_snapshot["cutoff"], {"fingerprint": decision_snapshot["snapshot_fingerprint"]})
            chain.append("decision.replay", case["decision"]["recorded_at"], {"fingerprint": replay["replay_fingerprint"], "selected": replay["selected_option_id"]})
            chain.append("decision.review", review["reviewed_at"], {"fingerprint": review["review_fingerprint"], "quadrant": review["decision_quality_quadrant"]})
            chain.append("decision.diff", later_snapshot["cutoff"], {"fingerprint": comparison["diff_fingerprint"]})
            verification = chain.verify()
            if not verification.ok:
                raise ValueError(f"created audit chain failed verification: {verification.message}")
            if args.checkpoint:
                records = list(chain.read())
                write_json(args.checkpoint, create_checkpoint(records))
            print(target)
            return 0

        if args.command == "audit":
            chain = AuditChain(args.path)
            verification = chain.verify()
            payload: dict[str, Any] = {"chain": verification.as_dict()}
            if args.checkpoint:
                payload["checkpoint"] = verify_checkpoint(list(chain.read()), load_json(args.checkpoint))
            payload["ok"] = verification.ok and payload.get("checkpoint", {"ok": True})["ok"]
            if args.json:
                _print_json(payload)
            else:
                print(f"audit: {'PASS' if payload['ok'] else 'FAIL'} | records={verification.record_count} message={verification.message}")
            return 0 if payload["ok"] else 1

        if args.command == "lab":
            case = load_json(args.case)
            before = freeze_case(case, case["decision"]["decision_cutoff"])
            after = freeze_case(case, case["review"]["reviewed_at"])
            replay = replay_decision(before)
            review = review_decision(case)
            comparison = compare_snapshots(before, after)
            _write_or_print(render("replay", replay, format_name="html", related=review, diff=comparison), args.output)
            return 0

        if args.command == "fingerprint":
            print(digest(load_json(args.path)))
            return 0

        if args.command == "scaffold":
            write_json(args.output, _scaffold())
            print(args.output)
            return 0

        if args.command == "self-test":
            result = _self_test(Path(args.root).resolve())
            if args.json:
                _print_json(result)
            else:
                print(f"self-test: PASS | cases={result['case_count']} mutants={result['mutant_count']}")
                for item in result["cases"]:
                    print(f"CASE {item['case_id']} selected={item['selected_option_id']} quadrant={item['quadrant']}")
                for item in result["mutants"]:
                    print(f"MUTANT {item['case_id']} gates={','.join(item['failed_hard_gates'])}")
            return 0

    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(args.command)
