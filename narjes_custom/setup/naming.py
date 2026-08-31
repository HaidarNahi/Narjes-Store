"""Sales Order naming: SO-YYMMDD-### (e.g. SO-260820-001).

ERPNext ships `SAL-ORD-.YYYY.-` with a five-digit counter that runs all year,
so the name says nothing except roughly how many orders have ever existed.
The shop reads order numbers off a whiteboard and a box sticker, where the
date is the useful part and a short daily counter is what people actually say
out loud ("order twelve today").

The daily reset is free, not implemented: Frappe keys its counter on the
*resolved* prefix, so `SO-260820-` is a different Series row from
`SO-260821-` and each one starts at 1 on its own.

Run via: bench execute narjes_custom.setup.naming.run
"""

import frappe

DOCTYPE = "Sales Order"
SERIES = "SO-.YY..MM..DD.-.###"


def run():
	_set_series()
	_normalise_existing()


def _set_series():
	"""Point the naming_series field at the new format."""
	current = frappe.db.get_value(
		"Property Setter",
		{"doc_type": DOCTYPE, "field_name": "naming_series", "property": "options"},
		"name",
	)
	if current:
		frappe.db.set_value("Property Setter", current, "value", SERIES)
	else:
		frappe.get_doc({
			"doctype": "Property Setter",
			"doctype_or_field": "DocField",
			"doc_type": DOCTYPE,
			"field_name": "naming_series",
			"property": "options",
			"property_type": "Text",
			"value": SERIES,
		}).insert(ignore_permissions=True)

	frappe.clear_cache(doctype=DOCTYPE)


def _normalise_existing():
	"""Repoint old documents' `naming_series` at the surviving option.

	Their `name` is untouched — renaming submitted orders would break every
	link, print-out and delivery reference that already quotes them. This is
	only the metadata field, and it matters because Frappe validates Select
	values on save: a draft still holding `SAL-ORD-.YYYY.-` would refuse to
	save once that string is no longer an option.
	"""
	stale = frappe.get_all(
		DOCTYPE,
		filters={"naming_series": ("!=", SERIES)},
		pluck="name",
		limit_page_length=0,
	)
	for name in stale:
		frappe.db.set_value(DOCTYPE, name, "naming_series", SERIES, update_modified=False)
	if stale:
		print(f"  repointed naming_series on {len(stale)} existing order(s) (names unchanged)")
