from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite numbers are not permitted")
        if value == 0.0:
            return 0.0
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value: Any, *, prefix: bool = True) -> str:
    result = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{result}" if prefix else result


def verify_digest(value: Any, expected: str) -> bool:
    return digest(value, prefix=expected.startswith("sha256:")) == expected
