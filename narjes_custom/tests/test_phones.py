"""Tests for narjes_custom.phones — the one canonical phone form.

Every number here is synthetic (0770/0780/0750 000 01xx). Each shape seen in
real order messages (digits masked, see the intake v2 notes) is covered in
both ASCII and Arabic-Indic digits, because every real message uses the
latter.
"""

import unittest

from narjes_custom.phones import (
    canonical,
    clean_text,
    display,
    find_phones,
    national,
    unreadable_groups,
)

A = "+9647700000101"  # 0770 000 0101
B = "+9647800000102"  # 0780 000 0102
C = "+9647500000103"  # 0750 000 0103

_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def ar(s):
    return s.translate(_AR)


def both(s):
    """The ASCII and the Arabic-Indic spelling of the same text."""
    return [s, ar(s)]


class TestCleanText(unittest.TestCase):
    def test_arabic_indic_and_persian_digits_become_ascii(self):
        self.assertEqual(clean_text("٠٧٧٠"), "0770")
        self.assertEqual(clean_text("0770".translate(_FA)), "0770")
        self.assertEqual(clean_text("０７７０"), "0770")

    def test_invisible_marks_are_dropped_and_spaces_normalised(self):
        self.assertEqual(clean_text("‭+964‬‎"), "+964")
        self.assertEqual(clean_text("0770 000 0101"), "0770 000 0101")

    def test_none(self):
        self.assertEqual(clean_text(None), "")


class TestCanonical(unittest.TestCase):
    def assertCanon(self, raws, expected):
        for raw in raws:
            with self.subTest(raw=raw):
                self.assertEqual(canonical(raw), expected)

    def test_plain_forms(self):
        self.assertCanon(both("07700000101"), A)
        self.assertCanon(["07700000101".translate(_FA), "０７７０００００１０１"], A)

    def test_separators(self):
        for s in ["0770 000 0101", "0770-000-0101", "0770.000.0101", "(0770) 000 0101"]:
            self.assertCanon(both(s), A)

    def test_country_code_forms(self):
        for s in ["+964 770 000 0101", "+9647700000101", "009647700000101", "9647700000101", "+964 (0) 770 000 0101"]:
            self.assertCanon(both(s), A)

    def test_ten_digits_without_leading_zero(self):
        self.assertCanon(both("770 000 0101") + both("7700000101"), A)
        self.assertEqual(canonical(7700000101), A)

    def test_invisible_marks(self):
        self.assertCanon(
            ["‭+964 770 000 0101‬", "‎07700000101‏", "07700000101 ", "⁦٠٧٧٠٠٠٠٠١٠١⁩"],
            A,
        )

    def test_other_operators(self):
        self.assertEqual(canonical("07800000102"), B)
        self.assertEqual(canonical("07500000103"), C)

    def test_same_number_twice_is_one_number(self):
        self.assertCanon(both("07700000101 07700000101"), A)

    def test_two_different_numbers_are_ambiguous(self):
        self.assertCanon(both("07700000101 / 07800000102"), None)

    def test_invalid_or_empty(self):
        self.assertCanon(
            both("077000001019") + both("0770 000 010") + ["12345", "abc", "", "   ", None, 0], None
        )

    def test_foreign_numbers_need_a_plus(self):
        # A bare foreign number is read as Iraqi and fails validation.
        self.assertIsNone(canonical("971500000101"))
        uae = canonical("+971 50 000 0101")
        self.assertTrue(uae is None or uae == "+971500000101")


class TestFindPhones(unittest.TestCase):
    """Phone-section shapes seen in real messages (Appendix A2 of the plan)."""

    CASES = (
        ("📞 رقم الهاتف: 07700000101", [A]),
        ("📞 رقم الهاتف: 0770 000 0101", [A]),
        ("📞 رقم الهاتف: +964 770 000 0101", [A]),
        ("📞 رقم الهاتف: +9647700000101", [A]),
        ("📞 رقم الهاتف: 7700000101", [A]),
        ("📞 رقم الهاتف: 770 000 0101", [A]),
        ("📞 رقم الهاتف: ‭+964 770 000 0101‬", [A]),
        ("📞 رقم الهاتف: (07700000101", [A]),
        ("📞 رقم الهاتف: الرقم 07700000101", [A]),
        ("📞 رقم الهاتف: 07700000101 يفضل هذا الرقم", [A]),
        ("📞 رقم الهاتف: +964 770 000 0101 +964 780 000 0102", [A, B]),
        ("📞 رقم الهاتف:\n07700000101", [A]),
        ("📞 رقم الهاتف:\nالرقم 1: 07700000101\nالرقم 2: 07800000102", [A, B]),
        ("📞 رقم الهاتف:\n0770 000 0101\nالرقم الثاني : 07800000102", [A, B]),
        ("📞رقم ‎الموبايل :\n‪0770 000 0101‬", [A]),
        ("📞 رقم الهاتف: ..  07700000101", [A]),
        ("📞 رقم الهاتف: /07700000101", [A]),
        ("📞 رقم الهاتف: 07700000101 الاتصال على هذا الرقم", [A]),
        ("📞 رقم الهاتف: الرقم الاول\n07700000101", [A]),
        ("📞 رقم الهاتف: رقم احتياط : 07800000102", [B]),
        ("📞 رقم الهاتف: الرقم 2 07700000101", [A]),
        ("📞 رقم الهاتف: 07700000101 - 07700000101", [A]),
        ("📞 رقم الهاتف: 0750 000 0103", [C]),
        ("770 000 0101 780 000 0102", [A, B]),
        ("📞 رقم الهاتف: 0770 000 010", []),
        ("📞 رقم الهاتف: 077000001019", []),
        ("📞 رقم الهاتف:", []),
    )

    def test_shapes_in_ascii_and_arabic_digits(self):
        for text, expected in self.CASES:
            for variant in both(text):
                with self.subTest(text=variant):
                    self.assertEqual([h.e164 for h in find_phones(variant)], expected)

    def test_non_phone_lines_produce_nothing(self):
        for line in [
            "💰 مبلغ الطلب: 35 الف",
            "📅 تاريخ استلام الطلب: 27/10/2026",
            "🖼️ تفاصيل الطلب: لوحة 40*60 عدد 2",
            "🚚 تاريخ تسليم الطلب: ان شاءالله 3الى 5ايام",
            "💳 المبلغ الكلي: 40 الف",
            "2026-10-27",
        ]:
            for variant in both(line):
                with self.subTest(line=variant):
                    self.assertEqual(find_phones(variant), [])
                    self.assertEqual(unreadable_groups(variant), [])


class TestUnreadableGroups(unittest.TestCase):
    def test_numbers_that_cannot_be_read_are_reported(self):
        self.assertEqual(unreadable_groups(ar("📞 رقم الهاتف: 0770 000 010")), ["0770 000 010"])
        self.assertEqual(unreadable_groups(ar("📞 رقم الهاتف: 077000001019")), ["077000001019"])

    def test_readable_numbers_are_not_reported(self):
        for text in ["07700000101", "07700000101 - 07700000101", "الرقم 2 07700000101", "+964 770 000 0101 +964 780 000 0102"]:
            with self.subTest(text=text):
                self.assertEqual(unreadable_groups(ar(text)), [])


class TestFormatting(unittest.TestCase):
    def test_national_is_how_the_shop_stores_numbers(self):
        self.assertEqual(national(A), "07700000101")
        self.assertEqual(national(""), "")
        self.assertEqual(national("+971500000101"), "+971500000101")

    def test_display(self):
        self.assertEqual(display(A), "0770 000 0101")
        self.assertEqual(display(""), "")
        self.assertTrue(display("+971500000101").startswith("+971"))


if __name__ == "__main__":
    unittest.main()
