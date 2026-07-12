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
