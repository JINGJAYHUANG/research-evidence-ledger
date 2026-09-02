from __future__ import annotations

from datetime import datetime, timezone


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp must include timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: str | datetime) -> str:
    parsed = parse_timestamp(value) if isinstance(value, str) else value.astimezone(timezone.utc)
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def at_or_before(value: str, cutoff: str) -> bool:
    return parse_timestamp(value) <= parse_timestamp(cutoff)


def strictly_after(value: str, cutoff: str) -> bool:
    return parse_timestamp(value) > parse_timestamp(cutoff)
