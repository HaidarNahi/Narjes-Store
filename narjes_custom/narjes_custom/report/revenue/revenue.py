# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

"""Revenue — the chain from what customers paid down to what the shop keeps.

The bottom line here is the number the Revenue & Salaries dashboard divides
between four people, so this report is deliberately not a single figure. Each
step is a row, each row names the accounts behind it, and the steps reconcile
by construction: gross is money in less direct cost, net is gross less the
cost of running the shop.

That structure exists because of what a naive version produced on this
company's own books. Summing the profit-and-loss accounts by root type gave a
net profit of 139,300 when the true figure was 29,300 — packaging was filed
under Income while being debited as a cost, and an opening stock receipt read
as 110,000 of negative spending. Both are fixed at the source now (see
setup/accounts.py and finance.STOCK_CORRECTION_ACCOUNT_TYPE), but a report
that pays salaries should show its working regardless.
"""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff

from narjes_custom import finance

# An em space (U+2003), written as an escape because an invisible
# character in source is a trap for whoever edits this next.
INDENT_STEP = "\u2003"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	company = filters.company or finance.default_company()
	current = finance.profit_summary(filters.from_date, filters.to_date, company)
	previous = _previous_period(filters, company) if filters.compare else None

	return (
		get_columns(bool(previous)),
		_rows(current, previous),
		_message(current),
		_chart(current),
		_summary(current, previous),
	)


def _previous_period(filters, company):
	"""The immediately preceding window of the same length.

	Same length rather than "last calendar month" so that comparing a 10-day
	range compares it against 10 days, not against 31.
	"""
	span = date_diff(filters.to_date, filters.from_date)
	prev_to = add_days(filters.from_date, -1)
	prev_from = add_days(prev_to, -span)
	return finance.profit_summary(prev_from, prev_to, company)


def _rows(cur, prev):
	rows = []

	def line(label, value, kind="detail", prev_value=None, note=""):
		row = {"step": label, "amount": value, "kind": kind, "note": note}
		if prev is not None:
			row["previous"] = prev_value or 0
			row["change"] = (value - (prev_value or 0)) if value is not None else 0
		rows.append(row)

	# ---- what came in
	line(_("Money in"), cur["money_in"], "total", prev and prev["money_in"])
	for account, amount in cur["by_income_account"].items():
		line(INDENT_STEP + account, amount, "detail", (prev or {}).get("by_income_account", {}).get(account))

	# ---- cost of the things sold
	line(_("Cost of goods sold"), -cur["direct_cost"], "subtract", prev and -prev["direct_cost"])
	for account, amount in cur["by_expense_account"].items():
		if _is_direct(account, cur):
			line(
				INDENT_STEP + account,
				-amount,
				"detail",
				-(prev or {}).get("by_expense_account", {}).get(account, 0) if prev else None,
			)

	line(
		_("Gross profit"),
		cur["gross_profit"],
		"total",
		prev and prev["gross_profit"],
		note=_("{0}% margin").format(round(cur["gross_margin"], 1)),
	)

	# ---- cost of keeping the doors open
	line(_("Cost of running the shop"), -cur["operating_cost"], "subtract", prev and -prev["operating_cost"])
	for account, amount in cur["by_expense_account"].items():
		if not _is_direct(account, cur):
			line(
				INDENT_STEP + account,
				-amount,
				"detail",
				-(prev or {}).get("by_expense_account", {}).get(account, 0) if prev else None,
			)

	line(
		_("Net profit"),
		cur["net_profit"],
		"net",
		prev and prev["net_profit"],
		note=_("{0}% margin — this is what the salary dashboard divides").format(
			round(cur["net_margin"], 1)
		),
	)

	if cur["stock_correction"]:
		line(
			_("Stock corrections (not counted above)"),
			cur["stock_correction"],
			"correction",
			None,
			note=_("Stock entered without a purchase behind it — no money moved"),
		)

	return rows


def _is_direct(account_name, summary):
	return (
		account_name in finance.DIRECT_COST_NAMES
		or account_name in ("Cost of Goods Sold",)
	)


def _summary(cur, prev):
	cards = [
		{"label": _("Money in"), "value": cur["money_in"], "indicator": "Green", "datatype": "Currency"},
		{
			"label": _("Cost of goods"),
			"value": cur["direct_cost"],
			"indicator": "Orange",
			"datatype": "Currency",
		},
		{
			"label": _("Gross profit"),
			"value": cur["gross_profit"],
			"indicator": "Blue",
			"datatype": "Currency",
		},
		{
			"label": _("Running costs"),
			"value": cur["operating_cost"],
			"indicator": "Orange",
			"datatype": "Currency",
		},
		{
			"label": _("Net profit"),
			"value": cur["net_profit"],
			"indicator": "Green" if cur["net_profit"] >= 0 else "Red",
			"datatype": "Currency",
		},
	]
	if prev:
		delta = cur["net_profit"] - prev["net_profit"]
		pct = (delta / abs(prev["net_profit"]) * 100) if prev["net_profit"] else 0
		cards.append(
			{
				"label": _("vs previous period"),
				"value": pct,
				"indicator": "Green" if delta >= 0 else "Red",
				"datatype": "Percent",
			}
		)
	return cards


def _chart(cur):
	return {
		"data": {
			"labels": [_("Money in"), _("Cost of goods"), _("Running costs"), _("Net profit")],
			"datasets": [
				{
					"name": _("This period"),
					"values": [
						round(cur["money_in"]),
						round(-cur["direct_cost"]),
						round(-cur["operating_cost"]),
						round(cur["net_profit"]),
					],
				}
			],
		},
		"type": "bar",
		"colors": ["#C8842A"],
		"fieldtype": "Currency",
	}


def _message(cur):
	if cur["money_in"] or cur["money_out"]:
		return None
	return _(
		"Nothing was posted to the ledger in this period. "
		"Try widening the dates, or check that orders have been submitted."
	)


def get_columns(comparing):
	columns = [
		{"fieldname": "step", "label": _("Step"), "fieldtype": "Data", "width": 300},
		{"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency", "width": 150},
	]
	if comparing:
		columns += [
			{
				"fieldname": "previous",
				"label": _("Previous"),
				"fieldtype": "Currency",
				"width": 140,
			},
			{"fieldname": "change", "label": _("Change"), "fieldtype": "Currency", "width": 130},
		]
	columns += [
		{"fieldname": "note", "label": _("Note"), "fieldtype": "Data", "width": 340},
		{"fieldname": "kind", "label": _("Kind"), "fieldtype": "Data", "width": 90, "hidden": 1},
	]
	return columns
