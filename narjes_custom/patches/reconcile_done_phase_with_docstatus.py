"""Reconcile the Done phase with docstatus on existing orders.

The board used to write `order_phase = "Done"` and *then* submit, in two
separate requests. When the submit failed — short stock being the usual cause
— the phase change stayed committed, leaving drafts parked in the Done column.
The board said the order was finished; ERPNext said it had never been
submitted.

Both directions are repaired, and neither invents a business outcome:

* **Draft in Done** — moved back to the last phase before Done. These orders
  were never submitted, so calling them done is the false statement; nothing
  is submitted here, because a submit can fail for real reasons and that is a
  decision for staff, not a migration.
* **Submitted not in Done** — moved to Done. The submit is the thing that
  actually happened, so the phase is simply catching up.

Cancelled orders are left alone entirely: "Cancelled" is its own phase and a
cancelled order legitimately sits outside Done.
"""

import frappe

# The phase immediately before Done, per the column order in
# narjes_custom.setup.kanban_board.
PHASE_BEFORE_DONE = "In Delivery"


def execute():
	stranded = frappe.get_all(
		"Sales Order",
		filters={"order_phase": "Done", "docstatus": 0},
		pluck="name",
	)
	for name in stranded:
		frappe.db.set_value("Sales Order", name, "order_phase", PHASE_BEFORE_DONE, update_modified=False)
	if stranded:
		print(
			f"  moved {len(stranded)} unsubmitted order(s) out of Done -> "
			f"{PHASE_BEFORE_DONE}: {', '.join(stranded)}"
		)

	lagging = frappe.get_all(
		"Sales Order",
		filters={"order_phase": ("!=", "Done"), "docstatus": 1},
		pluck="name",
	)
	# A submitted order that staff deliberately parked in Returned is a real
	# state, not drift — only phases that precede Done are caught up.
	lagging = [
		name
		for name in lagging
		if frappe.db.get_value("Sales Order", name, "order_phase") not in ("Returned", "Cancelled")
	]
	for name in lagging:
		frappe.db.set_value("Sales Order", name, "order_phase", "Done", update_modified=False)
	if lagging:
		print(f"  moved {len(lagging)} submitted order(s) into Done: {', '.join(lagging)}")
