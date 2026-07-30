"""Hides the default ERPNext workspaces this shop never actually uses, so
the sidebar only shows what's relevant to a flower shop's real workflow
(Sales, Buying, Stock, Accounts, the shop's own Narjes Dashboard) instead
of every module ERPNext ships for manufacturing/services/CRM businesses.

"Hidden" here only means "not pinned in the sidebar" — every one of these
Workspaces, and every DocType/Report inside them, is still fully reachable
through the awesomebar/global search (Ctrl+G) at all times. Nothing is
deleted, uninstalled, or permission-restricted; a System Manager can also
just un-hide any of these again from Workspace settings if the business
grows into needing them.

Run via: bench execute narjes_custom.setup.workspace_visibility.run
"""

import frappe

# Enterprise/manufacturing/service modules irrelevant to this business, plus
# onboarding scaffolding and a stray duplicate workspace left over from
# early setup (see "Narjes workspace" vs. the real "Narjes Dashboard").
HIDE_WORKSPACES = [
	"Assets",
	"CRM",
	"Manufacturing",
	"Projects",
	"Quality",
	"Subcontracting",
	"Support",
	"Website",
	"Integrations",
	"Welcome Workspace",
	"Home",
	"Narjes workspace",
]


def run():
	hidden = []
	for workspace_name in HIDE_WORKSPACES:
		if not frappe.db.exists("Workspace", workspace_name):
			continue
		if frappe.db.get_value("Workspace", workspace_name, "is_hidden"):
			continue
		frappe.db.set_value("Workspace", workspace_name, "is_hidden", 1)
		hidden.append(workspace_name)

	if hidden:
		frappe.db.commit()
	print(f"Hidden {len(hidden)} workspace(s) from the sidebar: {', '.join(hidden) or '(none needed)'}")
