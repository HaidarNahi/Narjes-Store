"""Recalculate draft sales documents after the delivery-fee charge rows were removed.

`strip_delivery_charge_rows` deletes the rows straight from the child table,
which is the only safe way to touch documents in bulk — but it leaves the
parents' stored totals as they were. Two figures are then wrong on every
affected draft:

* `grand_total` still contains the deleted delivery fee, so the shop's own
  revenue reads high.
* `total_with_delivery_fees` was computed by the old formula, and it is the
  figure printed on the sticker that goes on the box — the amount the customer
  hands to the courier. A wrong value there is money collected wrongly, which
  is why this cannot wait for someone to happen to re-open each order.

Only a real save recomputes these: ERPNext derives grand_total from the
charges table inside its own validate(), so writing the fields directly would
just be a second guess at the same arithmetic.

Each document gets a savepoint. A draft that fails validation for an unrelated
reason (short stock, a missing account) is left exactly as it was and reported,
rather than taking the other 38 down with it.
"""

import frappe

DOCTYPES = ("Sales Order", "Sales Invoice", "Delivery Note")


def execute():
	for doctype in DOCTYPES:
		names = frappe.get_all(doctype, filters={"docstatus": 0}, pluck="name")
		if not names:
			continue

		fixed, failed = 0, []
		for index, name in enumerate(names):
			save_point = f"recompute_{index}"
			try:
				frappe.db.savepoint(save_point)
				doc = frappe.get_doc(doctype, name)
				before = doc.get("total_with_delivery_fees")
				doc.save(ignore_permissions=True)
				if doc.get("total_with_delivery_fees") != before:
					fixed += 1
			except Exception as e:
				frappe.db.rollback(save_point=save_point)
				failed.append(f"{name}: {str(e).splitlines()[0][:80]}")

		print(f"  {doctype}: recalculated {fixed} of {len(names)} draft(s)")
		for line in failed:
			print(f"    could not save {line}")
