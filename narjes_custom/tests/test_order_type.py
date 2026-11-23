"""Order Type (Sales Order.design_type) detection for AI intake — no site needed."""

import unittest

from narjes_custom.ai_intake import extraction
from narjes_custom.ai_intake import order_type as ot

OPTIONS = ["حج", "عمره", "تخرج", "اعراس", "اطفال"]


class TestNormalize(unittest.TestCase):
	def test_exact_option(self):
		for opt in OPTIONS:
			self.assertEqual(ot.normalize(opt, OPTIONS), opt)

	def test_spelling_variants_map_to_the_option(self):
		self.assertEqual(ot.normalize("عمرة", OPTIONS), "عمره")
		self.assertEqual(ot.normalize("أطفال", OPTIONS), "اطفال")
		self.assertEqual(ot.normalize("زواج", OPTIONS), "اعراس")
		self.assertEqual(ot.normalize("حفلة تخرج", OPTIONS), "تخرج")
		self.assertEqual(ot.normalize("Wedding", OPTIONS), "اعراس")

	def test_unknown_or_empty_is_blank(self):
		self.assertEqual(ot.normalize("عيد ميلاد", OPTIONS), "")
		self.assertEqual(ot.normalize(None, OPTIONS), "")
		self.assertEqual(ot.normalize("", OPTIONS), "")

	def test_only_existing_options_are_returned(self):
		self.assertEqual(ot.normalize("زواج", ["حج", "تخرج"]), "")


class TestDetect(unittest.TestCase):
	def test_reads_each_occasion_from_a_message(self):
		cases = {
			"🖼️ تفاصيل الطلب: لوحة 40*60 للحاج ابو علي بمناسبة رجوعه من الحج": "حج",
			"لوحة تهنئة بمناسبة العمرة المباركة": "عمره",
			"درع تخرج باسم الخريجة زينب - كلية الطب": "تخرج",
			"لوحة للعروس والعريس مع تاريخ الزفاف": "اعراس",
			"تفاصيل الطلب: لوحة مولود جديد باسم الطفل علي": "اطفال",
			"وللتخرج نريد كتابة السنة": "تخرج",
		}
		for text, expected in cases.items():
			with self.subTest(text=text):
				self.assertEqual(ot.detect(text, OPTIONS), expected)

	def test_size_is_not_hajj(self):
		"""'حج' is inside 'حجم' (size), on almost every order."""
		self.assertEqual(ot.detect("لوحة حجم 30*40 كانفاس", OPTIONS), "")

	def test_his_age_is_not_umrah(self):
		"""'عمره' is also 'his age' — the kids word wins."""
		self.assertEqual(ot.detect("لوحة طفل عمره سنتين", OPTIONS), "اطفال")

	def test_umrah_alone_still_counts(self):
		self.assertEqual(ot.detect("لوحة عمره لوالدتي", OPTIONS), "عمره")

	def test_two_occasions_is_left_to_the_reviewer(self):
		self.assertEqual(ot.detect("لوحة تخرج وهدية عرس", OPTIONS), "")

	def test_nothing_named(self):
		self.assertEqual(ot.detect("لوحة MDF 30*40 مع ستاند", OPTIONS), "")


class TestResolve(unittest.TestCase):
	def test_ai_answer_wins_when_valid(self):
		self.assertEqual(ot.resolve("تخرج", "لوحة عرس", OPTIONS), "تخرج")

	def test_falls_back_to_the_message(self):
		self.assertEqual(ot.resolve(None, "لوحة عرس", OPTIONS), "اعراس")
		self.assertEqual(ot.resolve("غير معروف", "لوحة عرس", OPTIONS), "اعراس")


class TestSchema(unittest.TestCase):
	def test_enum_holds_the_field_options(self):
		schema = extraction.extraction_schema(OPTIONS)
		self.assertEqual(schema["properties"]["order_type"]["enum"], OPTIONS)
		self.assertTrue(schema["properties"]["order_type"]["nullable"])
		self.assertNotIn("order_type", extraction.EXTRACTION_SCHEMA["properties"])

	def test_no_options_means_no_empty_enum(self):
		self.assertNotIn("enum", extraction.extraction_schema([])["properties"]["order_type"])


if __name__ == "__main__":
	unittest.main()
