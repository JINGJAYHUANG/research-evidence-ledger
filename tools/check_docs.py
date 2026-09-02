#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    errors: list[str] = []
    count = 0
    for path in sorted(root.rglob("*.md")):
        if any(part in {".git", ".venv", "build", "dist"} for part in path.relative_to(root).parts):
            continue
        count += 1
        text = path.read_text(encoding="utf-8")
        for raw in LINK.findall(text):
            target = raw.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                errors.append(f"{path.relative_to(root)}: link escapes repository: {raw}")
                continue
            if not resolved.exists():
                errors.append(f"{path.relative_to(root)}: missing link target: {raw}")
    if errors:
        print("documentation check failed:")
        print("\n".join(errors))
        return 1
    print(f"documentation check passed: {count} Markdown file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
