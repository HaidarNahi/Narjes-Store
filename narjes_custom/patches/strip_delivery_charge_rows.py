"""Remove delivery-fee charge rows from draft sales documents.

The delivery fee used to be injected into Sales Taxes and Charges against the
"Service" income account, which booked it as revenue. It is not revenue: the
third-party courier collects the whole amount from the customer, keeps the
delivery portion and remits only the goods value, so the shop never receives
that money and is never owed it. See `_strip_delivery_charge` in api.py.

Only **draft** documents are rewritten. A submitted invoice has already
written its GL entries, and quietly editing the charges table underneath it
would leave the document disagreeing with the ledger it produced. The income
already booked from submitted invoices is reversed by a dated Journal Entry
instead, which is both correct and auditable.
"""

import frappe

DESCRIPTION = "Delivery Fees"
PARENT_TYPES = ("Sales Order", "Sales Invoice", "Delivery Note")


def execute():
	rows = frappe.get_all(
		"Sales Taxes and Charges",
		filters={"description": DESCRIPTION, "parenttype": ("in", PARENT_TYPES)},
		fields=["name", "parent", "parenttype", "tax_amount"],
	)
	if not rows:
		return

	removed = 0
	for row in rows:
		if frappe.db.get_value(row.parenttype, row.parent, "docstatus") != 0:
			continue
		frappe.db.delete("Sales Taxes and Charges", {"name": row.name})
		removed += 1

	if removed:
		print(f"  removed {removed} delivery-fee charge row(s) from draft documents")
		# The parents' stored totals still include the deleted row. They are
		# recalculated on the next save, and a draft is always saved before it
		# can be submitted, so there is no path from here to a submitted
		# document carrying a stale total.
		print("  parent totals refresh on next save")
