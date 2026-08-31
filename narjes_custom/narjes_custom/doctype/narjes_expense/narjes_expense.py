# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

"""Narjes Expense — a shop-owner-friendly way to record money going out.

ERPNext already has everything needed to *hold* an expense: a chart of
accounts with 30-odd expense heads, Journal Entries, and the P&L that reads
them. What it has no answer for is the shop owner who wants to record "I paid
Meta 131,000 for ads today" without knowing which account to debit and which
to credit. That question is the entire reason this doctype exists.

So this is a thin, friendly face over a Journal Entry — not a parallel
accounting system. On submit it posts a real JE (debit the expense head,
credit the cash account) and links it. Every existing report — Profit and
Loss, Trial Balance, General Ledger — picks it up with no changes, because
underneath it is exactly the document those reports already understand.

Cancelling the expense cancels the Journal Entry with it, so the books can
never disagree with the list the shop is reading.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# Account root types that money may be spent *from*. Anything else — an income
# head, an equity account — would produce a Journal Entry that balances but
# describes something that did not happen.
PAID_FROM_TYPES = ("Cash", "Bank")


class NarjesExpense(Document):
	def validate(self):
		self.validate_amount()
		self.validate_accounts()
		self.set_defaults()

	def validate_amount(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))

	def validate_accounts(self):
		"""Both accounts are Links to the same doctype, so nothing stops a
		mistyped one from being an income head or a group. The Journal Entry
		would still balance — it would just be wrong, and wrong in a way that
		is tedious to unpick once it is in the ledger."""
		category = frappe.db.get_value(
			"Account", self.expense_account, ["root_type", "is_group", "company"], as_dict=True
		)
		if not category:
			frappe.throw(_("Category account {0} does not exist.").format(self.expense_account))
		if category.is_group:
			frappe.throw(
				_("{0} is a group account. Pick the specific expense head underneath it.").format(
					frappe.bold(self.expense_account)
				)
			)
		if category.root_type != "Expense":
			frappe.throw(
				_("{0} is a {1} account, not an Expense account.").format(
					frappe.bold(self.expense_account), category.root_type
				)
			)

		source = frappe.db.get_value("Account", self.paid_from, ["account_type", "is_group"], as_dict=True)
		if not source:
			frappe.throw(_("Paid From account {0} does not exist.").format(self.paid_from))
		if source.is_group:
			frappe.throw(_("Paid From cannot be a group account."))
		if source.account_type not in PAID_FROM_TYPES:
			frappe.throw(
				_("Paid From must be a Cash or Bank account. {0} is {1}.").format(
					frappe.bold(self.paid_from), source.account_type or _("neither")
				)
			)

	def set_defaults(self):
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_value(
				"Company", {}, "name"
			)
		if not self.cost_center:
			self.cost_center = frappe.db.get_value(
				"Company", self.company, "cost_center"
			) or frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 0}, "name")

	def on_submit(self):
		self.create_journal_entry()

	def create_journal_entry(self):
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"posting_date": self.expense_date,
				"company": self.company,
				"user_remark": self.journal_remark(),
				"accounts": [
					{
						"account": self.expense_account,
						"debit_in_account_currency": flt(self.amount),
						"cost_center": self.cost_center,
					},
					{
						"account": self.paid_from,
						"credit_in_account_currency": flt(self.amount),
						"cost_center": self.cost_center,
					},
				],
			}
		)
		je.insert(ignore_permissions=True)
		je.submit()

		# db_set rather than assignment: this runs inside on_submit, after the
		# document has been written, so a plain assignment would be discarded.
		self.db_set("journal_entry", je.name)

	def journal_remark(self):
		parts = [self.description or _("Expense")]
		if self.payee:
			parts.append(_("paid to {0}").format(self.payee))
		parts.append(f"({self.name})")
		return " ".join(parts)

	def on_cancel(self):
		"""Cancel the Journal Entry too, so the ledger and this list can never
		tell two different stories."""
		if not self.journal_entry:
			return
		je = frappe.get_doc("Journal Entry", self.journal_entry)
		if je.docstatus == 1:
			je.cancel()
