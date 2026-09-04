# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

"""Narjes Debt — a register of who owes whom, in both directions.

Deliberately **not** connected to the general ledger.

ERPNext already tracks receivables properly: an invoice raises a debtor
balance and a payment clears it, and the Money In report reads exactly that.
This doctype is for the debts that live outside that machinery — cash lent to
a friend of the shop, an informal running tab, a supplier balance agreed over
the phone. Posting those to the ledger as well is how a sale that was already
invoiced and paid ends up counted twice, which would inflate the net profit
that the salary dashboard divides between four people.

So this is a register. It records, reminds and totals. It never posts.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


class NarjesDebt(Document):
	def validate(self):
		self.set_display_name()
		self.set_company()
		self.validate_amounts()
		self.roll_up_settlements()
		self.set_status()

	def set_display_name(self):
		"""One field the list view, dashboard and title can all rely on,
		whether the debtor is a Customer, a Supplier or a name written by
		hand."""
		if self.party_type == "Other":
			self.display_name = (self.party_name or "").strip()
		elif self.party:
			self.display_name = (
				frappe.db.get_value(self.party_type, self.party, "name") or self.party
			)
			if self.party_type == "Customer":
				self.display_name = (
					frappe.db.get_value("Customer", self.party, "customer_name") or self.party
				)
			elif self.party_type == "Supplier":
				self.display_name = (
					frappe.db.get_value("Supplier", self.party, "supplier_name") or self.party
				)
		if not self.display_name:
			self.display_name = _("Unnamed")

	def set_company(self):
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_value(
				"Company", {}, "name"
			)

	def validate_amounts(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("The debt amount must be more than zero."))

		if self.due_date and self.debt_date and getdate(self.due_date) < getdate(self.debt_date):
			frappe.throw(_("The settle-by date cannot be before the date the debt was taken on."))

		for row in self.settlements:
			if flt(row.amount) <= 0:
				frappe.throw(
					_("Instalment {0} has no amount. Every instalment needs one.").format(row.idx)
				)

		scheduled = sum(flt(r.amount) for r in self.settlements)
		if self.settlements and scheduled > flt(self.amount):
			# Catching this here saves someone discovering months later that
			# the plan was always going to overshoot.
			frappe.throw(
				_("The instalments add up to {0}, which is more than the debt of {1}.").format(
					frappe.format_value(scheduled, {"fieldtype": "Currency"}),
					frappe.format_value(flt(self.amount), {"fieldtype": "Currency"}),
				)
			)

	def roll_up_settlements(self):
		"""Paid = the instalments that actually have a payment date on them.

		A scheduled instalment with no `paid_on` is a plan, not a payment, and
		counting it would report a debt as settled before any money arrived.
		"""
		self.paid_amount = sum(flt(r.amount) for r in self.settlements if r.paid_on)
		self.outstanding = flt(self.amount) - flt(self.paid_amount)

	def set_status(self):
		if flt(self.outstanding) <= 0:
			self.status = "Settled"
		elif self.due_date and getdate(self.due_date) < getdate(today()):
			self.status = "Overdue"
		elif flt(self.paid_amount) > 0:
			self.status = "Partly settled"
		else:
			self.status = "Open"

	@property
	def days_overdue(self):
		if self.status != "Overdue" or not self.due_date:
			return 0
		return (getdate(today()) - getdate(self.due_date)).days
