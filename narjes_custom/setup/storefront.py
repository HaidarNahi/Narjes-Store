"""Storefront custom fields on stock doctypes (storefront plan W2).

Follows the same pattern as setup/custom_fields.py: everything is declared
once here, applied idempotently, and re-run on every migrate so a fresh site
converges without anyone remembering a manual step.

Run via: bench execute narjes_custom.setup.storefront.run
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# The label the shop asked for on website-placed orders. Stored as a Select so
# it is filterable in the Kanban and groupable in the Sales Revenue Report —
# a free-text tag would be neither.
ORDER_SOURCE_OPTIONS = "\n".join(
	["", "From the Website", "Instagram", "WhatsApp", "Phone", "Walk-in", "AI Intake"]
)

CUSTOM_FIELDS = {
	"Item": [
		{
			"fieldname": "custom_storefront_section",
			"label": "Storefront",
			"fieldtype": "Section Break",
			"insert_after": "description",
			"collapsible": 0,
		},
		{
			"fieldname": "custom_publish_on_website",
			"label": "on Storefront",
			"fieldtype": "Check",
			"insert_after": "custom_storefront_section",
			"description": "Show this item in the public store at narjes.store.",
		},
		{
			"fieldname": "custom_storefront_category",
			"label": "Storefront Category",
			"fieldtype": "Link",
			"options": "Narjes Storefront Category",
			"insert_after": "custom_publish_on_website",
			"depends_on": "eval:doc.custom_publish_on_website",
		},
		{
			"fieldname": "custom_web_badge",
			"label": "Website Badge",
			"fieldtype": "Select",
			"options": "\n".join(["", "New", "Best Seller", "Limited", "Sale"]),
			"insert_after": "custom_storefront_category",
			"depends_on": "eval:doc.custom_publish_on_website",
		},
		{
			"fieldname": "custom_is_featured",
			"label": "Featured on Home",
			"fieldtype": "Check",
			"insert_after": "custom_web_badge",
			"depends_on": "eval:doc.custom_publish_on_website",
		},
		{
			"fieldname": "custom_storefront_cb1",
			"fieldtype": "Column Break",
			"insert_after": "custom_is_featured",
		},
		{
			"fieldname": "custom_made_to_order",
			"label": "Made to Order",
			"fieldtype": "Check",
			"insert_after": "custom_storefront_cb1",
			"description": "Sells on the website without stock on hand.",
			"depends_on": "eval:doc.custom_publish_on_website",
		},
		{
			"fieldname": "custom_lead_time_days",
			"label": "Lead Time (days)",
			"fieldtype": "Int",
			"insert_after": "custom_made_to_order",
			"depends_on": "eval:doc.custom_made_to_order",
		},
		{
			"fieldname": "custom_display_order",
			"label": "Display Order",
			"fieldtype": "Int",
			"insert_after": "custom_lead_time_days",
			"description": "Lower numbers appear first. 0 = unsorted.",
			"depends_on": "eval:doc.custom_publish_on_website",
		},
		{
			"fieldname": "custom_web_route",
			"label": "Website Slug",
			"fieldtype": "Data",
			"insert_after": "custom_display_order",
			"description": "Leave blank to generate from the item name.",
			"depends_on": "eval:doc.custom_publish_on_website",
		},
		{
			"fieldname": "custom_web_content_section",
			"label": "Website Content",
			"fieldtype": "Section Break",
			"insert_after": "custom_gallery",
			"collapsible": 1,
			"depends_on": "eval:doc.custom_publish_on_website",
		},
		{
			"fieldname": "custom_web_title_ar",
			"label": "Title (العربية)",
			"fieldtype": "Data",
			"insert_after": "custom_web_content_section",
		},
		{
			"fieldname": "custom_web_short_ar",
			"label": "Short Description (العربية)",
			"fieldtype": "Small Text",
			"insert_after": "custom_web_title_ar",
		},
		{
			"fieldname": "custom_web_long_ar",
			"label": "Full Description (العربية)",
			"fieldtype": "Text Editor",
			"insert_after": "custom_web_short_ar",
		},
		{
			"fieldname": "custom_web_content_cb",
			"fieldtype": "Column Break",
			"insert_after": "custom_web_long_ar",
		},
		{
			"fieldname": "custom_web_title_en",
			"label": "Title (English)",
			"fieldtype": "Data",
			"insert_after": "custom_web_content_cb",
		},
		{
			"fieldname": "custom_web_short_en",
			"label": "Short Description (English)",
			"fieldtype": "Small Text",
			"insert_after": "custom_web_title_en",
		},
		{
			"fieldname": "custom_web_long_en",
			"label": "Full Description (English)",
			"fieldtype": "Text Editor",
			"insert_after": "custom_web_short_en",
		},
		{
			"fieldname": "custom_gallery_section",
			"label": "Website Gallery",
			"fieldtype": "Section Break",
			"insert_after": "custom_web_route",
			"collapsible": 0,
			"depends_on": "eval:doc.custom_publish_on_website",
		},
		{
			"fieldname": "custom_gallery",
			"label": "Gallery",
			"fieldtype": "Table",
			"options": "Narjes Product Media",
			"insert_after": "custom_gallery_section",
			"description": "Extra photos for the product page. The item's own Image is always shown first, then these in order.",
		},
	],
	"Sales Order": [
		{
			"fieldname": "custom_order_source",
			"label": "Order Source",
			"fieldtype": "Select",
			"options": ORDER_SOURCE_OPTIONS,
			"insert_after": "customer_name",
			"in_standard_filter": 1,
			"read_only": 1,
			"allow_on_submit": 1,
			"description": "Where this order came from. Set automatically for website orders.",
		},
		{
			"fieldname": "custom_web_order_ref",
			"label": "Website Order Reference",
			"fieldtype": "Data",
			"insert_after": "custom_order_source",
			"read_only": 1,
			"allow_on_submit": 1,
			"depends_on": "eval:doc.custom_web_order_ref",
		},
	],
}


def run():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	_extend_customer_channel()
	frappe.db.commit()
	print("Storefront custom fields applied (Item, Sales Order, Customer.channal)")


def _extend_customer_channel():
	"""Add 'Website' to Customer.channal so customers created by the storefront
	are distinguishable from walk-ins. Appends rather than overwrites, so any
	options the shop added by hand survive."""
	name = frappe.db.get_value("Custom Field", {"dt": "Customer", "fieldname": "channal"})
	if not name:
		return
	field = frappe.get_doc("Custom Field", name)
	options = [o.strip() for o in (field.options or "").split("\n")]
	if "Website" in options:
		return
	options.append("Website")
	field.options = "\n".join(options)
	field.save(ignore_permissions=True)
