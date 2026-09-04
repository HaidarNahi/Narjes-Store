# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

"""Money Out — every dinar that left the company, one row per ledger posting.

Reads the ledger rather than the Narjes Expense list, because a good deal of
what the shop spends never passes through that list: `automate_so_flow()`
books painting, packaging and flower cost straight to Journal Entries when an
order is submitted. A document-level report would show the rent and the ads
and quietly omit the cost of everything actually sold.

The arithmetic lives in narjes_custom.finance so this report, Money In and
Revenue cannot drift apart.
"""

import frappe
from frappe import _

from narjes_custom import finance
from narjes_custom.reports_meta import card


def execute(filters=None):
	filters = frappe._dict(filters or {})
	company = filters.company or finance.default_company()
	rows = finance.money_out_rows(filters.from_date, filters.to_date, company)

	if filters.bucket:
		rows = [r for r in rows if r["bucket"] == filters.bucket]

	data = [
		{
			"posting_date": r.posting_date,
			"description": _describe(r),
			"category": r.account_name,
			"bucket": r["bucket"],
			"voucher_type": r.voucher_type,
			"voucher_no": r.voucher_no,
			"amount": r["amount"],
		}
		for r in rows
	]

	return get_columns(), data, None, _chart(rows), _summary(rows)


def _describe(row):
	"""The most human sentence available for a posting.

	`remarks` is what a person wrote (or what the automation wrote on their
	behalf); it beats an account name every time. ERPNext fills it with a
	generic "Accounting Entry for Stock" on stock vouchers, which tells the
	reader nothing they cannot see in the other columns.
	"""
	remark = (row.remarks or "").strip()
	if remark and remark != "Accounting Entry for Stock":
		return remark[:180]
	if row.party:
		return _("{0} — {1}").format(row.account_name, row.party)
	return row.account_name


def _summary(rows):
	"""The cards above the table."""
	direct = sum(r["amount"] for r in rows if r["bucket"] == "Direct")
	operating = sum(r["amount"] for r in rows if r["bucket"] == "Operating")
	correction = sum(r["amount"] for r in rows if r["bucket"] == "Correction")

	cards = [
		card("Total out", direct + operating, indicator="Red", datatype="Currency"),
		card("Cost of goods", direct, indicator="Orange", datatype="Currency"),
		card("Running the shop", operating, indicator="Blue", datatype="Currency"),
		card("Entries", len(rows), datatype="Int"),
	]
	if correction:
		# Never folded into the total — see finance.STOCK_CORRECTION_ACCOUNT_TYPE.
		cards.append(
			card("Stock corrections (not spending)", correction, indicator="Grey", datatype="Currency")
		)
	return cards


def _chart(rows):
	"""Where the money went, biggest head first — the six that matter."""
	totals = {}
	for r in rows:
		if r["bucket"] == "Correction":
			continue
		totals[r.account_name] = totals.get(r.account_name, 0) + r["amount"]

	top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
	if not top:
		return None

	return {
		"data": {
			"labels": [name for name, _v in top],
			"datasets": [{"name": _("Spent"), "values": [round(v) for _n, v in top]}],
		},
		"type": "bar",
		"colors": ["#9B3B3B"],
		"fieldtype": "Currency",
	}


def get_columns():
	return [
		{"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "description", "label": _("What for"), "fieldtype": "Data", "width": 300},
		{
			"fieldname": "category",
			"label": _("Category"),
			"fieldtype": "Data",
			"width": 170,
		},
		{"fieldname": "bucket", "label": _("Kind"), "fieldtype": "Data", "width": 100},
		{
			"fieldname": "voucher_no",
			"label": _("Document"),
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 175,
		},
		{
			"fieldname": "voucher_type",
			"label": _("Document Type"),
			"fieldtype": "Data",
			"width": 130,
			"hidden": 1,
		},
		{"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency", "width": 130},
	]
