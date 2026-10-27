# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

"""Customer phones that get in the way of matching orders by phone.

AI Order Intake decides the customer by phone number alone, so every
customer should have a valid number that no other customer has. New saves
already enforce that; this lists the older records that don't, for staff to
fix: an invalid number, a number shared with another customer, the same
number twice on one customer, or no number at all.
"""

import frappe
from frappe import _

from narjes_custom.phones import canonical, display

PROBLEM_ORDER = ("Shared with another customer", "Invalid phone", "Main = secondary", "No phone")


def execute(filters=None):
    columns = [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": _("Problem"), "fieldname": "problem", "fieldtype": "Data", "width": 200},
        {"label": _("Field"), "fieldname": "field", "fieldtype": "Data", "width": 130},
        {"label": _("Stored Value"), "fieldname": "stored", "fieldtype": "Data", "width": 160},
        {"label": _("Read As"), "fieldname": "read_as", "fieldtype": "Data", "width": 130},
        {"label": _("Other Customers"), "fieldname": "others", "fieldtype": "Data", "width": 220},
    ]

    customers = frappe.get_all(
        "Customer",
        filters={"disabled": 0},
        fields=["name", "customer_name", "main_phone_number", "secondary_phone_number"],
        order_by="name asc",
    )

    owners = {}
    keyed = []
    for c in customers:
        main = canonical(c.main_phone_number) if c.main_phone_number else None
        secondary = canonical(c.secondary_phone_number) if c.secondary_phone_number else None
        keyed.append((c, main, secondary))
        for key in {k for k in (main, secondary) if k}:
            owners.setdefault(key, []).append(c.name)

    rows = []
    for c, main, secondary in keyed:
        base = {"customer": c.name, "customer_name": c.customer_name}
        if not c.main_phone_number and not c.secondary_phone_number:
            rows.append({**base, "problem": "No phone"})
            continue
        for field, raw, key in (("Main", c.main_phone_number, main), ("Secondary", c.secondary_phone_number, secondary)):
            if not raw:
                continue
            if not key:
                rows.append({**base, "problem": "Invalid phone", "field": field, "stored": raw})
                continue
            others = [n for n in owners.get(key, []) if n != c.name]
            if others:
                rows.append({**base, "problem": "Shared with another customer", "field": field, "stored": raw,
                             "read_as": display(key), "others": ", ".join(others)})
        if main and main == secondary:
            rows.append({**base, "problem": "Main = secondary", "field": "Secondary",
                         "stored": c.secondary_phone_number, "read_as": display(main)})

    if filters and filters.get("problem"):
        rows = [r for r in rows if r["problem"] == filters["problem"]]
    rows.sort(key=lambda r: (PROBLEM_ORDER.index(r["problem"]), r["customer"]))
    return columns, rows
