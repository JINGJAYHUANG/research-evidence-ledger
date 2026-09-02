from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_evidence_ledger.audit import AuditChain, GENESIS, create_checkpoint, merkle_root, verify_checkpoint


class AuditTests(unittest.TestCase):
    def test_empty_chain_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = AuditChain(Path(tmp) / "trace.jsonl").verify()
            self.assertTrue(result.ok)
            self.assertEqual(result.record_count, 0)
            self.assertIsNone(result.final_hash)

    def test_append_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(path)
            first = chain.append("decision.snapshot", "2026-01-01T00:00:00Z", {"id": 1})
            second = chain.append("decision.replay", "2026-01-01T00:01:00Z", {"id": 2})
            result = chain.verify()
            self.assertTrue(result.ok)
            self.assertEqual(result.record_count, 2)
            self.assertEqual(first["previous_hash"], GENESIS)
            self.assertEqual(second["previous_hash"], first["record_hash"])

    def test_sequence_contiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(path)
            chain.append("a", "2026-01-01T00:00:00Z", {})
            chain.append("b", "2026-01-01T00:01:00Z", {})
            records = [json.loads(line) for line in path.read_text().splitlines()]
            records[1]["sequence"] = 3
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            result = chain.verify()
            self.assertFalse(result.ok)
            self.assertEqual(result.message, "sequence mismatch")

    def test_payload_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(path)
            chain.append("a", "2026-01-01T00:00:00Z", {"value": 1})
            record = json.loads(path.read_text())
            record["payload"]["value"] = 2
            path.write_text(json.dumps(record) + "\n")
            self.assertEqual(chain.verify().message, "record hash mismatch")

    def test_previous_hash_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(path)
            chain.append("a", "2026-01-01T00:00:00Z", {})
            chain.append("b", "2026-01-01T00:01:00Z", {})
            records = [json.loads(line) for line in path.read_text().splitlines()]
            records[1]["previous_hash"] = GENESIS
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            self.assertEqual(chain.verify().message, "previous hash mismatch")

    def test_reorder_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(path)
            chain.append("a", "2026-01-01T00:00:00Z", {})
            chain.append("b", "2026-01-01T00:01:00Z", {})
            lines = path.read_text().splitlines()
            path.write_text("\n".join(reversed(lines)) + "\n")
            self.assertFalse(chain.verify().ok)

    def test_prefix_deletion_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(path)
            chain.append("a", "2026-01-01T00:00:00Z", {})
            chain.append("b", "2026-01-01T00:01:00Z", {})
            path.write_text(path.read_text().splitlines()[1] + "\n")
            self.assertFalse(chain.verify().ok)

    def test_invalid_json_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            path.write_text("{bad}\n")
            self.assertFalse(AuditChain(path).verify().ok)

    def test_non_object_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            path.write_text("[]\n")
            self.assertFalse(AuditChain(path).verify().ok)

    def test_checkpoint_empty(self):
        checkpoint = create_checkpoint([])
        self.assertEqual(checkpoint["record_count"], 0)
        self.assertEqual(checkpoint["signature_status"], "unsigned-fixture")
        self.assertFalse(checkpoint["authorship_proof"])
        self.assertFalse(checkpoint["external_timestamp_proof"])

    def test_checkpoint_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(path)
            chain.append("a", "2026-01-01T00:00:00Z", {})
            chain.append("b", "2026-01-01T00:01:00Z", {})
            records = list(chain.read())
            checkpoint = create_checkpoint(records)
            self.assertTrue(verify_checkpoint(records, checkpoint)["ok"])

    def test_checkpoint_change_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            chain = AuditChain(path)
            chain.append("a", "2026-01-01T00:00:00Z", {})
            records = list(chain.read())
            checkpoint = create_checkpoint(records)
            checkpoint["merkle_root"] = "sha256:" + "f" * 64
            self.assertFalse(verify_checkpoint(records, checkpoint)["ok"])

    def test_merkle_deterministic(self):
        hashes = ["sha256:" + "a" * 64, "sha256:" + "b" * 64, "sha256:" + "c" * 64]
        self.assertEqual(merkle_root(hashes), merkle_root(hashes))

    def test_merkle_order_sensitive(self):
        hashes = ["sha256:" + "a" * 64, "sha256:" + "b" * 64]
        self.assertNotEqual(merkle_root(hashes), merkle_root(list(reversed(hashes))))

    def test_append_is_deterministic_with_fixed_inputs(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            a = AuditChain(Path(left) / "trace.jsonl")
            b = AuditChain(Path(right) / "trace.jsonl")
            self.assertEqual(a.append("a", "2026-01-01T00:00:00Z", {"x": 1}), b.append("a", "2026-01-01T00:00:00Z", {"x": 1}))


def _make_length_test(count):
    def test(self):
        with tempfile.TemporaryDirectory() as tmp:
            chain = AuditChain(Path(tmp) / "trace.jsonl")
            for index in range(count):
                chain.append("event", f"2026-01-01T00:{index:02d}:00Z", {"index": index})
            result = chain.verify()
            self.assertTrue(result.ok)
            self.assertEqual(result.record_count, count)
    return test


for _count in range(1, 11):
    setattr(AuditTests, f"test_chain_length_{_count}", _make_length_test(_count))


if __name__ == "__main__":
    unittest.main()
