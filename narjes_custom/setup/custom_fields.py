"""
narjes_custom.setup.custom_fields
==================================
Single source of truth for every Custom Field this app depends on.

History note (see NARJES_STORE_SYSTEM.md §14.1): most of these fields used to
be hand-edited directly into ERPNext's own core doctype JSON files
(erpnext/selling/doctype/sales_order/sales_order.json, customer.json,
item.json), which is exactly what a separate custom app is supposed to
prevent — those edits were invisible to git, could be silently wiped by any
`bench update`, and could not travel to a fresh site. A smaller set already
existed as proper Custom Field records, created by half a dozen different
one-off scripts scattered across the app (setup_flowers.py, setup_painting.py,
setup_sheet_painting.py, setup_so_painting.py, setup_row_items.py,
create_custom_fields.py, create_fields.py). This module replaces all of that:
every custom field on a standard doctype is defined here, once, and this is
also what `hooks.py`'s `fixtures` entry exports, so the schema now travels
with the app in git and is reproducible on a fresh site.

Run via: bench --site <site> execute narjes_custom.setup.custom_fields.run
Idempotent — safe to run repeatedly (create_custom_fields only creates what's
missing and updates changed properties on what already exists).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# Iraq's 18 governorates — the canonical value list for every governorate
# field in the app (Customer.governorate, Sales Order.governorate_of_delivery).
# Keeping this in one place is what makes §14.6's fix real: a governorate can
# no longer be free text that silently drifts from what the delivery-fee
# logic checks against.
IRAQ_GOVERNORATES = [
    "بغداد", "بابل", "واسط", "ديالى", "الديوانية", "كربلاء", "النجف",
    "ذي قار", "ميسان", "المثنى", "البصرة", "الانبار", "صلاح الدين",
    "كركوك", "نينوى", "اربيل", "سليمانية", "دهوك",
]
GOVERNORATE_OPTIONS = "\n".join(IRAQ_GOVERNORATES)


CUSTOM_FIELDS = {
    "Customer": [
        {
            "fieldname": "main_phone_number",
            "fieldtype": "Data",
            "label": "Main Phone Number",
            "insert_after": "customer_primary_contact",
            "allow_in_quick_entry": 1,
        },
        {
            "fieldname": "secondary_phone_number",
            "fieldtype": "Data",
            "label": "Secondary Phone Number",
            "insert_after": "main_phone_number",
            "allow_in_quick_entry": 1,
        },
        {
            # Fieldname kept as "channal" (not "channel") even though it's a
            # typo: nothing in code reads this field, but production may
            # already hold data under this exact column name, and silently
            # renaming it would orphan that data without a real migration.
            "fieldname": "channal",
            "fieldtype": "Select",
            "label": "Channel",
            "options": "Instagram\nFacebook\nWhatsapp\nTelegram",
            "insert_after": "secondary_phone_number",
            "allow_in_quick_entry": 1,
        },
        {
            "fieldname": "username",
            "fieldtype": "Data",
            "label": "Username",
            "description": "Social media username or alias.",
            "insert_after": "channal",
            "allow_in_quick_entry": 1,
        },
        {
            "fieldname": "governorate",
            "fieldtype": "Select",
            "label": "Governorate",
            "options": GOVERNORATE_OPTIONS,
            "insert_after": "username",
            "allow_in_quick_entry": 1,
        },
        {
            "fieldname": "full_address",
            "fieldtype": "Data",
            "label": "Full Address",
            "insert_after": "governorate",
            "allow_in_quick_entry": 1,
        },
    ],
    "Item": [
        {
            "fieldname": "custom_is_canvas",
            "fieldtype": "Check",
            "label": "Is Canvas",
            "insert_after": "item_group",
            "description": "Check this if the item is a canvas that requires painting (priced by area — see custom_area).",
        },
        {
            "fieldname": "custom_area",
            "fieldtype": "Int",
            "label": "Canvas Area (cm²)",
            "insert_after": "custom_is_canvas",
            "depends_on": "eval:doc.custom_is_canvas==1",
            "description": "The area of the canvas in cm². Drives canvas painting cost = area × qty × Narjes Settings.painting_rate_per_cm.",
        },
        {
            "fieldname": "custom_is_sheet",
            "fieldtype": "Check",
            "label": "Is Sheet",
            "insert_after": "custom_area",
            "description": "Check this if the item is a sheet, priced flat per unit rather than by area. Cannot be checked together with 'Is Canvas' (enforced in item_validate).",
        },
        {
            "fieldname": "custom_is_flower",
            "fieldtype": "Check",
            "label": "Is Flower",
            "insert_after": "custom_is_sheet",
            "description": "Check this if the item is a flower/gift line. Flower items are kept out of the standard Sales Order Items table and tracked in the Flower Item child table instead.",
        },
        {
            "fieldname": "custom_is_row",
            "fieldtype": "Check",
            "label": "Is Row Item",
            "insert_after": "custom_is_flower",
            "description": "Check this if the item is tracked on the Items Balance report (stock sold/measured by roll — Nos or Centimeter).",
        },
    ],
    "Sales Order": [
        # --- Order intake meta-data ---
        {
            "fieldname": "governorate_of_delivery",
            "fieldtype": "Select",
            "label": "Governorate of Delivery",
            "options": GOVERNORATE_OPTIONS,
            "fetch_from": "customer.governorate",
            "hidden": 1,
            "read_only": 1,
            "insert_after": "customer_name",
            "description": "Drives the delivery fee (see Narjes Settings). A controlled Select, not free text, so it can never silently drift from the values the delivery-fee lookup checks against.",
        },
        {
            "fieldname": "design_type",
            "fieldtype": "Select",
            "label": "Design Type",
            "options": "\nحج\nتخرج\nاعراس",
            "insert_after": "governorate_of_delivery",
        },
        {
            "fieldname": "gift",
            "fieldtype": "Check",
            "label": "Gift",
            "default": "0",
            "insert_after": "design_type",
        },
        {
            "fieldname": "username",
            "fieldtype": "Data",
            "label": "Username",
            "fetch_from": "customer.username",
            "hidden": 1,
            "read_only": 1,
            "insert_after": "gift",
        },
        {
            "fieldname": "delivery_id",
            "fieldtype": "Data",
            "label": "Delivery ID",
            "insert_after": "delivery_date",
        },
        # --- Kanban / order-phase tracking ---
        {
            "fieldname": "order_phase",
            "fieldtype": "Select",
            "label": "Order Phase",
            "options": "New\nIn Design\nWaiting Approval\nReady to Execution\nExecution\nWaiting\nIn Delivery\nDone\nCancelled\nReturned",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "allow_on_submit": 1,
            "insert_after": "status",
        },
        {
            "fieldname": "priority",
            "fieldtype": "Select",
            "label": "Priority",
            "options": "\nHigh\nMedium\nLow",
            "insert_after": "order_phase",
        },
        {
            "fieldname": "has_flower",
            "fieldtype": "Check",
            "label": "Has Flower",
            "hidden": 1,
            "insert_after": "priority",
        },
        {
            "fieldname": "has_stand",
            "fieldtype": "Check",
            "label": "Has Stand",
            "hidden": 1,
            "insert_after": "has_flower",
        },
        # --- Flower Items (kept out of the standard items table) ---
        {
            "fieldname": "custom_flower_section",
            "fieldtype": "Section Break",
            "label": "Flower Items",
            "insert_after": "items",
            "collapsible": 0,
        },
        {
            "fieldname": "custom_flower_items",
            "fieldtype": "Table",
            "options": "Flower Item",
            "label": "Flower Items",
            "insert_after": "custom_flower_section",
        },
        {
            "fieldname": "custom_flower_total",
            "fieldtype": "Currency",
            "label": "Flower Items Total",
            "read_only": 1,
            "insert_after": "custom_flower_items",
        },
        {
            "fieldname": "custom_details",
            "fieldtype": "Small Text",
            "label": "Custom Details",
            "insert_after": "custom_flower_total",
        },
        # --- Painting costs (canvas + sheet), auto-calculated ---
        {
            "fieldname": "custom_painting_section",
            "fieldtype": "Section Break",
            "label": "Painting Costs (Auto Calculated)",
            "insert_after": "taxes_and_charges",
        },
        {
            "fieldname": "custom_painting_items",
            "fieldtype": "Table",
            "options": "Painting Cost Item",
            "label": "Canvas Items",
            "read_only": 1,
            "insert_after": "custom_painting_section",
        },
        {
            "fieldname": "custom_total_canvas_area",
            "fieldtype": "Int",
            "label": "Total Canvas Area (cm²)",
            "read_only": 1,
            "insert_after": "custom_painting_items",
        },
        {
            "fieldname": "custom_canvas_painting_cost",
            "fieldtype": "Currency",
            "label": "Canvas Painting Cost",
            "read_only": 1,
            "insert_after": "custom_total_canvas_area",
        },
        {
            "fieldname": "custom_sheet_items",
            "fieldtype": "Table",
            "options": "Painting Sheet Item",
            "label": "Sheet Items",
            "read_only": 1,
            "insert_after": "custom_canvas_painting_cost",
        },
        {
            "fieldname": "custom_sheet_painting_cost",
            "fieldtype": "Currency",
            "label": "Sheet Painting Cost",
            "read_only": 1,
            "insert_after": "custom_sheet_items",
        },
        {
            "fieldname": "custom_total_painting_cost",
            "fieldtype": "Currency",
            "label": "Total Painting Cost",
            "read_only": 1,
            "insert_after": "custom_sheet_painting_cost",
        },
        # --- Totals / fees ---
        {
            "fieldname": "delivery_fees",
            "fieldtype": "Currency",
            "label": "Delivery Fees",
            "read_only": 1,
            "insert_after": "total",
        },
        {
            "fieldname": "total_with_delivery_fees",
            "fieldtype": "Currency",
            "label": "Total with Delivery Fees",
            "read_only": 1,
            "insert_after": "delivery_fees",
        },
        {
            # No static "default" here on purpose: the live default now comes
            # from Narjes Settings.default_packaging_cost, applied in
            # sales_order_before_validate the same way the delivery fee is
            # (see §14.5) — a static field default would just be one more
            # place this number could silently drift from Settings.
            "fieldname": "packaging_costs",
            "fieldtype": "Currency",
            "label": "Packaging Costs (IQD)",
            "options": "currency",
            "bold": 1,
            "description": "Packaging costs added to the order total. Defaults from Narjes Settings if left blank.",
            "insert_after": "total_with_delivery_fees",
        },
        # --- "Customer" tab: this order's customer, in full, read-only ---
        # Rendered from the live Customer record by sales_order.js rather than
        # mirrored into ~44 fetch_from columns on tabSales Order. That keeps
        # the schema (and every Sales Order row) from carrying a duplicate of
        # the customer master, means the tab can never show a stale copy, and
        # picks up new Customer fields automatically. If a specific value is
        # ever needed in a print format or report, add that ONE field as a
        # normal fetch_from custom field here.
        {
            # Anchored to the last field of the Details tab (`pricing_rules`,
            # immediately before ERPNext's `contact_info` tab break), so this
            # lands as the SECOND tab — right next to Details.
            "fieldname": "custom_customer_tab",
            "fieldtype": "Tab Break",
            "label": "Customer",
            "insert_after": "pricing_rules",
        },
        {
            "fieldname": "custom_customer_info_html",
            "fieldtype": "HTML",
            "label": "Customer Information",
            "insert_after": "custom_customer_tab",
        },
    ],
    "Purchase Order": [
        {
            # Already correctly created by earlier work — listed here too so
            # this module is genuinely the single source of truth for every
            # custom field in the app, not "everything except this one".
            "fieldname": "transportation_charges",
            "fieldtype": "Currency",
            "label": "Transportation Charges",
            "options": "currency",
            "insert_after": "total_taxes_and_charges",
        },
    ],
}


def run():
    """Idempotently create/update every custom field this app needs."""
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
    frappe.db.commit()
    print(f"Synced {sum(len(v) for v in CUSTOM_FIELDS.values())} custom field(s) "
          f"across {len(CUSTOM_FIELDS)} doctype(s).")


if __name__ == "__main__":
    run()
