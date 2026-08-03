"""Seeds any AI Intake Settings field that has never been saved with the
default declared on the doctype.

Frappe applies a field's `default` when a document is created, not when a
field is added to a doctype that already has a row. For a Single like AI
Intake Settings that means every new setting reads back as NULL — and a
Check field reading NULL is indistinguishable from a Check the admin
deliberately unticked. Adding `enabled` without this would have silently
switched AI Order Intake off on the next migrate.

Only fields with no stored value at all are touched, so an admin who turns
something off keeps it off across migrations.

Run via: bench execute narjes_custom.setup.ai_intake_defaults.run
"""

import frappe

SETTINGS_DOCTYPE = "AI Intake Settings"

# Layout-only fieldtypes hold no value to seed
LAYOUT_FIELDTYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Heading"}


def run():
	if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
		print(f"{SETTINGS_DOCTYPE} not installed yet — nothing to seed.")
		return

	stored = frappe.db.get_singles_dict(SETTINGS_DOCTYPE)
	meta = frappe.get_meta(SETTINGS_DOCTYPE)

	doc = frappe.get_doc(SETTINGS_DOCTYPE)
	seeded = []

	for df in meta.fields:
		if df.fieldtype in LAYOUT_FIELDTYPES:
			continue
		if df.fieldname in stored:
			continue
		if df.default in (None, ""):
			continue
		doc.set(df.fieldname, df.default)
		seeded.append(df.fieldname)

	if not seeded:
		print("AI Intake Settings: all settings already have a stored value.")
		return

	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()
	print(f"AI Intake Settings: seeded {len(seeded)} setting(s) — {', '.join(seeded)}")
