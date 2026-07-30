"""Curates the "Narjes Dashboard" workspace's sidebar into grouped sections
(a "Section Header" row renders as a group label instead of a link — see
Narjes Sidebar Link / Narjes Settings.sync_sidebar_links) instead of the
single "Home Dashboard" link it shipped with, so daily-use doctypes/reports
are one click away and grouped the way this shop actually works, matching
the approved Narjes Ledger design direction's sidebar grouping.

Idempotent: only inserts rows that don't already exist (matched by
workspace + label), so re-running (e.g. on every migrate) never duplicates
rows or clobbers rows an admin has since edited by hand elsewhere.

Run via: bench execute narjes_custom.setup.sidebar_layout.run
"""

import frappe

WORKSPACE = "Narjes Dashboard"

# (label, link_type, link_to, icon) — link_type "Section Header" ignores link_to.
LAYOUT = [
	("Home Dashboard", "Page", "narjes-home", "home"),
	("Store", "Section Header", None, None),
	("Sales Orders", "DocType", "Sales Order", "list-bullets"),
	("Items", "DocType", "Item", "package"),
	("Customers", "DocType", "Customer", "users-three"),
	("Deliveries", "DocType", "Delivery Note", "truck"),
	("Insights", "Section Header", None, None),
	("Revenue Report", "Report", "Sales Revenue Report", "chart-line-up"),
	("AI Order Intake", "Page", "ai-intake", "sparkle"),
]


def run():
	settings = frappe.get_single("Narjes Settings")
	existing_labels = {
		row.label for row in settings.sidebar_links if row.workspace == WORKSPACE
	}

	added = []
	for label, link_type, link_to, icon in LAYOUT:
		if label in existing_labels:
			continue
		settings.append("sidebar_links", {
			"workspace": WORKSPACE,
			"label": label,
			"link_type": link_type,
			"link_to": link_to,
			"icon": icon,
		})
		added.append(label)

	if added:
		settings.save(ignore_permissions=True)
		frappe.db.commit()
	print(f"Added {len(added)} sidebar row(s) to '{WORKSPACE}': {', '.join(added) or '(none needed)'}")
