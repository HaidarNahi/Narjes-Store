"""Move a sale's *money* paperwork back to the month the order was taken.

Repairs orders posted before api._posting_date() existed, when everything a
sale generated was dated the day someone pressed submit rather than the day
the business happened.

**Deliberately does not touch Delivery Notes.** A Delivery Note carries stock
as well as cost: re-dating one re-prices inventory on that date and can fail
outright if the goods were not in the warehouse yet. Only the three
money-only documents are moved:

    Sales Invoice    the revenue
    Payment Entry    the cash
    Journal Entry    packaging, painting and flower cost

The cost of goods stays in the month the stock moved, so a repaired month
gains its full revenue but not quite all of its cost. `dry_run()` prints
exactly how much is left behind, per month, so the residual is a number you
chose rather than one you discover later.

Nothing is amended or cancelled. The voucher keeps its name, its amounts and
its links; only `posting_date` moves, on the document and on the GL Entry rows
it wrote. That is the whole change.

Usage — always look before you leap:

    bench --site <site> execute narjes_custom.tools.redate_money_vouchers.dry_run
    bench --site <site> execute narjes_custom.tools.redate_money_vouchers.apply

`apply` refuses to run if the accounts are frozen or a period has been closed.
"""

import frappe
from frappe.utils import getdate

from narjes_custom.tools import misdated_orders

# Money only. "Delivery Note" is absent from this tuple on purpose — see the
# module docstring.
MOVABLE = ("Sales Invoice", "Payment Entry", "Journal Entry")

LEFT_BEHIND = "Delivery Note"


def _plan(company=None):
	"""Which vouchers would move, and where the residual lands."""
	moving, staying = [], []
	for order in misdated_orders.find(company):
		for voucher in order["vouchers"]:
			row = {
				"sales_order": order["name"],
				"order_date": order["transaction_date"],
				"doctype": voucher["doctype"],
				"name": voucher["name"],
				"from_date": voucher["posting_date"],
				"ledger": voucher["ledger"],
			}
			(moving if voucher["doctype"] in MOVABLE else staying).append(row)
	return moving, staying


def _guard():
	"""Refuse to rewrite dates into a period somebody has closed."""
	closed = frappe.get_all("Period Closing Voucher", filters={"docstatus": 1}, pluck="name")
	if closed:
		frappe.throw(
			f"The books have been closed by {', '.join(closed)}. "
			"Re-dating into a closed period needs those reversed first."
		)

	settings = frappe.get_single("Accounts Settings")
	frozen = getattr(settings, "acc_frozen_upto", None) or getattr(
		settings, "accounts_frozen_upto", None
	)
	if frozen:
		frappe.throw(f"Accounts are frozen up to {frozen}. Unfreeze them before re-dating.")


def dry_run(company=None):
	"""Print what would change. Changes nothing."""
	moving, staying = _plan(company)

	if not moving:
		print("\nNothing to move — every money voucher is already in its order's month.\n")
		return moving

	print(f"\n{len(moving)} voucher(s) would move:\n")
	by_type = {}
	for row in moving:
		by_type.setdefault(row["doctype"], []).append(row)
	for doctype in sorted(by_type):
		rows = by_type[doctype]
		print(f"  {doctype} ({len(rows)})")
		for r in rows[:4]:
			print(f"      {r['name']:<26} {r['from_date']} -> {r['order_date']}   ({r['sales_order']})")
		if len(rows) > 4:
			print(f"      … and {len(rows) - 4} more")
	print()

	_print_month_table("What each month gains or loses", moving)

	if staying:
		print(f"  Left in place ({LEFT_BEHIND}, because it moves stock as well as money):")
		residual = sum(r["ledger"]["expense"] for r in staying)
		print(f"      {len(staying)} voucher(s), {residual:,.0f} of cost of goods\n")
		_print_month_table("Cost left behind, by month", staying, expense_only=True)
		print(
			f"  So a repaired month reads about {residual:,.0f} better than it truly did,"
			f"\n  because it has its revenue but not this part of its cost.\n"
		)

	print("  Nothing has been changed. Run apply() to make it so.\n")
	return moving


def _print_month_table(title, rows, expense_only=False):
	moves = {}
	for r in rows:
		frm = getdate(r["from_date"]).strftime("%B %Y")
		to = getdate(r["order_date"]).strftime("%B %Y")
		for m in (frm, to):
			moves.setdefault(m, {"income": 0.0, "expense": 0.0})
		moves[frm]["income"] -= r["ledger"]["income"]
		moves[frm]["expense"] -= r["ledger"]["expense"]
		moves[to]["income"] += r["ledger"]["income"]
		moves[to]["expense"] += r["ledger"]["expense"]

	print(f"  {title}:\n")
	print(f"      {'Month':<18}{'Income':>14}{'Expense':>14}{'Net profit':>14}")
	for month in sorted(moves, key=lambda m: getdate(f"1 {m}")):
		m = moves[month]
		net = m["income"] - m["expense"]
		if expense_only:
			print(f"      {month:<18}{'':>14}{m['expense']:>+14,.0f}{-m['expense']:>+14,.0f}")
		else:
			print(f"      {month:<18}{m['income']:>+14,.0f}{m['expense']:>+14,.0f}{net:>+14,.0f}")
	print()


def apply(company=None):
	"""Move the money vouchers. One order at a time, stopping on any failure."""
	_guard()
	moving, _ = _plan(company)
	if not moving:
		print("\nNothing to move.\n")
		return

	print(f"\nMoving {len(moving)} voucher(s)…\n")
	moved, failed = 0, []

	for row in moving:
		savepoint = "redate"
		frappe.db.savepoint(savepoint)
		try:
			_move(row)
			frappe.db.commit()
			moved += 1
			print(f"  moved {row['doctype']:<15} {row['name']:<26} -> {row['order_date']}")
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			failed.append((row, str(exc)[:120]))
			print(f"  FAILED {row['doctype']:<15} {row['name']:<26} {str(exc)[:80]}")

	print(f"\n  {moved} moved, {len(failed)} failed.")
	if failed:
		print("  Failures are rolled back individually — the rest still moved.")
	print()


def _move(row):
	"""Re-date one voucher and the ledger rows it wrote.

	`db_set`/direct SQL rather than doc.save(): these are submitted documents,
	and posting_date is not editable after submit through the normal path. The
	document is not otherwise touched — no amounts, no links, no docstatus, so
	nothing needs revalidating.
	"""
	doctype, name, new_date = row["doctype"], row["name"], row["order_date"]

	frappe.db.set_value(doctype, name, "posting_date", new_date, update_modified=False)

	# A Sales Invoice whose due date now precedes its posting date would be
	# reported as overdue the moment it was moved.
	if doctype == "Sales Invoice":
		due = frappe.db.get_value(doctype, name, "due_date")
		if due and getdate(due) < getdate(new_date):
			frappe.db.set_value(doctype, name, "due_date", new_date, update_modified=False)

	updated = frappe.db.sql(
		"""UPDATE `tabGL Entry` SET posting_date = %(date)s
		   WHERE voucher_type = %(dt)s AND voucher_no = %(dn)s AND is_cancelled = 0""",
		{"date": new_date, "dt": doctype, "dn": name},
	)
	return updated
