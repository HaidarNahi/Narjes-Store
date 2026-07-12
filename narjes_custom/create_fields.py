import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def run():
    custom_fields = {
        "Sales Order": [
            {"fieldname": "has_flower", "label": "Has Flower", "fieldtype": "Check", "hidden": 1, "insert_after": "gift"},
            {"fieldname": "has_stand", "label": "Has Stand", "fieldtype": "Check", "hidden": 1, "insert_after": "has_flower"}
        ]
    }
    create_custom_fields(custom_fields, ignore_validate=True)
    frappe.db.commit()
    print("Custom fields created successfully.")
