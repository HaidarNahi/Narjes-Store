import frappe

def run():
    so = frappe.get_meta("Sales Order")
    for f in so.fields:
        if "phase" in f.fieldname or "order" in f.fieldname:
            print(f.fieldname, f.fieldtype, f.options)
