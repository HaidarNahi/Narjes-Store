"""
Unit tests for narjes_custom.ai_intake.matching

These tests are pure Python — zero Frappe DB, zero AI dependency.
Run with: python -m pytest apps/narjes_custom/narjes_custom/ai_intake/tests/test_matching.py -v
"""

import os
import sys

# Allow running without Frappe context
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import unittest
from unittest.mock import patch

from narjes_custom.ai_intake.matching import (
    find_customer_by_phone,
    match_customer,
    normalize_phone,
    normalize_stored_phone,
)


class TestNormalizePhone(unittest.TestCase):
    """Test Iraqi phone number normalization to canonical 07XXXXXXXXX format."""

    # ── Standard Iraqi format ──────────────────────────────────────────────
    def test_standard_07_format(self):
        self.assertEqual(normalize_phone("07701234567"), "07701234567")

    def test_standard_with_spaces(self):
        self.assertEqual(normalize_phone("0770 123 4567"), "07701234567")

    def test_standard_with_dashes(self):
        self.assertEqual(normalize_phone("0770-123-4567"), "07701234567")

    def test_standard_with_mixed_separators(self):
        self.assertEqual(normalize_phone("077 0-123 4567"), "07701234567")

    # ── Country code variants ──────────────────────────────────────────────
    def test_plus_964(self):
        self.assertEqual(normalize_phone("+9647701234567"), "07701234567")

    def test_00964(self):
        self.assertEqual(normalize_phone("009647701234567"), "07701234567")

    def test_964_without_prefix(self):
        """13-digit number starting with 964 (no leading 00 or +)."""
        self.assertEqual(normalize_phone("9647701234567"), "07701234567")

    def test_plus_964_with_spaces(self):
        self.assertEqual(normalize_phone("+964 770 123 4567"), "07701234567")

    # ── Stored Int format (missing leading 0) ─────────────────────────────
    def test_stored_int_10_digits(self):
        """Int field stores 7701234567 (dropped leading 0 from 07701234567)."""
        self.assertEqual(normalize_phone("7701234567"), "07701234567")

    def test_stored_int_as_integer(self):
        self.assertEqual(normalize_stored_phone(7701234567), "07701234567")

    def test_stored_int_zero(self):
        self.assertEqual(normalize_stored_phone(0), "")

    def test_stored_int_none(self):
        self.assertEqual(normalize_stored_phone(None), "")

    # ── Umnati / Zain / Asia Cell prefixes ────────────────────────────────
    def test_07x_prefixes(self):
        """Different Iraqi operator prefixes."""
        for prefix in ["0770", "0771", "0772", "0773", "0774",
                       "0780", "0781", "0782", "0783", "0784",
                       "0790", "0791", "0792", "0793", "0794",
                       "0750", "0751", "0752", "0753"]:
            number = f"{prefix}1234567"
            result = normalize_phone(number)
            self.assertEqual(result, number, f"Failed for {number}")

    # ── Edge cases ─────────────────────────────────────────────────────────
    def test_empty_string(self):
        self.assertEqual(normalize_phone(""), "")

    def test_none_input(self):
        self.assertEqual(normalize_phone(None), "")

    def test_non_phone_string(self):
        """A string with no digits should return empty."""
        self.assertEqual(normalize_phone("no phone"), "")

    def test_parentheses(self):
        self.assertEqual(normalize_phone("(0770) 123-4567"), "07701234567")


class TestNormalizeArabicDigits(unittest.TestCase):
    """Every real order message writes numbers in Arabic-Indic digits. The old
    normaliser kept them as they were, so those numbers never matched."""

    def test_arabic_indic_digits(self):
        self.assertEqual(normalize_phone("٠٧٧٠١٢٣٤٥٦٧"), "07701234567")
        self.assertEqual(normalize_phone("\u202d+٩٦٤ ٧٧٠ ١٢٣ ٤٥٦٧\u202c"), "07701234567")

    def test_invalid_lengths_are_rejected(self):
        self.assertEqual(normalize_phone("077012345678"), "")
        self.assertEqual(normalize_phone("0770 123 456"), "")


def _resolution(status, customer=None, candidates=()):
    return {"status": status, "customer": customer, "candidates": list(candidates)}


class TestMatchCustomer(unittest.TestCase):
    """match_customer is phone-only; resolution itself is tested in
    tests/test_customer_phones.py."""

    @patch("narjes_custom.ai_intake.matching.customer_phones.resolve")
    def test_phones_are_canonicalised_before_lookup(self, resolve):
        resolve.return_value = _resolution("MATCHED", "Ahmed")
        result = match_customer(["0770 123 4567", "not a phone", "", None], "Ahmed Mohammed")
        resolve.assert_called_once_with(["+9647701234567"])
        self.assertEqual(result["customer"], "Ahmed")
        self.assertEqual(result["method"], "Phone")
        self.assertEqual(result["confidence"], 100.0)

    @patch("narjes_custom.ai_intake.matching.customer_phones.resolve")
    def test_name_never_matters(self, resolve):
        resolve.return_value = _resolution("NEW")
        a = match_customer(["07701234567"], "Ahmed Mohammed")
        b = match_customer(["07701234567"], "someone else entirely")
        c = match_customer(["07701234567"])
        self.assertEqual(a, b)
        self.assertEqual(b, c)
        self.assertIsNone(a["customer"])

    @patch("narjes_custom.ai_intake.matching.customer_phones.resolve")
    def test_no_phone_never_matches_even_with_a_name(self, resolve):
        resolve.return_value = _resolution("NO_PHONE")
        result = match_customer([], "Ahmed Mohammed")
        resolve.assert_called_once_with([])
        self.assertIsNone(result["customer"])
        self.assertEqual(result["method"], "None")

    @patch("narjes_custom.ai_intake.matching.customer_phones.resolve")
    def test_conflict_is_not_guessed(self, resolve):
        resolve.return_value = _resolution("CONFLICT", candidates=["Ahmed", "Hussein"])
        result = match_customer(["07701234567", "07801111111"])
        self.assertIsNone(result["customer"])
        self.assertEqual(result["method"], "Conflict")
        self.assertEqual(result["candidates"], ["Ahmed", "Hussein"])
        self.assertIsNone(find_customer_by_phone(["07701234567", "07801111111"]))

    @patch("narjes_custom.ai_intake.matching.customer_phones.resolve")
    def test_find_customer_by_phone(self, resolve):
        resolve.return_value = _resolution("MATCHED", "Hussein")
        self.assertEqual(find_customer_by_phone(["+964 780 111 1111"]), "Hussein")


if __name__ == "__main__":
    unittest.main()
