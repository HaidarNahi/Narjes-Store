"""One-off repairs to UI records that live in the database rather than in git.

These were authored through the UI (Client Scripts, per-user grid settings), so
they are invisible to the app's fixtures and travel with neither git nor
`bench migrate`. Each fix below is idempotent and safe to re-run; they run on
after_migrate so a restored/fresh site converges to the same working state.

Run via: bench --site <site> execute narjes_custom.setup.fix_legacy_ui.run
"""

import frappe

SUPPLIER_CONTACTS = "Supplier Contacts"

# The Client Script fetches a "rate" off Item to prefill the Sales Order Item
# rate, but Item has no `rate` field (nor `custom_rate`) — the call failed with
# "Field not permitted in query: rate" on every item selection, so the rate was
# never prefilled. `standard_rate` (Standard Selling Rate) is the real field,
# and the script's own comment says to repoint it.
RATE_SCRIPT = "fetching the rate of the product bundle from the `rate` inside the item"


def run():
	_repoint_rate_client_script()
	_clear_supplier_contacts_grid_overrides()
	frappe.db.commit()


def _repoint_rate_client_script():
	if not frappe.db.exists("Client Script", RATE_SCRIPT):
		print("rate Client Script: not present, nothing to do")
		return

	doc = frappe.get_doc("Client Script", RATE_SCRIPT)
	# Match the assignment specifically: the script also contains a legitimate
	# `set_value(cdt, cdn, 'rate', ...)` (the destination field), so a bare
	# "'rate' in script" test would report a false "needs fixing" forever.
	broken = "let source_fieldname = 'rate';"
	if broken not in doc.script:
		print("rate Client Script: already repointed to standard_rate")
		return

	doc.script = doc.script.replace(broken, "let source_fieldname = 'standard_rate';")
	doc.save(ignore_permissions=True)
	print("rate Client Script: source field 'rate' -> 'standard_rate'")


def _clear_supplier_contacts_grid_overrides():
	"""Drop every user's saved "Configure Columns" override for the Supplier
	Contacts grid, so the column set/widths defined on the child doctype apply.

	Frappe's grid prefers User Settings > GridView over the doctype's own
	in_list_view/columns, so without this a user who reconfigured the grid once
	keeps their old columns no matter what the doctype says.
	"""
	rows = frappe.db.sql(
		"select user, data from `__UserSettings` where doctype = 'Supplier'", as_dict=True
	)
	cleared = 0
	for row in rows:
		try:
			settings = frappe.parse_json(row.data) or {}
		except Exception:
			continue

		grid_view = settings.get("GridView")
		if not isinstance(grid_view, dict) or SUPPLIER_CONTACTS not in grid_view:
			continue

		del grid_view[SUPPLIER_CONTACTS]
		settings["GridView"] = grid_view or None
		frappe.db.sql(
			"update `__UserSettings` set data = %s where doctype = 'Supplier' and user = %s",
			(frappe.as_json(settings), row.user),
		)
		cleared += 1

	print(f"Supplier Contacts grid overrides cleared for {cleared} user(s)")
