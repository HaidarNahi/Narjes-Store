import frappe
import traceback

def run():
    customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
    
    flower_item = frappe.db.get_value("Item", {"custom_is_flower": 1, "disabled": 0}, "name")
    if not flower_item:
        frappe.get_doc({
            "doctype": "Item",
            "item_code": "Test Flower",
            "item_name": "Test Flower",
            "item_group": "Products",
            "stock_uom": "Nos",
            "custom_is_flower": 1,
            "is_stock_item": 0,
            "include_item_in_manufacturing": 0
        }).insert(ignore_permissions=True)
        flower_item = "Test Flower"

    so = frappe.get_doc({
        "doctype": "Sales Order",
        "customer": customer,
        "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
        "custom_flower_items": [
            {
                "flower_item": flower_item,
                "qty": 1,
                "rate": 5000,
                "amount": 5000,
                "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
            }
        ]
    })
    
    so.insert(ignore_permissions=True)
    
    try:
        so.submit()
        print("Success")
    except Exception as e:
        print("ERROR TRACEBACK:")
        traceback.print_exc()
