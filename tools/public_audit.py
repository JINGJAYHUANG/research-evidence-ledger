#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {"", ".cff", ".csv", ".html", ".in", ".ini", ".json", ".jsonl", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
ALLOWED_EMAIL_SUFFIXES = ("@users.noreply.github.com", "@example.org", "@example.invalid")
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{30,}\b"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{30,}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "mainland_phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "windows_home": re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+"),
    "mac_home": re.compile(r"(?<![\w.-])/" + r"Users/[^/\s]+"),
    "linux_home": re.compile(r"(?<![\w.-])/" + r"home/[^/\s]+"),
    "webhook_secret": re.compile(r"https://hooks\.[^\s/]+/services/[A-Za-z0-9/_-]{20,}"),
}
FORBIDDEN_MARKERS = {
    "private_strategy": "goal49" + "-cloud-morning",
    "private_incubator": "JINGJAYHUANG/" + "try",
    "real_decision_marker": "real" + "-customer-decision",
}


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    excerpt: str

    def as_dict(self):
        return asdict(self)


def scan(root: Path) -> tuple[int, list[Finding]]:
    root = root.resolve()
    findings: list[Finding] = []
    count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            findings.append(Finding("unexpected-binary", relative.as_posix(), 0, path.suffix or "no suffix"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            findings.append(Finding("non-utf8", relative.as_posix(), 0, "could not decode as UTF-8"))
            continue
        count += 1
        for line_number, line in enumerate(text.splitlines(), 1):
            for code, pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    excerpt = match.group(0)
                    if code == "email" and excerpt.lower().endswith(tuple(value.lower() for value in ALLOWED_EMAIL_SUFFIXES)):
                        continue
                    findings.append(Finding(code, relative.as_posix(), line_number, excerpt[:120]))
            for code, marker in FORBIDDEN_MARKERS.items():
                if marker in line:
                    findings.append(Finding(code, relative.as_posix(), line_number, marker))
    return count, findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    count, findings = scan(Path(args.root))
    if findings:
        print(f"public audit failed: {len(findings)} finding(s) in {count} text file(s)")
        for item in findings:
            print(f"{item.code} {item.path}:{item.line} {item.excerpt}")
        return 1
    print(f"public audit passed: {count} text file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
