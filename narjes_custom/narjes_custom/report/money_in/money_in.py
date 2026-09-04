# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

"""Money In — every dinar that arrived, one row per ledger posting.

The distinction this report exists to make is between *earned* and
*collected*. A cash-on-delivery shop mostly collects what it earns on the same
day, so the two figures usually agree — which is exactly why the day they
stop agreeing is worth seeing immediately, not at the end of the quarter.

Shares narjes_custom.finance with Money Out and Revenue.
"""

import frappe
from frappe import _

from narjes_custom import finance


def execute(filters=None):
	filters = frappe._dict(filters or {})
	company = filters.company or finance.default_company()
	rows = finance.money_in_rows(filters.from_date, filters.to_date, company)

	if filters.customer:
		rows = [r for r in rows if r.party == filters.customer]

	# One batched lookup for the customer behind each voucher, instead of a
	# query per row. On a busy month this is the difference between one round
	# trip and several hundred.
	customers = _customers_for(rows)

	data = [
		{
			"posting_date": r.posting_date,
			"customer": r.party or customers.get(r.voucher_no) or "",
			"description": _describe(r),
			"source": r.account_name,
			"voucher_type": r.voucher_type,
			"voucher_no": r.voucher_no,
			"amount": r["amount"],
		}
		for r in rows
	]

	return (
		get_columns(),
		data,
		None,
		_chart(rows),
		_summary(rows, filters, company),
	)


def _customers_for(rows):
	"""voucher_no -> customer, for the voucher types that carry one."""
	by_type = {}
	for r in rows:
		if r.voucher_type in ("Sales Invoice", "Delivery Note", "Sales Order"):
			by_type.setdefault(r.voucher_type, set()).add(r.voucher_no)

	found = {}
	for doctype, names in by_type.items():
		for row in frappe.get_all(
			doctype,
			filters={"name": ["in", list(names)]},
			fields=["name", "customer"],
		):
			found[row.name] = row.customer
	return found


def _describe(row):
	remark = (row.remarks or "").strip()
	if remark and remark != "Accounting Entry for Stock":
		return remark[:180]
	return row.account_name


def _summary(rows, filters, company):
	total = sum(r["amount"] for r in rows)
	collected = finance.cash_collected(filters.from_date, filters.to_date, company)
	orders = len({r.voucher_no for r in rows})

	cards = [
		{
			"label": _("Total in"),
			"value": total,
			"indicator": "Green",
			"datatype": "Currency",
		},
		{
			"label": _("Cash received"),
			"value": collected,
			"indicator": "Green",
			"datatype": "Currency",
		},
		{
			"label": _("Still owed"),
			# Earned but not yet in the till. Floored at zero: collecting last
			# month's invoice this month makes this genuinely negative, and
			# "still owed: -40,000" reads as a bug rather than as good news.
			"value": max(total - collected, 0),
			"indicator": "Orange",
			"datatype": "Currency",
		},
		{
			"label": _("Average sale"),
			"value": (total / orders) if orders else 0,
			"datatype": "Currency",
		},
	]
	return cards


def _chart(rows):
	"""Daily takings — the shape of the month at a glance."""
	by_day = {}
	for r in rows:
		key = str(r.posting_date)
		by_day[key] = by_day.get(key, 0) + r["amount"]
	if not by_day:
		return None

	days = sorted(by_day)
	return {
		"data": {
			"labels": days,
			"datasets": [{"name": _("Taken"), "values": [round(by_day[d]) for d in days]}],
		},
		"type": "line",
		"colors": ["#2E5C46"],
		"fieldtype": "Currency",
		"lineOptions": {"regionFill": 1, "hideDots": 1 if len(days) > 45 else 0},
	}


def get_columns():
	return [
		{"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{
			"fieldname": "customer",
			"label": _("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"width": 175,
		},
		{"fieldname": "description", "label": _("For"), "fieldtype": "Data", "width": 260},
		{"fieldname": "source", "label": _("Source"), "fieldtype": "Data", "width": 130},
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
