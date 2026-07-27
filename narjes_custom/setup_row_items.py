import frappe


def run():
    if not frappe.db.exists("Custom Field", "Item-custom_is_row"):
        doc = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Item",
            "fieldname": "custom_is_row",
            "fieldtype": "Check",
            "label": "Is Row Item",
            "insert_after": "custom_is_flower",
            "description": "Check this if the item is tracked on the Items Balance report (stock sold/measured by roll — Nos or Centimeter).",
        })
        doc.insert(ignore_permissions=True)
        print("Created Custom Field: Item-custom_is_row")
    else:
        print("Custom Field already exists: Item-custom_is_row")

    frappe.db.commit()
    print("Done!")
