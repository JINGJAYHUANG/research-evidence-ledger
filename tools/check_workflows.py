#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ACTION = re.compile(r"(?m)^\s*(?:-\s*)?uses:\s*[^#\s]+@([^\s#]+)")
RUN_BLOCK = re.compile(r"^(?P<indent>\s*)(?:-\s*)?run:\s*\|[-+]?\s*$")
HEREDOC = re.compile(r"(?:^|\s)python(?:[0-9.]*)?\s+-\s+<<-?['\"]?(?P<tag>[A-Za-z_][A-Za-z0-9_]*)['\"]?\s*$")
EXPR = re.compile(r"\$\{\{.*?\}\}")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def run_blocks(text: str):
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = RUN_BLOCK.match(lines[index])
        if not match:
            index += 1
            continue
        parent = len(match.group("indent"))
        start = index + 2
        index += 1
        block = []
        while index < len(lines):
            line = lines[index]
            if line.strip() and _indent(line) <= parent:
                break
            block.append(line)
            index += 1
        widths = [_indent(line) for line in block if line.strip()]
        content_indent = min(widths) if widths else parent + 2
        yield start, "\n".join(line[content_indent:] if line.strip() else "" for line in block) + "\n"


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors = []
    if "\t" in text:
        errors.append(f"{path}: tabs are not allowed")
    if not re.search(r"(?m)^name:\s*\S", text) or not re.search(r"(?m)^on:\s*(?:$|\S)", text) or not re.search(r"(?m)^jobs:\s*$", text):
        errors.append(f"{path}: missing name, on, or jobs")
    for reference in ACTION.findall(text):
        if not re.fullmatch(r"[0-9a-f]{40}", reference):
            errors.append(f"{path}: unpinned third-party action {reference}")
    bash = shutil.which("bash")
    for start, script in run_blocks(text):
        label = f"{path}:run@{start}"
        lines = script.splitlines()
        i = 0
        while i < len(lines):
            match = HEREDOC.search(lines[i])
            if not match:
                i += 1
                continue
            tag = match.group("tag")
            body = []
            i += 1
            while i < len(lines) and lines[i].strip() != tag:
                body.append(lines[i])
                i += 1
            if i >= len(lines):
                errors.append(f"{label}: unterminated Python heredoc {tag}")
                break
            try:
                compile("\n".join(body) + "\n", f"{label}:{tag}", "exec")
            except SyntaxError as exc:
                errors.append(f"{label}: {exc}")
            i += 1
        if bash:
            with tempfile.NamedTemporaryFile("w", suffix=".sh", encoding="utf-8", delete=False) as handle:
                handle.write(EXPR.sub("GITHUB_EXPRESSION", script))
                temp = Path(handle.name)
            try:
                result = subprocess.run([bash, "-n", str(temp)], text=True, capture_output=True, timeout=10)
                if result.returncode:
                    errors.append(f"{label}: bash syntax failed: {(result.stderr or result.stdout).strip()}")
            finally:
                temp.unlink(missing_ok=True)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    paths = sorted([*(root / ".github/workflows").glob("*.yml"), *(root / ".github/workflows").glob("*.yaml")])
    errors = [error for path in paths for error in check(path)]
    if not paths:
        errors.append("no workflow files found")
    if errors:
        print("workflow check failed:")
        print("\n".join(errors))
        return 1
    print(f"workflow check passed: {len(paths)} workflow file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
