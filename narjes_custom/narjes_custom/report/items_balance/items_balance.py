# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

import frappe
from frappe import _

# Minimum balance thresholds — a row is highlighted red once its balance
# drops to or below the threshold matching the item's stock UOM.
LOW_BALANCE_THRESHOLD_NOS = 15
LOW_BALANCE_THRESHOLD_CENTIMETER = 2500


def execute(filters=None):
    columns = get_columns()
    data = get_data()
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 320
        },
        {
            "fieldname": "balance",
            "label": _("Balance"),
            "fieldtype": "Float",
            "precision": 3,
            "width": 150
        }
    ]


def get_data():
    row_items = frappe.get_all(
        "Item",
        filters={"custom_is_row": 1, "disabled": 0},
        fields=["name", "item_name", "stock_uom"],
        order_by="item_name asc",
    )

    data = []
    for item in row_items:
        balance = frappe.db.sql(
            """
            SELECT COALESCE(SUM(actual_qty), 0)
            FROM `tabBin`
            WHERE item_code = %s
            """,
            item.name,
        )[0][0] or 0.0
        balance = float(balance)

        data.append({
            "item_code": item.name,
            "item_name": item.item_name or item.name,
            "balance": balance,
            "stock_uom": item.stock_uom,
            "is_low_balance": is_low_balance(balance, item.stock_uom),
        })

    return data


def is_low_balance(balance, stock_uom):
    uom = (stock_uom or "").strip().lower()
    if "centimeter" in uom or uom == "cm":
        threshold = LOW_BALANCE_THRESHOLD_CENTIMETER
    else:
        threshold = LOW_BALANCE_THRESHOLD_NOS
    return balance <= threshold
