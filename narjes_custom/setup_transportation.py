import frappe

def create_new_page():
    page_name = "ai-intake"
    if not frappe.db.exists("Page", page_name):
        page = frappe.get_doc({
            "doctype": "Page",
            "page_name": page_name,
            "title": "AI Order Intake",
            "module": "Narjes Custom",
            "standard": "Yes",
            "roles": [
                {"role": "System Manager"},
                {"role": "Sales User"}
            ]
        })
        page.insert(ignore_permissions=True)
        frappe.db.commit()
        print(f"Created Page: {page_name}")
    else:
        print(f"Page already exists: {page_name}")

create_new_page()
