import frappe

def run():
    board = frappe.get_doc("Kanban Board", "Order Phases")
    
    import json
    existing_fields = json.loads(board.fields or "[]")
    needed_fields = ['customer', 'username', 'delivery_id', 'delivery_date', 'gift', 'has_flower', 'has_stand', 'priority']
    
    dirty = False
    for f in needed_fields:
        if f not in existing_fields:
            existing_fields.append(f)
            dirty = True
            
    if dirty:
        board.fields = json.dumps(existing_fields)
        board.save()
        frappe.db.commit()
        print("Updated Kanban Board fields")
    else:
        print("Kanban Board fields already updated")
