# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

DASHBOARD_WORKSPACE = "Narjes Dashboard"


class NarjesSettings(Document):
	def on_update(self):
		sync_sidebar_links(self)


def sync_sidebar_links(doc):
	"""Rebuild the Narjes Dashboard workspace sidebar from the configured links."""
	if not frappe.db.exists("Workspace", DASHBOARD_WORKSPACE):
		return

	workspace = frappe.get_doc("Workspace", DASHBOARD_WORKSPACE)
	workspace.set("links", [])
	workspace.append("links", {
		"type": "Link",
		"label": "Home Dashboard",
		"link_to": "narjes-home",
		"link_type": "Page",
	})

	for row in doc.sidebar_links:
		workspace.append("links", {
			"type": "Link",
			"label": row.label,
			"link_to": row.link_to,
			"link_type": row.link_type,
		})

	workspace.save(ignore_permissions=True)
