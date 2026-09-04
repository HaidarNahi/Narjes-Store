"""Report orders whose paperwork was posted in a different month than the sale.

Read-only. Nothing here changes a document, a date, or a ledger entry.

`automate_so_flow` used to date everything it generated "today" — the day
someone pressed submit — rather than the day the order was taken. An order
taken on 31 August and submitted on 1 September put its revenue, its cost of
goods and its payment into September, while the order and the piece commission
earned on it stayed in August. That is fixed for new orders (see
api._posting_date), but it does not move anything already posted.

This tells you what is already posted that way, and what moving it would do to
each month.

Run:  bench --site <site> execute narjes_custom.tools.misdated_orders.report
"""

import frappe
from frappe.utils import flt, getdate


def find(company=None, from_date=None, to_date=None):
	"""Submitted orders with at least one voucher posted in another month."""
	company = company or frappe.db.get_value("Company", {}, "name")

	orders = frappe.db.sql(
		"""
		SELECT DISTINCT so.name, so.transaction_date, so.customer, so.grand_total
		FROM `tabSales Order` so
		WHERE so.docstatus = 1
		  AND so.company = %(company)s
		  AND (%(from_date)s IS NULL OR so.transaction_date >= %(from_date)s)
		  AND (%(to_date)s IS NULL OR so.transaction_date <= %(to_date)s)
		ORDER BY so.transaction_date
		""",
		{"company": company, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	affected = []
	for order in orders:
		vouchers = _vouchers_for(order.name)
		wrong = [
			v
			for v in vouchers
			if _month(v["posting_date"]) != _month(order.transaction_date)
		]
		if wrong:
			affected.append({**order, "vouchers": wrong})
	return affected


def _vouchers_for(order_name):
	"""Every ledger-bearing document the automation created for an order."""
	rows = []

	for parent in frappe.db.sql(
		"""SELECT DISTINCT si.name, si.posting_date FROM `tabSales Invoice` si
		   INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		   WHERE sii.sales_order = %s AND si.docstatus = 1""",
		order_name,
		as_dict=True,
	):
		rows.append({"doctype": "Sales Invoice", "name": parent.name, "posting_date": parent.posting_date})

	for parent in frappe.db.sql(
		"""SELECT DISTINCT dn.name, dn.posting_date FROM `tabDelivery Note` dn
		   INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		   WHERE dni.against_sales_order = %s AND dn.docstatus = 1""",
		order_name,
		as_dict=True,
	):
		rows.append({"doctype": "Delivery Note", "name": parent.name, "posting_date": parent.posting_date})

	for pe in frappe.get_all(
		"Payment Entry",
		filters={"reference_no": f"AUTO-{order_name}", "docstatus": 1},
		fields=["name", "posting_date"],
	):
		rows.append({"doctype": "Payment Entry", "name": pe.name, "posting_date": pe.posting_date})

	for je in frappe.get_all(
		"Journal Entry",
		filters={"custom_sales_order": order_name, "docstatus": 1},
		fields=["name", "posting_date"],
	):
		rows.append({"doctype": "Journal Entry", "name": je.name, "posting_date": je.posting_date})

	for row in rows:
		row["ledger"] = _ledger_effect(row["doctype"], row["name"])
	return rows


def _ledger_effect(doctype, name):
	"""What this voucher put on the profit and loss, by root type."""
	rows = frappe.db.sql(
		"""
		SELECT acc.root_type, SUM(gl.debit) AS dr, SUM(gl.credit) AS cr
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` acc ON acc.name = gl.account
		WHERE gl.voucher_type = %s AND gl.voucher_no = %s
		  AND gl.is_cancelled = 0 AND acc.root_type IN ('Income', 'Expense')
		GROUP BY acc.root_type
		""",
		(doctype, name),
		as_dict=True,
	)
	effect = {"income": 0.0, "expense": 0.0}
	for r in rows:
		if r.root_type == "Income":
			effect["income"] += flt(r.cr) - flt(r.dr)
		else:
			effect["expense"] += flt(r.dr) - flt(r.cr)
	return effect


def _month(date):
	d = getdate(date)
	return (d.year, d.month)


def _month_name(date):
	return getdate(date).strftime("%B %Y")


def report(company=None, from_date=None, to_date=None):
	"""Print what is misdated and what correcting it would move."""
	affected = find(company, from_date, to_date)

	if not affected:
		print("\nEvery submitted order has its paperwork posted in the month it was taken.\n")
		return affected

	print(f"\n{len(affected)} order(s) have paperwork posted in a different month.\n")

	moves = {}
	for order in affected:
		print(f"  {order['name']}  ordered {order['transaction_date']} ({_month_name(order['transaction_date'])})")
		for v in order["vouchers"]:
			effect = v["ledger"]
			bits = []
			if effect["income"]:
				bits.append(f"income {effect['income']:+,.0f}")
			if effect["expense"]:
				bits.append(f"expense {effect['expense']:+,.0f}")
			detail = ", ".join(bits) or "no P&L effect"
			print(
				f"      {v['doctype']:<15} {v['name']:<26} posted {v['posting_date']} "
				f"({_month_name(v['posting_date'])})  [{detail}]"
			)

			# Correcting this voucher would take its effect out of the month
			# it sits in and put it into the month the order belongs to.
			frm = _month_name(v["posting_date"])
			to = _month_name(order["transaction_date"])
			moves.setdefault(frm, {"income": 0.0, "expense": 0.0})
			moves.setdefault(to, {"income": 0.0, "expense": 0.0})
			moves[frm]["income"] -= effect["income"]
			moves[frm]["expense"] -= effect["expense"]
			moves[to]["income"] += effect["income"]
			moves[to]["expense"] += effect["expense"]
		print()

	print("  If every one of these were re-dated to its order, each month would change by:\n")
	print(f"      {'Month':<18}{'Income':>14}{'Expense':>14}{'Net profit':>14}")
	for month in sorted(moves, key=lambda m: getdate(f"1 {m}")):
		m = moves[month]
		net = m["income"] - m["expense"]
		print(f"      {month:<18}{m['income']:>+14,.0f}{m['expense']:>+14,.0f}{net:>+14,.0f}")

	print(
		"\n  Nothing has been changed. Delivery Notes carry stock as well as cost,"
		"\n  so re-dating one means repricing stock on that date too — decide that"
		"\n  deliberately rather than as a side effect of a report.\n"
	)
	return affected
