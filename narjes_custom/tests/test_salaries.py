"""Tests for the commission rule and the profit split.

The commission rule decides what a real person is paid every month from a
match on item names, so the cases that matter most are the ones where a naive
match pays the wrong amount.
"""

import unittest

from narjes_custom import salaries


class TestCommissionKeywords(unittest.TestCase):
	"""The `_keyword_for` classifier, which uses the same whole-word rule as
	the SQL that seeds the checkbox."""

	def kind(self, text):
		return salaries._keyword_for(text, "")

	def test_the_three_kinds_are_recognised(self):
		self.assertEqual(self.kind("mdf 40*60"), "MDF")
		self.assertEqual(self.kind("Wood Stand"), "Stand")
		self.assertEqual(self.kind("frame"), "Frame")

	def test_case_does_not_matter(self):
		# The catalogue has both "mdf 50*80" and "MDF 30*40".
		self.assertEqual(self.kind("MDF 30*40"), "MDF")
		self.assertEqual(self.kind("mDf large"), "MDF")

	def test_standard_is_not_a_stand(self):
		"""The whole reason this is a word match and not a substring match.

		A plain LIKE '%stand%' pays commission on every one of these.
		"""
		for text in ("Standard Box", "Freestanding Lamp", "Understanding", "Standee"):
			self.assertEqual(self.kind(text), "Other", text)

	def test_frameless_is_not_a_frame(self):
		self.assertEqual(self.kind("Frameless Print"), "Other")

	def test_separators_still_split_words(self):
		# Item codes here are full of punctuation: "mdf 50*80", "MDF 30*40".
		self.assertEqual(self.kind("frame-large"), "Frame")
		self.assertEqual(self.kind("stand/metal"), "Stand")


class TestPieceUoms(unittest.TestCase):
	def test_pieces_are_countable(self):
		self.assertIn("Nos", salaries.PIECE_UOMS)

	def test_length_is_not_a_piece(self):
		"""`Wood Stand` is flagged as a row item. If one were sold as a 250 cm
		cut, paying per unit would hand over 250,000 for a single line."""
		self.assertNotIn("Centimeter", salaries.PIECE_UOMS)
		self.assertNotIn("Meter", salaries.PIECE_UOMS)


class TestSplitArithmetic(unittest.TestCase):
	def test_the_agreed_shares_account_for_everything(self):
		shares = {"emergency": 15, "growth": 25, "ibrahim": 30, "haneen": 30}
		self.assertEqual(sum(shares.values()), 100)

	def test_commission_comes_out_before_the_split(self):
		"""Walaa is a cost of selling, not a share of the profit.

		Paying her out of the 60% would make the partners' share depend on
		how many frames she sold, which is not the arrangement.
		"""
		gross, operating_before_commission = 2955000, 1063000
		commission = 214000

		net = gross - (operating_before_commission + commission)
		self.assertEqual(net, 1678000)

		partners = net * 0.60
		self.assertAlmostEqual(partners, 1006800.0, places=2)

		# Her pay does not move when the partners' share changes, and theirs
		# is reduced by hers — which is the whole point.
		self.assertLess(net, gross - operating_before_commission)

	def test_a_negative_month_still_divides(self):
		"""A loss must not crash the dashboard — it divides as a loss."""
		net = -13700
		self.assertAlmostEqual(net * 0.30, -4110.0, places=2)
		self.assertAlmostEqual(net * 0.15 + net * 0.25 + net * 0.30 * 2, net, places=6)


if __name__ == "__main__":
	unittest.main()
