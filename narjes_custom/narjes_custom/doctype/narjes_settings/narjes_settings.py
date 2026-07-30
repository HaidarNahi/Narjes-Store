# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class NarjesSettings(Document):
	def on_update(self):
		sync_sidebar_links(self)


def sync_sidebar_links(doc):
	"""Rebuild the sidebar of every Workspace referenced in sidebar_links.

	Only Workspaces that have at least one configured row are touched — a
	Workspace with no rows here is left exactly as-is (native/manual edits
	are never overwritten unless the admin explicitly manages it here).
	"""
	rows_by_workspace = {}
	for row in doc.sidebar_links:
		rows_by_workspace.setdefault(row.workspace, []).append(row)

	for workspace_name, rows in rows_by_workspace.items():
		if not frappe.db.exists("Workspace", workspace_name):
			continue

		workspace = frappe.get_doc("Workspace", workspace_name)
		workspace.set("links", [])
		for row in rows:
			if row.link_type == "Section Header":
				workspace.append("links", {"type": "Card Break", "label": row.label})
			else:
				workspace.append("links", {
					"type": "Link",
					"label": row.label,
					"link_to": row.link_to,
					"link_type": row.link_type,
				})
		workspace.save(ignore_permissions=True)
