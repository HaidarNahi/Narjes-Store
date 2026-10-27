# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

"""Confirmed intakes whose order went to a customer who doesn't own the
order's phone.

Before intake v2, customers were also matched by name, and some orders
landed on a customer with the same or a similar name but a different phone
— so the delivery could go out with the wrong number and address. This
reads each confirmed message's phone again (from the order form, no AI) and
lists the orders whose customer owns none of those numbers, for staff to
check one by one. Nothing is changed automatically.
"""

import frappe
from frappe import _

from narjes_custom.ai_intake import template
from narjes_custom.customer_phones import customer_keys
from narjes_custom.phones import display

DOCSTATUS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}


def execute(filters=None):
    filters = filters or {}
    columns = [
        {"label": _("Intake"), "fieldname": "intake", "fieldtype": "Link", "options": "AI Order Intake", "width": 170},
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 150},
        {"label": _("Order Status"), "fieldname": "order_status", "fieldtype": "Data", "width": 100},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 170},
        {"label": _("Phone in Message"), "fieldname": "message_phones", "fieldtype": "Data", "width": 170},
        {"label": _("Customer's Phones"), "fieldname": "customer_phones", "fieldtype": "Data", "width": 170},
        {"label": _("Phone Source"), "fieldname": "phone_source", "fieldtype": "Data", "width": 110},
        {"label": _("Override Reason"), "fieldname": "override_reason", "fieldtype": "Data", "width": 200},
        {"label": _("Created"), "fieldname": "created", "fieldtype": "Date", "width": 100},
    ]

    intake_filters = {"status": "Confirmed", "created_sales_order": ["is", "set"]}
    if filters.get("from_date"):
        intake_filters["creation"] = [">=", filters["from_date"]]
    intakes = frappe.get_all(
        "AI Order Intake",
        filters=intake_filters,
        fields=["name", "raw_text", "created_sales_order", "creation", "phone_source", "phone_override_reason"],
        order_by="creation asc",
    )
    if not intakes:
        return columns, []

    orders = {
        so.name: so
        for so in frappe.get_all(
            "Sales Order",
            filters={"name": ["in", [i.created_sales_order for i in intakes]]},
            fields=["name", "customer", "docstatus"],
        )
    }
    customers = {
        c.name: c
        for c in frappe.get_all(
            "Customer",
            filters={"name": ["in", list({so.customer for so in orders.values()})]},
            fields=["name", "main_phone_number", "secondary_phone_number"],
        )
    }

    rows = []
    for intake in intakes:
        so = orders.get(intake.created_sales_order)
        if not so or (filters.get("hide_cancelled", 1) and so.docstatus == 2):
            continue
        message_keys = template.parse(intake.raw_text or "").phone_keys
        if not message_keys:
            continue  # nothing to compare against
        customer = customers.get(so.customer)
        owned = [k for k in customer_keys(customer) if k] if customer else []
        if set(message_keys) & set(owned):
            continue
        rows.append({
            "intake": intake.name,
            "sales_order": so.name,
            "order_status": DOCSTATUS.get(so.docstatus, ""),
            "customer": so.customer,
            "message_phones": ", ".join(display(k) for k in message_keys),
            "customer_phones": ", ".join(display(k) for k in owned) or "—",
            # "reviewer" = the phone was deliberately corrected at review
            "phone_source": intake.phone_source or "",
            "override_reason": intake.phone_override_reason or "",
            "created": intake.creation.date() if intake.creation else None,
        })
    return columns, rows
