from __future__ import annotations

import unittest
from datetime import datetime, timezone

from research_evidence_ledger.canonical import canonical_json, digest, verify_digest
from research_evidence_ledger.timeutil import at_or_before, iso_utc, parse_timestamp, strictly_after


class CanonicalTests(unittest.TestCase):
    def test_keys_sorted(self):
        self.assertEqual(canonical_json({"b": 1, "a": 2}), '{"a":2,"b":1}')

    def test_tuple_normalized(self):
        self.assertEqual(canonical_json((1, 2)), "[1,2]")

    def test_negative_zero_normalized(self):
        self.assertEqual(canonical_json({"x": -0.0}), '{"x":0.0}')

    def test_nan_rejected(self):
        with self.assertRaises(ValueError):
            canonical_json({"x": float("nan")})

    def test_inf_rejected(self):
        with self.assertRaises(ValueError):
            canonical_json({"x": float("inf")})

    def test_unknown_type_rejected(self):
        with self.assertRaises(TypeError):
            canonical_json({"x": object()})

    def test_digest_prefixed(self):
        self.assertRegex(digest({"a": 1}), r"^sha256:[0-9a-f]{64}$")

    def test_digest_unprefixed(self):
        self.assertRegex(digest({"a": 1}, prefix=False), r"^[0-9a-f]{64}$")

    def test_digest_order_independent(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))

    def test_verify_digest(self):
        value = {"a": [1, 2]}
        self.assertTrue(verify_digest(value, digest(value)))

    def test_verify_digest_detects_change(self):
        self.assertFalse(verify_digest({"a": 2}, digest({"a": 1})))


class TimeTests(unittest.TestCase):
    def test_parse_z(self):
        self.assertEqual(parse_timestamp("2026-01-01T00:00:00Z").tzinfo, timezone.utc)

    def test_parse_offset_normalized(self):
        self.assertEqual(parse_timestamp("2026-01-01T08:00:00+08:00"), parse_timestamp("2026-01-01T00:00:00Z"))

    def test_naive_rejected(self):
        with self.assertRaises(ValueError):
            parse_timestamp("2026-01-01T00:00:00")

    def test_blank_rejected(self):
        with self.assertRaises(ValueError):
            parse_timestamp("")

    def test_at_or_before_equal(self):
        self.assertTrue(at_or_before("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))

    def test_at_or_before(self):
        self.assertTrue(at_or_before("2025-12-31T23:59:59Z", "2026-01-01T00:00:00Z"))

    def test_strictly_after(self):
        self.assertTrue(strictly_after("2026-01-01T00:00:01Z", "2026-01-01T00:00:00Z"))

    def test_iso_utc_from_offset(self):
        self.assertEqual(iso_utc("2026-01-01T08:00:00+08:00"), "2026-01-01T00:00:00Z")

    def test_iso_utc_datetime(self):
        self.assertEqual(iso_utc(datetime(2026, 1, 1, tzinfo=timezone.utc)), "2026-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
