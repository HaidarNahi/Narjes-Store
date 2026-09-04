"""Data for the Debts dashboard.

One endpoint, one round trip. The dashboard is a page the shop opens to
answer "who owes me, and what have I not paid" — if that takes three requests
and a spinner per card, they will stop opening it.
"""

import frappe
from frappe.utils import flt, getdate, today

OWED_TO_US = "They owe us"
WE_OWE = "We owe them"


@frappe.whitelist()
def get_dashboard(status=None, direction=None):
	"""Everything the Debts page draws, in a single query plus a rollup."""
	frappe.has_permission("Narjes Debt", ptype="read", throw=True)

	filters = {}
	if status:
		filters["status"] = status
	if direction:
		filters["direction"] = direction

	debts = frappe.get_all(
		"Narjes Debt",
		filters=filters,
		fields=[
			"name", "display_name", "direction", "party_type", "party",
			"amount", "paid_amount", "outstanding", "status",
			"debt_date", "due_date", "description", "phone",
		],
		order_by="due_date asc",
		limit_page_length=0,
	)

	# Ordered in Python rather than SQL: the useful order is "what needs
	# attention first", which is a fixed status ranking, and Frappe's query
	# builder rejects the FIELD() call that would express it in SQL.
	rank = {"Overdue": 0, "Partly settled": 1, "Open": 2, "Settled": 3}
	debts.sort(key=lambda d: (rank.get(d.status, 9), d.due_date or getdate("2999-12-31")))

	# Instalment counts for every debt in one query rather than one per row.
	plans = _settlement_counts([d.name for d in debts])
	now = getdate(today())
	for debt in debts:
		plan = plans.get(debt.name, {})
		debt["instalments"] = plan.get("total", 0)
		debt["instalments_paid"] = plan.get("paid", 0)
		debt["days_overdue"] = (
			(now - getdate(debt.due_date)).days
			if debt.due_date and debt.status == "Overdue"
			else 0
		)

	from narjes_custom.reports_meta import explain

	return {
		"debts": debts,
		"summary": _summary(debts),
		"explainers": {
			"owed_to_us": explain("Owed to us"),
			"we_owe": explain("We owe"),
			"net_position": explain("Net position"),
			"overdue": explain("Overdue"),
		},
	}


def _settlement_counts(names):
	if not names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT parent,
		       COUNT(*) AS total,
		       SUM(CASE WHEN paid_on IS NOT NULL THEN 1 ELSE 0 END) AS paid
		FROM `tabNarjes Debt Settlement`
		WHERE parent IN %(names)s AND parenttype = 'Narjes Debt'
		GROUP BY parent
		""",
		{"names": names},
		as_dict=True,
	)
	return {r.parent: {"total": r.total, "paid": int(r.paid or 0)} for r in rows}


def _summary(debts):
	"""Only what is still owed counts — a settled debt is history."""
	open_debts = [d for d in debts if d.status != "Settled"]
	owed_to_us = sum(flt(d.outstanding) for d in open_debts if d.direction == OWED_TO_US)
	we_owe = sum(flt(d.outstanding) for d in open_debts if d.direction == WE_OWE)
	overdue = [d for d in open_debts if d.status == "Overdue"]

	return {
		"owed_to_us": owed_to_us,
		"owed_to_us_count": len([d for d in open_debts if d.direction == OWED_TO_US]),
		"we_owe": we_owe,
		"we_owe_count": len([d for d in open_debts if d.direction == WE_OWE]),
		"net_position": owed_to_us - we_owe,
		"overdue_total": sum(flt(d.outstanding) for d in overdue),
		"overdue_count": len(overdue),
		"worst_overdue_days": max((d.days_overdue for d in overdue), default=0),
		"settled_count": len([d for d in debts if d.status == "Settled"]),
	}


@frappe.whitelist()
def get_settlements(debt):
	"""The instalment plan for one debt, for the expanded row."""
	frappe.has_permission("Narjes Debt", doc=debt, throw=True)
	return frappe.get_all(
		"Narjes Debt Settlement",
		filters={"parent": debt, "parenttype": "Narjes Debt"},
		fields=["idx", "due_date", "paid_on", "amount", "mode_of_payment", "notes"],
		order_by="idx asc",
	)
