"""
narjes_custom.expenses.api
===========================
Whitelisted endpoints for the Narjes Expense form.

The only thing exposed is *reading* a sentence into form fields. Nothing here
creates, submits or posts anything: the expense is saved and submitted by the
person looking at the filled-in form, through the ordinary doctype flow. That
separation is deliberate — an AI that can post to the general ledger without a
human in the loop is a bad idea no matter how good the model is.
"""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from narjes_custom.ai_intake.extraction import ExtractionError
from narjes_custom.expenses import extraction

# How far back a parsed date may plausibly sit. A model with no clock resolves
# "yesterday" against its own training cutoff — in testing that produced a date
# two years stale, which would post the expense into a closed period without
# anyone noticing. The prompt now carries the real date; this is the backstop
# for when the model ignores it anyway.
MAX_BACKDATE_DAYS = 370


def _safe_date(value, warnings):
	"""A trustworthy expense date, or today with an explanation."""
	today = getdate(nowdate())

	if not value:
		return nowdate()

	try:
		parsed = getdate(value)
	except Exception:
		warnings.append(_("Could not read a date from that — using today."))
		return nowdate()

	if parsed > today:
		warnings.append(_("That date ({0}) is in the future — using today instead.").format(value))
		return nowdate()

	if (today - parsed).days > MAX_BACKDATE_DAYS:
		warnings.append(
			_("That date ({0}) looks wrong — using today. Set it by hand if it really was then.").format(
				value
			)
		)
		return nowdate()

	return str(parsed)


@frappe.whitelist()
def parse_expense(raw_text, company=None):
	"""Read a free-text note into Narjes Expense field values.

	Returns {"ok": True, "fields": {...}, "warnings": [...]} — never raises
	for an ordinary "could not understand" case, because the form should show
	that as a message next to the fields rather than as a traceback dialog.
	"""
	frappe.has_permission("Narjes Expense", ptype="create", throw=True)

	try:
		fields = extraction.extract_expense(raw_text, company)
	except ExtractionError as e:
		return {"ok": False, "error": str(e)}

	warnings = []

	fields["expense_date"] = _safe_date(fields.get("expense_date"), warnings)

	if not fields.get("amount"):
		warnings.append(_("No amount found — type it in yourself."))
	if not fields.get("expense_account"):
		warnings.append(_("No category matched confidently — choose one below."))

	return {"ok": True, "fields": fields, "warnings": warnings}


@frappe.whitelist()
def get_expense_summary(from_date=None, to_date=None, company=None):
	"""Submitted expense totals per category for a period.

	Backs the "where did the money go" question the shop actually asks. Reads
	only submitted expenses — a draft is something someone is still typing,
	not money that left.
	"""
	frappe.has_permission("Narjes Expense", throw=True)

	filters = {"docstatus": 1}
	if company:
		filters["company"] = company
	if from_date and to_date:
		filters["expense_date"] = ("between", [from_date, to_date])
	elif from_date:
		filters["expense_date"] = (">=", from_date)
	elif to_date:
		filters["expense_date"] = ("<=", to_date)

	rows = frappe.get_all(
		"Narjes Expense",
		filters=filters,
		fields=["expense_account", "amount", "payee"],
		limit_page_length=0,
	)

	by_category = {}
	for row in rows:
		by_category[row.expense_account] = by_category.get(row.expense_account, 0) + (row.amount or 0)

	return {
		"total": sum(by_category.values()),
		"count": len(rows),
		"by_category": sorted(
			({"account": k, "amount": v} for k, v in by_category.items()),
			key=lambda r: r["amount"],
			reverse=True,
		),
	}
