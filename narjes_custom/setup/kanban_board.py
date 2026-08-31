"""
narjes_custom.setup.kanban_board
=================================
Creates/repairs the "Order Phases" Kanban board that Sales Order navigation
is funneled onto (see public/js/sales_order_list.js, which redirects the
plain Sales Order List View to this board).

There used to be two near-identical copies of this script living in two
different places, disagreeing on a couple of column colors — see
NARJES_STORE_SYSTEM.md §14.4. This is the one canonical version.

Run via: bench --site <site> execute narjes_custom.setup.kanban_board.run
"""

import json

import frappe

BOARD_NAME = "Order Phases"
REFERENCE_DOCTYPE = "Sales Order"
FIELDNAME = "order_phase"

# Must stay in sync with the order_phase Select options in
# narjes_custom.setup.custom_fields.
COLUMN_COLORS = {
    "New": "Light Blue",
    "In Design": "Purple",
    "Waiting Approval": "Orange",
    "Ready to Execution": "Blue",
    "Execution": "Cyan",
    "Waiting": "Yellow",
    "In Delivery": "Pink",
    "Done": "Green",
    "Cancelled": "Red",
    "Returned": "Gray",
}

# Extra fields the custom Kanban card renderer (sales_order_list.js) needs
# beyond what Frappe fetches for a Kanban board by default.
#
# owner/creation/_assign are NOT listed: Frappe's KanbanView.set_fields()
# already adds those itself, and the assignee chip reads the parsed
# _assign that prepare_card() hands over.
EXTRA_CARD_FIELDS = [
    "customer", "username", "delivery_id", "delivery_date",
    "gift", "has_flower", "has_stand", "priority",
    # the card shows the order value; currency comes along so the amount is
    # labelled in the order's own currency rather than a guessed default
    "grand_total", "currency",
]


def run():
    if not frappe.db.exists("Kanban Board", BOARD_NAME):
        board = frappe.new_doc("Kanban Board")
        board.name = BOARD_NAME
        board.kanban_board_name = BOARD_NAME
        board.reference_doctype = REFERENCE_DOCTYPE
        board.field_name = FIELDNAME
        board.insert(ignore_permissions=True)
        print(f"Created Kanban Board: {BOARD_NAME}")
    else:
        board = frappe.get_doc("Kanban Board", BOARD_NAME)
        print(f"Kanban Board '{BOARD_NAME}' already exists.")

    existing_columns = {c.column_name: c for c in board.columns}
    dirty = False
    for phase, color in COLUMN_COLORS.items():
        if phase not in existing_columns:
            board.append("columns", {"column_name": phase, "status": "Active", "indicator": color})
            dirty = True
        elif existing_columns[phase].indicator != color:
            existing_columns[phase].indicator = color
            dirty = True

    # Kanban Board.fields is a plain JSON-encoded list of field name
    # strings (Code/JSON fieldtype), not a child table — the original
    # script this was consolidated from (§14.4) assumed it was a child
    # table with .fieldname rows, which would raise AttributeError the
    # first time it ran against a board whose `fields` was non-empty.
    existing_fields = json.loads(board.fields) if board.fields else []
    for fieldname in EXTRA_CARD_FIELDS:
        if fieldname not in existing_fields:
            existing_fields.append(fieldname)
            dirty = True
    board.fields = json.dumps(existing_fields)

    if dirty:
        board.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"Synced columns/fields for '{BOARD_NAME}'.")
    else:
        print(f"'{BOARD_NAME}' already up to date.")


if __name__ == "__main__":
    run()
