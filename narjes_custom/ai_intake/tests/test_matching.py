"""
Unit tests for narjes_custom.ai_intake.matching

These tests are pure Python — zero Frappe DB, zero AI dependency.
Run with: python -m pytest apps/narjes_custom/narjes_custom/ai_intake/tests/test_matching.py -v
"""

import sys
import os

# Allow running without Frappe context
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import unittest
from unittest.mock import patch, MagicMock

from narjes_custom.ai_intake.matching import normalize_phone, normalize_stored_phone


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


class TestMatchCustomer(unittest.TestCase):
    """Test match_customer with mocked Frappe DB calls."""

    def _make_customers(self):
        return [
            {"name": "Ahmed", "customer_name": "Ahmed Mohammed", "main_phone_number": 7701234567, "secondary_phone_number": 0},
            {"name": "Hussein", "customer_name": "Hussein Ali", "main_phone_number": 7905551234, "secondary_phone_number": 7801111111},
            {"name": "Hamoody", "customer_name": "Hamoody", "main_phone_number": 0, "secondary_phone_number": 0},
        ]

    @patch("narjes_custom.ai_intake.matching.frappe")
    def test_phone_match_standard_format(self, mock_frappe):
        """Match by phone — 07701234567 matches Ahmed (stored as 7701234567)."""
        mock_frappe.get_all.return_value = self._make_customers()

        from narjes_custom.ai_intake.matching import match_customer
        result = match_customer(["07701234567"], "Unknown Name")

        self.assertEqual(result["customer"], "Ahmed")
        self.assertEqual(result["method"], "Phone")
        self.assertEqual(result["confidence"], 100.0)

    @patch("narjes_custom.ai_intake.matching.frappe")
    def test_phone_match_country_code(self, mock_frappe):
        """+9647701234567 should match Ahmed (same number, different format)."""
        mock_frappe.get_all.return_value = self._make_customers()

        from narjes_custom.ai_intake.matching import match_customer
        result = match_customer(["+9647701234567"], "")

        self.assertEqual(result["customer"], "Ahmed")
        self.assertEqual(result["method"], "Phone")

    @patch("narjes_custom.ai_intake.matching.frappe")
    def test_phone_match_secondary(self, mock_frappe):
        """Match on secondary phone number."""
        mock_frappe.get_all.return_value = self._make_customers()

        from narjes_custom.ai_intake.matching import match_customer
        result = match_customer(["07801111111"], "")

        self.assertEqual(result["customer"], "Hussein")
        self.assertEqual(result["method"], "Phone")

    @patch("narjes_custom.ai_intake.matching.frappe")
    def test_fuzzy_name_exact(self, mock_frappe):
        """Exact name match → fuzzy score 100."""
        mock_frappe.get_all.return_value = self._make_customers()

        from narjes_custom.ai_intake.matching import match_customer
        result = match_customer([], "Ahmed Mohammed")

        self.assertEqual(result["customer"], "Ahmed")
        self.assertEqual(result["method"], "Fuzzy Name")
        self.assertGreaterEqual(result["confidence"], 85)

    @patch("narjes_custom.ai_intake.matching.frappe")
    def test_fuzzy_name_transliteration(self, mock_frappe):
        """'حسين علي' vs 'Hussein Ali' — cross-language, may not match (acceptable)."""
        mock_frappe.get_all.return_value = self._make_customers()

        from narjes_custom.ai_intake.matching import match_customer
        # Arabic transliteration — fuzzy match may or may not hit threshold
        # Test that it returns a valid result without crashing
        result = match_customer([], "حسين علي")
        self.assertIn(result["method"], ["Fuzzy Name", "None"])

    @patch("narjes_custom.ai_intake.matching.frappe")
    def test_no_match_low_confidence(self, mock_frappe):
        """Completely different name + no phone → no match."""
        mock_frappe.get_all.return_value = self._make_customers()

        from narjes_custom.ai_intake.matching import match_customer
        result = match_customer([], "Completely Different Person XYZ")

        self.assertEqual(result["method"], "None")
        self.assertIsNone(result["customer"])
        self.assertEqual(result["confidence"], 0.0)

    @patch("narjes_custom.ai_intake.matching.frappe")
    def test_no_match_empty_inputs(self, mock_frappe):
        """Empty phones and empty name → no match."""
        mock_frappe.get_all.return_value = self._make_customers()

        from narjes_custom.ai_intake.matching import match_customer
        result = match_customer([], "")

        self.assertEqual(result["method"], "None")
        self.assertIsNone(result["customer"])

    @patch("narjes_custom.ai_intake.matching.frappe")
    def test_phone_takes_priority_over_fuzzy(self, mock_frappe):
        """Even if name is fuzzy-matching Hussein, phone match to Ahmed wins."""
        mock_frappe.get_all.return_value = self._make_customers()

        from narjes_custom.ai_intake.matching import match_customer
        # Phone matches Ahmed, name vaguely matches Hussein
        result = match_customer(["07701234567"], "Hussein Something")

        # Phone match should win
        self.assertEqual(result["customer"], "Ahmed")
        self.assertEqual(result["method"], "Phone")


if __name__ == "__main__":
    unittest.main()
