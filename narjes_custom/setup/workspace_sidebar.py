"""Replaces the auto-generated, "every doctype in the module" sidebar (see
frappe.desk.doctype.workspace_sidebar.workspace_sidebar.auto_generate_sidebar_from_module)
with a small, curated one matching the Narjes Ledger design direction: a
handful of daily-use items grouped into "Store" and "Insights", instead of
every DocType/Report/Page the narjes_custom module happens to register.

This is a deliberate declutter, not data loss — anything left out (Purchase
Order, Painting Cost, Items Balance, ...) is still one Ctrl+G search away.

Mechanically: Frappe only auto-generates a module's sidebar when no
"Workspace Sidebar" doc already exists for that module (see
auto_generate_sidebar_from_module's `frappe.db.exists(...)` guard) — so
creating one, once, permanently opts this module out of the generic
auto-generated list in favor of this curated one.

Run via: bench execute narjes_custom.setup.workspace_sidebar.run
"""

import frappe

MODULE = "Narjes Custom"

ITEMS = [
	{"type": "Link", "label": "Home", "link_type": "Page", "link_to": "narjes-home", "icon": "house"},
	{"type": "Section Break", "label": "Store", "collapsible": 1},
	{"type": "Link", "label": "Sales Orders", "link_type": "DocType", "link_to": "Sales Order", "icon": "list-bullets"},
	{"type": "Link", "label": "Items", "link_type": "DocType", "link_to": "Item", "icon": "package"},
	{"type": "Link", "label": "Customers", "link_type": "DocType", "link_to": "Customer", "icon": "users-three"},
	{"type": "Link", "label": "Deliveries", "link_type": "DocType", "link_to": "Delivery Note", "icon": "truck"},
	{"type": "Section Break", "label": "Money", "collapsible": 1},
	{"type": "Link", "label": "Expenses", "link_type": "DocType", "link_to": "Narjes Expense", "icon": "receipt"},
	{"type": "Section Break", "label": "Insights", "collapsible": 1},
	{"type": "Link", "label": "Revenue Report", "link_type": "Report", "link_to": "Sales Revenue Report", "icon": "chart-line-up"},
	{"type": "Link", "label": "AI Order Intake", "link_type": "Page", "link_to": "ai-intake", "icon": "sparkle"},
]


def run():
	if frappe.db.exists("Workspace Sidebar", MODULE):
		doc = frappe.get_doc("Workspace Sidebar", MODULE)
	else:
		doc = frappe.new_doc("Workspace Sidebar")
		doc.title = MODULE
		doc.module = MODULE
		doc.app = "narjes_custom"

	doc.set("items", [])
	for item in ITEMS:
		doc.append("items", item)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"Curated Workspace Sidebar for module '{MODULE}' with {len(ITEMS)} item(s).")
