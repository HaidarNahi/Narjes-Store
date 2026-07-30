import frappe
from narjes_custom.api import sales_order_before_validate

def run():
    frappe.flags.in_test = True
    for so in frappe.get_all("Sales Order", pluck="name"):
        doc = frappe.get_doc("Sales Order", so)
        sales_order_before_validate(doc, None)
        doc.db_update()
    frappe.db.commit()
    print("Backfill complete")


def backfill_has_flower():
    """Recompute `has_flower` on existing Sales Orders against the current
    rule — any row in the `custom_flower_items` child table — so the kanban
    flower icon is correct on orders created before that rule changed (it
    used to sniff for the substring "flower" in the main `items` table).

    Writes only the derived `has_flower` flag, with update_modified=False:
    no validation re-runs, no total is recalculated, and submitted documents
    are otherwise untouched. Idempotent — re-running is a no-op.

    Run via: bench --site <site> execute narjes_custom.backfill.backfill_has_flower
    """
    child_doctype = frappe.get_meta("Sales Order").get_field(
        "custom_flower_items"
    ).options

    changed = 0
    for name in frappe.get_all("Sales Order", pluck="name"):
        has_flower = 1 if frappe.db.exists(
            child_doctype,
            {"parent": name, "parenttype": "Sales Order", "parentfield": "custom_flower_items"},
        ) else 0

        if frappe.db.get_value("Sales Order", name, "has_flower") != has_flower:
            frappe.db.set_value(
                "Sales Order", name, "has_flower", has_flower, update_modified=False
            )
            changed += 1

    frappe.db.commit()
    print(f"has_flower backfill: {changed} Sales Order(s) updated")
