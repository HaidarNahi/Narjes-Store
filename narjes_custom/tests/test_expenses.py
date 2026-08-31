"""
Unit tests for expense capture — pure Python, no live site. Run via:

    python -m pytest apps/narjes_custom/narjes_custom/tests/test_expenses.py -v

Two things are worth a safety net here, and both are about the AI layer being
wrong rather than the accounting being wrong (the accounting is a Journal
Entry, which ERPNext already guarantees):

* `sanitize` must drop an account name the model invented. A hallucinated
  account either fails the Link validation later — noisy but harmless — or
  matches something real and wrong, which is money filed under the wrong head
  and nobody noticing.
* `_safe_date` must refuse a stale date. The model has no clock: before the
  calendar block was added to the prompt, "yesterday" came back as a date two
  years old, which would post an expense into a closed accounting period.
"""

import unittest
from datetime import date, timedelta
from unittest import mock

from narjes_custom.expenses import api, extraction

ACCOUNTS = [{"name": "Marketing Expenses - NS"}, {"name": "Office Rent - NS"}]


class TestSanitize(unittest.TestCase):
	def test_keeps_a_real_account(self):
		got = extraction.sanitize(
			{"description": "ads", "amount": 131000, "expense_account": "Marketing Expenses - NS"},
			ACCOUNTS,
		)
		self.assertEqual(got["expense_account"], "Marketing Expenses - NS")

	def test_drops_an_invented_account(self):
		"""The field arrives empty so the human picks — the right outcome for
		'the model was not sure'."""
		got = extraction.sanitize(
			{"description": "ads", "amount": 1, "expense_account": "Meta Ads Account - NS"},
			ACCOUNTS,
		)
		self.assertEqual(got["expense_account"], "")

	def test_coerces_string_amount(self):
		self.assertEqual(extraction.sanitize({"amount": "131000"}, ACCOUNTS)["amount"], 131000.0)

	def test_unreadable_amount_becomes_zero(self):
		self.assertEqual(extraction.sanitize({"amount": "lots"}, ACCOUNTS)["amount"], 0.0)

	def test_negative_amount_becomes_zero(self):
		self.assertEqual(extraction.sanitize({"amount": -5}, ACCOUNTS)["amount"], 0.0)

	def test_none_and_whitespace_are_safe(self):
		got = extraction.sanitize(
			{"description": "  spaced  ", "payee": None, "notes": None, "amount": 5}, ACCOUNTS
		)
		self.assertEqual(got["description"], "spaced")
		self.assertEqual(got["payee"], "")
		self.assertEqual(got["notes"], "")

	def test_every_key_always_present(self):
		"""The form reads these unconditionally."""
		got = extraction.sanitize({}, ACCOUNTS)
		self.assertEqual(
			set(got),
			{"description", "payee", "amount", "expense_account", "expense_date", "notes"},
		)


class TestSafeDate(unittest.TestCase):
	TODAY = date(2026, 8, 17)

	def setUp(self):
		p = mock.patch.object(api, "nowdate", lambda: self.TODAY.isoformat())
		p.start()
		self.addCleanup(p.stop)
		# frappe's _() is a passthrough for these tests
		p2 = mock.patch.object(api, "_", lambda s: s)
		p2.start()
		self.addCleanup(p2.stop)

	def test_recent_date_kept(self):
		warnings = []
		got = api._safe_date("2026-08-16", warnings)
		self.assertEqual(got, "2026-08-16")
		self.assertEqual(warnings, [])

	def test_blank_becomes_today(self):
		warnings = []
		self.assertEqual(api._safe_date("", warnings), self.TODAY.isoformat())
		self.assertEqual(warnings, [])

	def test_future_date_refused(self):
		warnings = []
		self.assertEqual(api._safe_date("2026-09-01", warnings), self.TODAY.isoformat())
		self.assertEqual(len(warnings), 1)

	def test_stale_date_refused(self):
		"""The exact failure seen in testing: the model answered 2024-01-19
		for 'yesterday' because it was reading its own training cutoff."""
		warnings = []
		self.assertEqual(api._safe_date("2024-01-19", warnings), self.TODAY.isoformat())
		self.assertEqual(len(warnings), 1)

	def test_boundary_is_inclusive(self):
		edge = (self.TODAY - timedelta(days=api.MAX_BACKDATE_DAYS)).isoformat()
		self.assertEqual(api._safe_date(edge, []), edge)

	def test_just_past_boundary_refused(self):
		over = (self.TODAY - timedelta(days=api.MAX_BACKDATE_DAYS + 1)).isoformat()
		warnings = []
		self.assertEqual(api._safe_date(over, warnings), self.TODAY.isoformat())
		self.assertEqual(len(warnings), 1)

	def test_garbage_refused(self):
		warnings = []
		self.assertEqual(api._safe_date("not a date", warnings), self.TODAY.isoformat())
		self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
	unittest.main()
