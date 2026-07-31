#!/usr/bin/env python3
"""Scaffold the storefront doctypes (plan W2) as app-owned JSON + controllers.

App-owned doctypes live in the repo as JSON (not as fixtures), so they are
versioned, reviewable, and installed by `bench migrate` on any site.

Run from the app root:  python3 scripts/scaffold_storefront_doctypes.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "narjes_custom" / "narjes_custom" / "doctype"
MODULE = "Narjes Custom"
CREATED = "2026-07-31 00:00:00.000000"

PERMS_MASTER = [
	{
		"create": 1, "delete": 1, "email": 1, "export": 1, "print": 1, "read": 1,
		"report": 1, "role": "System Manager", "share": 1, "write": 1,
	},
	{
		"create": 1, "delete": 0, "email": 1, "export": 1, "print": 1, "read": 1,
		"report": 1, "role": "Sales User", "share": 1, "write": 1,
	},
]


def field(fieldname, label=None, fieldtype="Data", **kw):
	f = {"fieldname": fieldname, "fieldtype": fieldtype}
	if label:
		f["label"] = label
	f.update(kw)
	return f


def doctype(name, fields, *, istable=0, issingle=0, title_field=None,
            autoname=None, search_fields=None, sort_field="modified"):
	doc = {
		"actions": [],
		"allow_rename": 1,
		"creation": CREATED,
		"doctype": "DocType",
		"editable_grid": 1,
		"engine": "InnoDB",
		"field_order": [f["fieldname"] for f in fields],
		"fields": fields,
		"index_web_pages_for_search": 1,
		"links": [],
		"modified": CREATED,
		"modified_by": "Administrator",
		"module": MODULE,
		"name": name,
		"owner": "Administrator",
		"permissions": [] if istable else PERMS_MASTER,
		"sort_field": sort_field,
		"sort_order": "DESC",
		"states": [],
	}
	if istable:
		doc["istable"] = 1
	if issingle:
		doc["issingle"] = 1
		doc["allow_rename"] = 0
	if title_field:
		doc["title_field"] = title_field
	if autoname:
		doc["autoname"] = autoname
	if search_fields:
		doc["search_fields"] = search_fields
	return doc


DOCTYPES = [
	# ---------------------------------------------------------------- media
	doctype(
		"Narjes Product Media",
		[
			field("image", "Image", "Attach Image", in_list_view=1, columns=3, reqd=1),
			field("alt_text", "Alt Text", "Data", in_list_view=1, columns=5,
			      description="Describes the photo for screen readers and search engines."),
			field("is_primary", "Primary", "Check", in_list_view=1, columns=1),
		],
		istable=1,
	),
	# ------------------------------------------------------------- category
	doctype(
		"Narjes Storefront Category",
		[
			field("category_name_en", "Name (English)", "Data", reqd=1, in_list_view=1),
			field("category_name_ar", "Name (العربية)", "Data", reqd=1, in_list_view=1),
			field("published", "Published", "Check", default="1", in_list_view=1),
			field("cb_1", fieldtype="Column Break"),
			field("slug", "Slug", "Data", description="URL segment. Auto-generated if blank."),
			field("display_order", "Display Order", "Int"),
			field("image", "Image", "Attach Image"),
			field("sb_desc", "Description", "Section Break"),
			field("description_en", "Description (English)", "Small Text"),
			field("description_ar", "Description (العربية)", "Small Text"),
		],
		title_field="category_name_en",
		autoname="field:category_name_en",
		sort_field="display_order",
	),
	# ------------------------------------------------------------- settings
	doctype(
		"Narjes Storefront Settings",
		[
			field("sb_status", "Status", "Section Break"),
			field("storefront_enabled", "Storefront Enabled", "Check", default="1",
			      description="Turn the public store on or off. When off, visitors see a maintenance page."),
			field("noindex", "Discourage Search Engines", "Check", default="1",
			      description="Keep on until launch. Adds a noindex tag to every page."),
			field("cb_status", fieldtype="Column Break"),
			field("default_language", "Default Language", "Select", options="ar\nen", default="ar"),
			field("orders_enabled", "Accept Orders", "Check", default="1",
			      description="Turn off to keep the catalogue browsable but disable checkout."),
			field("sb_brand", "Brand & Hero", "Section Break"),
			field("hero_title_en", "Hero Title (English)", "Data"),
			field("hero_title_ar", "Hero Title (العربية)", "Data"),
			field("hero_subtitle_en", "Hero Subtitle (English)", "Small Text"),
			field("hero_subtitle_ar", "Hero Subtitle (العربية)", "Small Text"),
			field("cb_brand", fieldtype="Column Break"),
			field("hero_image", "Hero Image", "Attach Image"),
			field("announcement_en", "Announcement Bar (English)", "Data"),
			field("announcement_ar", "Announcement Bar (العربية)", "Data"),
			field("sb_contact", "Contact Details", "Section Break"),
			field("phone", "Phone", "Data"),
			field("whatsapp", "WhatsApp Number", "Data",
			      description="International format without +, e.g. 9647701234567"),
			field("email", "Email", "Data"),
			field("cb_contact", fieldtype="Column Break"),
			field("instagram", "Instagram URL", "Data"),
			field("address_en", "Address (English)", "Small Text"),
			field("address_ar", "Address (العربية)", "Small Text"),
			field("working_hours", "Working Hours", "Data"),
			field("sb_seo", "SEO", "Section Break"),
			field("meta_title_en", "Meta Title (English)", "Data"),
			field("meta_title_ar", "Meta Title (العربية)", "Data"),
			field("cb_seo", fieldtype="Column Break"),
			field("meta_description_en", "Meta Description (English)", "Small Text"),
			field("meta_description_ar", "Meta Description (العربية)", "Small Text"),
			field("og_image", "Share Image", "Attach Image",
			      description="Shown when a link is pasted into Instagram or WhatsApp. 1200×630."),
		],
		issingle=1,
	),
	# ------------------------------------------------------- design request
	doctype(
		"Narjes Design Request File",
		[
			field("file_url", "File", "Attach", in_list_view=1, columns=6, reqd=1),
			field("caption", "Caption", "Data", in_list_view=1, columns=4),
		],
		istable=1,
	),
	doctype(
		"Narjes Design Request",
		[
			field("naming_series", "Series", "Select", options="NJ-DR-.YYYY.-", default="NJ-DR-.YYYY.-",
			      reqd=1, hidden=1),
			field("customer_name", "Customer Name", "Data", reqd=1, in_list_view=1, in_standard_filter=1),
			field("phone", "Phone", "Data", reqd=1, in_list_view=1),
			field("governorate", "Governorate", "Data", in_standard_filter=1),
			field("cb_1", fieldtype="Column Break"),
			field("status", "Status", "Select",
			      options="\n".join(["New", "In Review", "Quoted", "Converted", "Declined"]),
			      default="New", in_list_view=1, in_standard_filter=1, reqd=1),
			field("occasion", "Occasion", "Select",
			      options="\n".join(["", "Graduation", "Wedding", "Hajj", "Birthday", "Other"]),
			      in_standard_filter=1),
			field("design_type", "Design Type", "Select",
			      options="\n".join(["", "Canvas", "MDF", "Frame", "Flowers", "Gift", "Other"])),
			field("sb_detail", "Details", "Section Break"),
			field("size_note", "Size / Dimensions", "Data"),
			field("notes", "Notes", "Text"),
			field("attachments", "Reference Images", "Table", options="Narjes Design Request File"),
			field("sb_link", "Linked Records", "Section Break"),
			field("customer", "Customer", "Link", options="Customer", read_only=1),
			field("cb_2", fieldtype="Column Break"),
			field("sales_order", "Sales Order", "Link", options="Sales Order", read_only=1),
			field("amended_from", "Amended From", "Link", options="Narjes Design Request",
			      read_only=1, no_copy=1, print_hide=1),
		],
		title_field="customer_name",
		autoname="naming_series:",
		search_fields="phone,status",
		sort_field="creation",
	),
]

CONTROLLER = '''"""Auto-scaffolded by scripts/scaffold_storefront_doctypes.py (plan W2)."""

from frappe.model.document import Document


class {cls}(Document):
	pass
'''


def main():
	for doc in DOCTYPES:
		slug = doc["name"].lower().replace(" ", "_")
		folder = ROOT / slug
		folder.mkdir(parents=True, exist_ok=True)
		(folder / "__init__.py").write_text("")
		(folder / f"{slug}.json").write_text(json.dumps(doc, indent=1) + "\n")
		controller = folder / f"{slug}.py"
		if not controller.exists():
			cls = doc["name"].replace(" ", "")
			controller.write_text(CONTROLLER.format(cls=cls))
		print(f"  {doc['name']}")


if __name__ == "__main__":
	main()
