"""
Unit tests for intake warehouse resolution — pure Python, no live site. Run via:

    python -m pytest apps/narjes_custom/narjes_custom/tests/test_warehouse_defaults.py -v

The bug these lock in: `_get_default_so_items_params` fell back to
`frappe.get_all("Warehouse", ..., limit=1)` with no `order_by`, so Frappe
applied its default of `modified desc`. Two consequences, both of which the
shop hit:

* Nothing excluded **Transit** warehouses, so orders were assigned to "Goods
  In Transit" — a staging area that never holds sellable stock — and failed at
  submit with "Insufficient Stock" regardless of real inventory.
* The choice was **unstable**. Editing any warehouse re-ordered the result, so
  moving stock to satisfy the error moved the target. That is why the system
  appeared to change its mind between attempts.
"""

import unittest
from unittest import mock

from narjes_custom.ai_intake import api

# name -> (is_group, disabled, warehouse_type)
WAREHOUSES = {
	"All Warehouses - NS": (1, 0, None),
	"Finished Goods - NS": (0, 0, None),
	"Goods In Transit - NS": (0, 0, "Transit"),
	"Stores - NS": (0, 0, None),
	"Work In Progress - NS": (0, 0, None),
	"Old Shop - NS": (0, 1, None),
}


def _fake_get_all(doctype, filters=None, pluck=None, order_by=None, limit=None):
	"""Mimics the real query, including that `!=` is NULL-safe in Frappe."""
	names = [
		n
		for n, (is_group, disabled, wtype) in WAREHOUSES.items()
		if not is_group and not disabled and (wtype or "") != "Transit"
	]
	if order_by and order_by.startswith("name asc"):
		names.sort()
	return names[:limit] if limit else names


class _FakeDB:
	"""Stands in for `frappe.db`, which is a thread-local proxy that raises
	outside a site connection — so it has to be replaced wholesale, not
	patched attribute by attribute."""

	def __init__(self, single_value=None):
		self.single_value = single_value

	def get_value(self, doctype, name, fields, as_dict=False):
		row = WAREHOUSES.get(name)
		if not row:
			return None
		return mock.Mock(is_group=row[0], disabled=row[1], warehouse_type=row[2])

	def get_single_value(self, *a, **k):
		return self.single_value


class _Base(unittest.TestCase):
	def setUp(self):
		patches = [
			mock.patch.object(api.frappe, "db", _FakeDB()),
			mock.patch.object(api.frappe, "get_all", _fake_get_all),
			mock.patch.object(api.ai_settings, "get_str", lambda *a, **k: "Nos"),
		]
		for p in patches:
			p.start()
			self.addCleanup(p.stop)

	def _resolve(self, ai_setting=None, stock_setting=None):
		# stock_setting is ERPNext's own default (Company in v16, Stock
		# Settings before), as _erpnext_default_warehouse returns it.
		with mock.patch.object(api, "_erpnext_default_warehouse", lambda: stock_setting):
			with mock.patch.object(api.ai_settings, "get_setting", lambda *a, **k: ai_setting):
				return api._get_default_so_items_params()[0]


class TestUsableWarehouse(_Base):
	def test_rejects_transit(self):
		self.assertFalse(api._usable_warehouse("Goods In Transit - NS"))

	def test_rejects_group_and_disabled(self):
		self.assertFalse(api._usable_warehouse("All Warehouses - NS"))
		self.assertFalse(api._usable_warehouse("Old Shop - NS"))

	def test_accepts_ordinary_warehouse(self):
		self.assertTrue(api._usable_warehouse("Stores - NS"))

	def test_rejects_missing_and_blank(self):
		self.assertFalse(api._usable_warehouse("Nope - NS"))
		self.assertFalse(api._usable_warehouse(None))
		self.assertFalse(api._usable_warehouse(""))


class TestResolutionOrder(_Base):
	def test_explicit_setting_wins(self):
		self.assertEqual(self._resolve(ai_setting="Work In Progress - NS"), "Work In Progress - NS")

	def test_falls_back_to_stock_settings(self):
		self.assertEqual(self._resolve(stock_setting="Stores - NS"), "Stores - NS")

	def test_transit_ai_setting_is_refused(self):
		"""Even an explicit setting cannot select a transit warehouse."""
		self.assertEqual(
			self._resolve(ai_setting="Goods In Transit - NS", stock_setting="Stores - NS"),
			"Stores - NS",
		)

	def test_transit_stock_setting_is_refused(self):
		self.assertEqual(self._resolve(stock_setting="Goods In Transit - NS"), "Finished Goods - NS")

	def test_last_resort_never_transit(self):
		self.assertEqual(self._resolve(), "Finished Goods - NS")

	def test_last_resort_is_deterministic(self):
		"""Ordered by name, so it cannot drift when a warehouse is edited."""
		self.assertEqual({self._resolve() for _ in range(5)}, {"Finished Goods - NS"})


class _Meta:
	def __init__(self, fields):
		self.fields = fields

	def has_field(self, name):
		return name in self.fields


class TestErpnextDefault(unittest.TestCase):
	"""ERPNext v16 dropped Stock Settings.default_warehouse; reading it threw
	"Field default_warehouse does not exist on Stock Settings" on confirm."""

	def _run(self, metas, company_wh=None, stock_wh=None):
		db = mock.Mock()
		db.get_single_value.side_effect = lambda doctype, field: {
			("Global Defaults", "default_company"): "Narjes Store",
			("Stock Settings", "default_warehouse"): stock_wh,
		}[(doctype, field)]
		with mock.patch.object(api.frappe, "db", db), \
			mock.patch.object(api.frappe, "defaults", mock.Mock(get_user_default=lambda k: None)), \
			mock.patch.object(api.frappe, "get_meta", lambda dt: _Meta(metas.get(dt, ()))), \
			mock.patch.object(api.frappe, "get_cached_value", lambda *a: company_wh):
			return api._erpnext_default_warehouse(), db

	def test_v16_reads_company_and_never_stock_settings(self):
		wh, db = self._run({"Company": ("default_warehouse",)}, company_wh="Stores - NS")
		self.assertEqual(wh, "Stores - NS")
		self.assertNotIn(("Stock Settings", "default_warehouse"), [c.args for c in db.get_single_value.call_args_list])

	def test_v16_without_company_default_is_none(self):
		wh, db = self._run({"Company": ("default_warehouse",)})
		self.assertIsNone(wh)
		self.assertNotIn(("Stock Settings", "default_warehouse"), [c.args for c in db.get_single_value.call_args_list])

	def test_older_erpnext_still_reads_stock_settings(self):
		wh, _db = self._run({"Stock Settings": ("default_warehouse",)}, stock_wh="Stores - NS")
		self.assertEqual(wh, "Stores - NS")


if __name__ == "__main__":
	unittest.main()
