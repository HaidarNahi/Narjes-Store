import frappe

def run():
    board_name = "Order Phases"
    reference_doctype = "Sales Order"
    fieldname = "order_phase"

    if not frappe.db.exists("Kanban Board", board_name):
        doc = frappe.new_doc("Kanban Board")
        doc.name = board_name
        doc.kanban_board_name = board_name
        doc.reference_doctype = reference_doctype
        doc.field_name = fieldname
        doc.insert(ignore_permissions=True)
        print(f"Created Kanban Board: {board_name}")
    else:
        doc = frappe.get_doc("Kanban Board", board_name)
        print(f"Kanban Board {board_name} already exists.")

    colors = {
        "New": "Light Blue",
        "In Design": "Purple",
        "Waiting Approval": "Orange",
        "Ready to Execution": "Blue",
        "Execution": "Cyan",
        "Waiting": "Yellow",
        "In Delivery": "Pink",
        "Done": "Green",
        "Cancelled": "Red",
        "Returned": "Gray"
    }

    # Add columns if they don't exist
    existing_columns = {c.column_name: c for c in doc.columns}
    
    dirty = False
    for phase, color in colors.items():
        if phase not in existing_columns:
            doc.append("columns", {
                "column_name": phase,
                "status": "Active",
                "indicator": color
            })
            dirty = True
        else:
            if existing_columns[phase].indicator != color:
                existing_columns[phase].indicator = color
                dirty = True

    if dirty:
        doc.save(ignore_permissions=True)
        print(f"Updated columns for {board_name}")

    frappe.db.commit()
