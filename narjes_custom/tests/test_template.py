"""Tests for narjes_custom.ai_intake.template — the order form read without AI.

All names, addresses and numbers are invented. The layouts are the shop's
own order forms (v1, v2, and v2 with the discount line), written with
Arabic-Indic digits and the invisible marks real messages carry.
"""

import unittest

from narjes_custom.ai_intake.template import parse, parse_iqd

A = "+9647700000101"
B = "+9647800000102"

V2 = """👤 اسم الزبون: زبون تجريبي
@ اسم المستخدم: test.user
📱 منصة الطلب: instgram
📅 تاريخ استلام الطلب: ٢٧/١٠
🚚 تاريخ تسليم الطلب: ان شاءالله ٣الى ٥ايام
🖼️ تفاصيل الطلب: لوحة كانفاس ٤٠*٦٠ عدد ١
🎁 تغليف هدية: بدون
📍 العنوان: بغداد - منطقة تجريبية
📞 رقم الهاتف: {phone}
💰 مبلغ الطلب: ٣٥ الف
🚚 خدمة التوصيل: ٥الاف
💳 المبلغ الكلي: ٤٠ الف
‼️ملاحظة: نص ثابت للاختبار"""

V1 = """🔹طلب باسم: زبونة تجريبية
🔹تاريخ استلام الطلب: ٢٧/١٠/٢٠٢٦
🔹تاريخ تسليم الطلب: ان شاءالله باجر مستعجل
📌تفاصيل الطلب: لوحة ٣٠*٤٠ مع ستاند خشب
🎁تغليف هدية او لا:
📍العنوان: البصرة - شارع تجريبي
📞رقم ‎الموبايل :
٠٧٧٠ ٠٠٠ ٠١٠١
الرقم الثاني : ٠٧٨٠٠٠٠٠١٠٢
💵 مبلغ الطلب: ٤٥الف
🚗خدمة التوصيل: مجاني
💵المبلغ الكلي: ٤٥ الف
‼️ملاحظة: نص ثابت للاختبار"""


def v2(phone="٠٧٧٠٠٠٠٠١٠١"):
    return V2.format(phone=phone)


class TestTemplateV2(unittest.TestCase):
    def test_fields(self):
        r = parse(v2())
        self.assertTrue(r.recognised)
        self.assertEqual(r.version, "v2")
        self.assertEqual(r.name, "زبون تجريبي")
        self.assertEqual(r.username, "test.user")
        self.assertEqual(r.platform, "instgram")
        self.assertEqual(r.address, "بغداد - منطقة تجريبية")
        self.assertEqual(r.amounts, {"order": 35000, "fee": 5000, "total": 40000})
        self.assertEqual(r.assumed_thousands, [])
        self.assertIs(r.gift_hint, False)

    def test_identity_phone_comes_from_the_phone_field(self):
        r = parse(v2())
        self.assertEqual(r.phone_source, "template")
        self.assertEqual(r.phone_keys, [A])
        self.assertEqual(r.phone_problems, [])

    def test_numbers_elsewhere_are_never_identity_phones(self):
        text = v2().replace("بغداد - منطقة تجريبية", "بغداد - اتصل على ٠٧٨٠٠٠٠٠١٠٢ عند الوصول")
        self.assertEqual(parse(text).phone_keys, [A])


class TestTemplateV1(unittest.TestCase):
    def test_fields_and_continuation_lines(self):
        r = parse(V1)
        self.assertTrue(r.recognised)
        self.assertEqual(r.version, "v1")
        self.assertEqual(r.name, "زبونة تجريبية")
        self.assertEqual(r.phone_source, "template")
        self.assertEqual(r.phone_keys, [A, B])
        self.assertEqual(r.amounts, {"order": 45000, "fee": 0, "total": 45000})
        self.assertIs(r.gift_hint, False)
        self.assertEqual(r.username, "")
        self.assertEqual(r.platform, "")


class TestPhoneSectionShapes(unittest.TestCase):
    """Every phone-field shape seen in real messages, inside a full v2 form."""

    SHAPES = (
        ("٠٧٧٠٠٠٠٠١٠١", [A], []),
        ("٠٧٧٠ ٠٠٠ ٠١٠١", [A], []),
        ("+٩٦٤ ٧٧٠ ٠٠٠ ٠١٠١", [A], []),
        ("+٩٦٤٧٧٠٠٠٠٠١٠١", [A], []),
        ("٧٧٠٠٠٠٠١٠١", [A], []),
        ("٧٧٠ ٠٠٠ ٠١٠١", [A], []),
        ("‭+٩٦٤ ٧٧٠ ٠٠٠ ٠١٠١‬", [A], []),
        ("(٠٧٧٠٠٠٠٠١٠١", [A], []),
        ("الرقم ٠٧٧٠٠٠٠٠١٠١", [A], []),
        ("٠٧٧٠٠٠٠٠١٠١ يفضل هذا الرقم", [A], []),
        ("+964 770 000 0101 +964 780 000 0102", [A, B], []),
        ("\n٠٧٧٠٠٠٠٠١٠١", [A], []),
        ("\nالرقم ١: ٠٧٧٠٠٠٠٠١٠١\nالرقم ٢: ٠٧٨٠٠٠٠٠١٠٢", [A, B], []),
        ("\n٠٧٧٠ ٠٠٠ ٠١٠١\nالرقم الثاني : ٠٧٨٠٠٠٠٠١٠٢", [A, B], []),
        ("..  ٠٧٧٠٠٠٠٠١٠١", [A], []),
        ("/٠٧٧٠٠٠٠٠١٠١", [A], []),
        ("الرقم الاول\n٠٧٧٠٠٠٠٠١٠١", [A], []),
        ("رقم احتياط : ٠٧٨٠٠٠٠٠١٠٢", [B], []),
        ("٠٧٧٠٠٠٠٠١٠١ - ٠٧٧٠٠٠٠٠١٠١", [A], []),
        ("\nرقم الهاتف ٠٧٧٠٠٠٠٠١٠١", [A], []),
    )

    def test_shapes(self):
        for phone, expected, problems in self.SHAPES:
            with self.subTest(phone=phone):
                r = parse(v2(phone))
                self.assertEqual(r.phone_source, "template")
                self.assertEqual(r.phone_keys, expected)
                self.assertEqual(r.phone_problems, problems)

    def test_unreadable_numbers_are_reported_not_guessed(self):
        for phone, problem in (("٠٧٧٠ ٠٠٠ ٠١٠", "0770 000 010"), ("٠٧٧٠٠٠٠٠١٠١٩", "077000001019")):
            with self.subTest(phone=phone):
                r = parse(v2(phone))
                self.assertEqual(r.phone_keys, [])
                self.assertEqual(r.phone_source, "none")
                self.assertEqual(r.phone_problems, [problem])

    def test_empty_phone_field(self):
        r = parse(v2(""))
        self.assertTrue(r.recognised)
        self.assertEqual(r.phone_keys, [])
        self.assertEqual(r.phone_source, "none")
        self.assertEqual(r.phone_problems, [])

    def test_an_unknown_field_ends_the_phone_section(self):
        # A newer form adds a discount line right under the phone field.
        text = v2("").replace("💰 مبلغ الطلب", "💸 قيمة الخصم: ٥ الاف\n💰 مبلغ الطلب")
        r = parse(text)
        self.assertEqual(r.phone_keys, [])
        self.assertEqual(r.amounts["discount"], 5000)
        text = v2("").replace("💰 مبلغ الطلب", "🧾 حقل جديد: ٠٧٨٠٠٠٠٠١٠٢\n💰 مبلغ الطلب")
        self.assertEqual(parse(text).phone_keys, [])


class TestFreeText(unittest.TestCase):
    def test_not_a_template(self):
        r = parse("مرحبا اريد لوحة ٣٠*٤٠\nرقمي ٠٧٧٠٠٠٠٠١٠١")
        self.assertFalse(r.recognised)
        self.assertIsNone(r.version)
        self.assertEqual(r.phone_source, "free_text")
        self.assertEqual(r.phone_keys, [A])

    def test_free_text_without_phone(self):
        r = parse("مرحبا اريد لوحة ٣٠*٤٠")
        self.assertEqual(r.phone_source, "none")
        self.assertEqual(r.phone_keys, [])

    def test_template_without_phone_label_falls_back_but_skips_money_and_dates(self):
        text = "\n".join(line for line in v2().splitlines() if "رقم الهاتف" not in line)
        text += "\nاتصلوا ٠٧٨٠٠٠٠٠١٠٢"
        r = parse(text)
        self.assertTrue(r.recognised)
        self.assertEqual(r.phone_source, "free_text")
        self.assertEqual(r.phone_keys, [B])
        self.assertTrue(r.notes)


class TestParseIqd(unittest.TestCase):
    def test_amounts(self):
        cases = {
            "٣٥ الف": (35000, False),
            "35الف": (35000, False),
            "5الاف": (5000, False),
            "35 الل": (35000, False),
            "35 الف تحويل على الماستر": (35000, False),
            "١٢٠ الف": (120000, False),
            "مجاني": (0, False),
            "35": (35000, True),
            "35,000": (35000, False),
            "45000": (45000, False),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_iqd(value), expected)

    def test_not_amounts(self):
        for value in ("تكسي", "", None, "   "):
            with self.subTest(value=value):
                self.assertIsNone(parse_iqd(value))


if __name__ == "__main__":
    unittest.main()
