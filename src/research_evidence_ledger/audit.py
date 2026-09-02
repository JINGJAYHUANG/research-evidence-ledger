from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .canonical import canonical_json, digest

GENESIS = "sha256:" + "0" * 64


@dataclass(frozen=True)
class AuditVerification:
    ok: bool
    record_count: int
    final_hash: str | None
    error_index: int | None = None
    message: str = "ok"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "record_count": self.record_count,
            "final_hash": self.final_hash,
            "error_index": self.error_index,
            "message": self.message,
        }


class AuditChain:
    """Local tamper-evident evidence chain; not a signature or authorship proof."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, event_type: str, observed_at: str, payload: dict[str, Any]) -> dict[str, Any]:
        records = list(self.read())
        previous = records[-1]["record_hash"] if records else GENESIS
        record: dict[str, Any] = {
            "schema_version": 1,
            "sequence": len(records) + 1,
            "event_type": event_type,
            "observed_at": observed_at,
            "payload": payload,
            "previous_hash": previous,
        }
        record["record_hash"] = digest(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(record) + "\n")
        return record

    def read(self) -> Iterable[dict[str, Any]]:
        if not self.path.exists():
            return iter(())

        def generate():
            with self.path.open(encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError(f"audit line {number} is not an object")
                    yield value
        return generate()

    def verify(self) -> AuditVerification:
        previous = GENESIS
        count = 0
        final_hash = None
        try:
            for index, record in enumerate(self.read(), 1):
                count = index
                if record.get("sequence") != index:
                    return AuditVerification(False, index - 1, final_hash, index, "sequence mismatch")
                if record.get("previous_hash") != previous:
                    return AuditVerification(False, index - 1, final_hash, index, "previous hash mismatch")
                payload = {key: value for key, value in record.items() if key != "record_hash"}
                actual = digest(payload)
                if record.get("record_hash") != actual:
                    return AuditVerification(False, index - 1, final_hash, index, "record hash mismatch")
                previous = actual
                final_hash = actual
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AuditVerification(False, count, final_hash, count + 1, str(exc))
        return AuditVerification(True, count, final_hash)


def _leaf_hash(value: str) -> str:
    return digest({"leaf": value})


def merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return digest({"empty": True})
    level = [_leaf_hash(item) for item in hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [digest({"left": level[index], "right": level[index + 1]}) for index in range(0, len(level), 2)]
    return level[0]


def create_checkpoint(records: list[dict[str, Any]]) -> dict[str, Any]:
    hashes = [record["record_hash"] for record in records]
    checkpoint: dict[str, Any] = {
        "schema_version": 1,
        "record_count": len(records),
        "first_hash": hashes[0] if hashes else None,
        "last_hash": hashes[-1] if hashes else None,
        "merkle_root": merkle_root(hashes),
        "signature_status": "unsigned-fixture",
        "authorship_proof": False,
        "external_timestamp_proof": False,
    }
    checkpoint["checkpoint_hash"] = digest(checkpoint)
    return checkpoint


def verify_checkpoint(records: list[dict[str, Any]], checkpoint: dict[str, Any]) -> dict[str, Any]:
    expected = create_checkpoint(records)
    return {
        "ok": expected == checkpoint,
        "expected": expected,
        "observed": checkpoint,
        "claim_boundary": "A matching checkpoint proves only mathematical consistency of the supplied fixture, not signer identity or external timestamping.",
    }
