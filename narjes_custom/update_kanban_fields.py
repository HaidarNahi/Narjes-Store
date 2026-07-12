import frappe
import json

def run():
    board = frappe.get_doc("Kanban Board", "Order Phases")
    existing_fields = json.loads(board.fields) if board.fields else []
    
    required_fields = ["customer", "username", "delivery_id", "delivery_date", "creation", "priority", "gift", "has_flower", "has_stand", "owner"]
    
    added = False
    for f in required_fields:
        if f not in existing_fields:
            existing_fields.append(f)
            added = True
            
    if added:
        board.fields = json.dumps(existing_fields)
        board.save(ignore_permissions=True)
        frappe.db.commit()
        print("Updated Kanban Board fields.")
    else:
        print("Fields already exist.")
