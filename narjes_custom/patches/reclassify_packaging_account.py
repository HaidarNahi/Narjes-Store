"""Move `Packaging Expenses` from Income to Expense, and say what moved.

The account was created under Direct Income as an "Income Account", but
`automate_so_flow()` has always debited it as a cost. Debiting an income
account does not corrupt the bottom line — a debit reduces income by the
same amount an expense would — but it does mean packaging never appears in
any report of spending, and gross income reads low by the same figure.

This patch does not touch a single GL Entry. Reclassifying the account
re-files the postings that already exist, which is the whole correction; the
amounts, dates and vouchers are all untouched and still reconcile. It prints
the sum being re-filed so the change is visible in the migrate log rather
than silent — restating a live company's books should never be quiet.
"""

import frappe

from narjes_custom.setup import accounts


def execute():
	moved = []
	for company in frappe.get_all("Company", pluck="name"):
		name = accounts.resolve("Packaging Expenses", company)
		if not name:
			continue
		before = frappe.db.get_value("Account", name, ["root_type", "parent_account"], as_dict=True)
		if before.root_type != "Income":
			continue

		total = (
			frappe.db.sql(
				"""SELECT COALESCE(SUM(debit) - SUM(credit), 0)
				   FROM `tabGL Entry` WHERE account = %s AND is_cancelled = 0""",
				name,
			)[0][0]
			or 0
		)
		count = frappe.db.count("GL Entry", {"account": name, "is_cancelled": 0})
		moved.append((name, before.parent_account, total, count))

	# accounts.run() is what actually performs the reparent, and it is also
	# wired into after_migrate — so this patch stays correct if it is ever
	# re-run, and a site that has already been corrected reports nothing.
	accounts.run()

	for name, old_parent, total, count in moved:
		print(
			f"  Reclassified {name}: {old_parent} (Income) -> Indirect Expenses (Expense). "
			f"{count} existing GL entries totalling {total:,.0f} now report as spending "
			f"instead of negative income. No GL Entry was modified."
		)
