#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    directory = root / "examples/generated"
    manifest_path = directory / "generated-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = []
    expected = set(manifest["files"])
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if expected != actual:
        errors.append(f"file set mismatch: missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    for relative, metadata in manifest["files"].items():
        path = directory / relative
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) != metadata["bytes"]:
            errors.append(f"byte count mismatch: {relative}")
        if hashlib.sha256(data).hexdigest() != metadata["sha256"]:
            errors.append(f"digest mismatch: {relative}")
    if manifest["file_count"] != len(manifest["files"]):
        errors.append("manifest file_count mismatch")
    if errors:
        print("generated artifact audit failed:")
        print("\n".join(errors))
        return 1
    print(f"generated artifact audit passed: {len(expected)} managed file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
