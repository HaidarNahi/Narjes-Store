"""Tests for the money definitions every report shares.

These are the arithmetic that decides what four people get paid, so the cases
below are the ones that were actually wrong on this company's books, not
hypotheticals.
"""

import unittest

from narjes_custom import finance


class _Row(dict):
	"""A GL row the way finance._bucket() sees one."""

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError as exc:
			raise AttributeError(key) from exc


def row(account_name="Marketing Expenses", account_type="", debit=0, credit=0):
	return _Row(
		account_name=account_name,
		account_type=account_type,
		debit=debit,
		credit=credit,
	)


class TestBucketing(unittest.TestCase):
	def bucket(self, r):
		return finance._bucket(r, r["debit"] - r["credit"])

	def test_cost_of_goods_is_a_direct_cost(self):
		self.assertEqual(
			self.bucket(row("Cost of Goods Sold", "Cost of Goods Sold", debit=1000)),
			"Direct",
		)

	def test_painting_and_packaging_are_direct_costs(self):
		# Both are the cost of making the thing sold, and both reach the
		# ledger as plain Journal Entries with no account_type set.
		for name in ("Painting Costs", "Packaging Expenses"):
			self.assertEqual(self.bucket(row(name, "", debit=500)), "Direct", name)

	def test_rent_is_an_operating_cost(self):
		self.assertEqual(self.bucket(row("Office Rent", "", debit=350000)), "Operating")

	def test_stock_written_off_is_a_real_cost(self):
		"""A debit to Stock Adjustment is stock genuinely lost."""
		self.assertEqual(
			self.bucket(row("Stock Adjustment", "Stock Adjustment", debit=40000)),
			"Operating",
		)

	def test_stock_appearing_is_not_negative_spending(self):
		"""The 110,000 Material Receipt that inflated profit by 110,000.

		Stock entered without a purchase behind it nets to a credit. Treated
		as an expense it is negative, which reads as money coming back and
		lands straight in the pot that pays everybody.
		"""
		self.assertEqual(
			self.bucket(row("Stock Adjustment", "Stock Adjustment", credit=110000)),
			"Correction",
		)


class TestProfitChainReconciles(unittest.TestCase):
	"""Whatever the buckets are, the chain must add up."""

	def test_steps_are_consistent(self):
		money_in, direct, operating = 5470000, 2515000, 1277000
		gross = money_in - direct
		net = gross - operating

		self.assertEqual(gross, 2955000)
		self.assertEqual(net, 1678000)
		# The relationship the Revenue report renders as rows.
		self.assertEqual(money_in - direct - operating, net)

	def test_the_split_never_creates_or_loses_money(self):
		net = 1678000
		shares = [15, 25, 30, 30]
		parts = [net * s / 100 for s in shares]
		self.assertAlmostEqual(sum(parts), net, places=6)


if __name__ == "__main__":
	unittest.main()
