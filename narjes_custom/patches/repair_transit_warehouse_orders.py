"""Repair draft orders that were pointed at a Transit warehouse.

`ai_intake.api._get_default_so_items_params` used to fall back to
`get_all("Warehouse", ..., limit=1)` with no `order_by`, which means Frappe's
default of `modified desc`. The warehouse an intake-built order was assigned
to was therefore whichever warehouse happened to have been edited most
recently — and it moved as staff touched warehouse records. On this site it
landed on "Goods In Transit", a staging warehouse that never holds sellable
stock, so every affected order failed at submit with "Insufficient Stock" no
matter how much stock the shop actually had. Moving stock to satisfy the error
re-ordered the table and moved the target again.

The resolver is fixed; this repairs the rows it already wrote.

Only **draft** orders are touched. A submitted order has already written its
stock ledger, and rewriting a warehouse underneath it would desynchronise the
ledger from the document — those have to be cancelled and reissued by hand if
any exist.
"""

import frappe

from narjes_custom.ai_intake.api import _get_default_so_items_params


def execute():
	transit = frappe.get_all("Warehouse", filters={"warehouse_type": "Transit"}, pluck="name")
	if not transit:
		return

	target, _uom = _get_default_so_items_params()
	if not target:
		frappe.log_error(
			title="Transit-warehouse repair skipped",
			message="No usable non-transit warehouse exists to move draft orders to.",
		)
		return

	# Sales Order Item and Packed Item both carry a warehouse, and both are
	# checked at submit — repairing only `items` would leave bundle components
	# (the rows the shop actually saw in the error) still pointing at transit.
	for doctype, parent_field in (("Sales Order Item", "parent"), ("Packed Item", "parent")):
		rows = frappe.get_all(
			doctype,
			filters={"warehouse": ("in", transit), "parenttype": "Sales Order"},
			fields=["name", parent_field],
		)
		if not rows:
			continue

		drafts = {
			so
			for so in {r[parent_field] for r in rows}
			if frappe.db.get_value("Sales Order", so, "docstatus") == 0
		}
		repaired = [r for r in rows if r[parent_field] in drafts]
		for row in repaired:
			frappe.db.set_value(doctype, row.name, "warehouse", target, update_modified=False)

		if repaired:
			print(
				f"  repaired {len(repaired)} {doctype} row(s) across "
				f"{len(drafts)} draft Sales Order(s) -> {target}"
			)

	# set_warehouse is the order-level default shown on the form; leaving it on
	# transit would re-poison any row added later.
	for so in frappe.get_all(
		"Sales Order",
		filters={"set_warehouse": ("in", transit), "docstatus": 0},
		pluck="name",
	):
		frappe.db.set_value("Sales Order", so, "set_warehouse", target, update_modified=False)
