"""Canonical chart-of-accounts setup for the accounts this app posts to.

Every account `narjes_custom` books against is declared once, here, and
created (or corrected) idempotently on every migrate. Before this module the
accounts were made by a handful of one-off functions that disagreed with each
other — which is how `Packaging Expenses` ended up classified as *Income*
while the sale automation debited it as a cost, and how `setup_packaging()`
came to build an account named "Packaging Expenses - NS - NS".

The classification matters far beyond tidiness: the Money Out and Revenue
reports read the ledger by account, so an expense filed under Income is money
that leaves the shop without appearing in any report of spending.
"""

import frappe

# Account name -> how it should be classified. The parent decides root_type
# and report_type: ERPNext's Account.set_root_and_report_type() copies both
# down from the parent, so reparenting an account is what actually corrects
# its classification (and it cascades to any children).
MANAGED_ACCOUNTS = {
	"Packaging Expenses": {
		"parent": "Indirect Expenses",
		"account_type": "Expense Account",
		# Was created under Direct Income as an "Income Account" by the old
		# setup_packaging(). automate_so_flow() has always *debited* it, so
		# every packaging cost has been sitting on the books as negative
		# income instead of as an expense.
		"was": "Direct Income",
	},
	"Painting Costs": {
		"parent": "Indirect Expenses",
		"account_type": "Expense Account",
	},
	"Accrued Expenses": {
		"parent": "Current Liabilities",
		"account_type": "",
	},
	"Salary": {
		"parent": "Indirect Expenses",
		"account_type": "",
	},
}


def resolve(account_name, company):
	"""The full name of a managed account for `company`, or None."""
	return frappe.db.get_value("Account", {"account_name": account_name, "company": company})


def run():
	"""Create anything missing and correct anything misclassified."""
	for company in frappe.get_all("Company", pluck="name"):
		for account_name, spec in MANAGED_ACCOUNTS.items():
			_ensure(account_name, spec, company)


def _ensure(account_name, spec, company):
	parent = frappe.db.get_value(
		"Account", {"account_name": spec["parent"], "company": company, "is_group": 1}
	)
	if not parent:
		# A company on a non-standard chart of accounts. Skip rather than
		# guess at a parent — booking to the wrong head is worse than a
		# missing account, which _get_account() reports loudly at use time.
		return

	existing = resolve(account_name, company)
	if not existing:
		frappe.get_doc(
			{
				"doctype": "Account",
				# Deliberately *not* suffixed with the abbreviation: ERPNext
				# appends " - <abbr>" itself when it builds `name`. The old
				# setup_packaging() passed "Packaging Expenses - NS" here,
				# which would have produced "Packaging Expenses - NS - NS".
				"account_name": account_name,
				"parent_account": parent,
				"company": company,
				"is_group": 0,
				"account_type": spec["account_type"],
			}
		).insert(ignore_permissions=True)
		return

	# Correct an existing account only when it is genuinely misfiled. Writing
	# unconditionally would touch every account on every migrate and churn the
	# nested set for no reason.
	current = frappe.db.get_value(
		"Account", existing, ["parent_account", "account_type"], as_dict=True
	)
	if current.parent_account == parent and (current.account_type or "") == spec["account_type"]:
		return

	doc = frappe.get_doc("Account", existing)
	doc.parent_account = parent
	doc.account_type = spec["account_type"]
	# root_type/report_type are recomputed from the new parent on validate.
	doc.save(ignore_permissions=True)
