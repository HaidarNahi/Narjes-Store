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
        },
        {
            "fieldname": "selling_uom",
            "label": _("Selling UoM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 120
        },
        {
            "fieldname": "selling_rate",
            "label": _("Selling Rate / Unit"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "purchase_uom",
            "label": _("Purchase UoM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 120
        },
        {
            "fieldname": "purchase_rate",
            "label": _("Purchase Price / Unit"),
            "fieldtype": "Currency",
            "width": 160
        }
    ]


def get_data():
    row_items = frappe.get_all(
        "Item",
        filters={"custom_is_row": 1, "disabled": 0},
        fields=["name", "item_name", "stock_uom", "sales_uom", "purchase_uom",
                "standard_rate", "last_purchase_rate"],
        order_by="item_name asc",
    )
    if not row_items:
        return []

    item_codes = [item.name for item in row_items]

    # One grouped query for balances instead of one per item.
    balances = {
        r.item_code: float(r.balance or 0)
        for r in frappe.db.sql(
            """
            SELECT item_code, COALESCE(SUM(actual_qty), 0) AS balance
            FROM `tabBin`
            WHERE item_code IN %(item_codes)s
            GROUP BY item_code
            """,
            {"item_codes": item_codes},
            as_dict=True,
        )
    }

    prices = get_item_prices(item_codes)

    data = []
    for item in row_items:
        balance = balances.get(item.name, 0.0)
        price = prices.get(item.name, {})

        data.append({
            "item_code": item.name,
            "item_name": item.item_name or item.name,
            "balance": balance,
            "stock_uom": item.stock_uom,
            # UOM falls back to the stock UOM: an item with no dedicated
            # selling/buying UOM is transacted in its stock UOM, so showing
            # that is accurate rather than leaving the cell blank.
            "selling_uom": price.get("selling_uom") or item.sales_uom or item.stock_uom,
            "selling_rate": price.get("selling_rate") or item.standard_rate or 0,
            "purchase_uom": price.get("purchase_uom") or item.purchase_uom or item.stock_uom,
            "purchase_rate": price.get("purchase_rate") or item.last_purchase_rate or 0,
            "is_low_balance": is_low_balance(balance, item.stock_uom),
        })

    return data


def get_item_prices(item_codes):
    """Per-item selling/buying rate and the UOM each is quoted in, read from
    Item Price — the record that actually drives what is charged and paid.

    Item Price is per (item, price list, UOM), so the UOM shown next to a rate
    is the one that rate is quoted in; quoting a price without its UOM is
    meaningless for items bought by the centimetre and sold by the piece.
    Later `valid_from` wins, so a current price supersedes an older one.
    """
    if not item_codes:
        return {}

    lists = frappe.db.get_all("Price List", filters={"enabled": 1},
                              fields=["name", "selling", "buying"])
    selling_lists = [pl.name for pl in lists if pl.selling]
    buying_lists = [pl.name for pl in lists if pl.buying]
    if not (selling_lists or buying_lists):
        return {}

    prices = {}
    for row in frappe.db.get_all(
        "Item Price",
        filters={
            "item_code": ["in", item_codes],
            "price_list": ["in", list(set(selling_lists + buying_lists))],
        },
        fields=["item_code", "price_list", "price_list_rate", "uom", "valid_from"],
        order_by="valid_from asc, modified asc",
    ):
        entry = prices.setdefault(row.item_code, {})
        if row.price_list in selling_lists:
            entry["selling_rate"] = row.price_list_rate or 0
            entry["selling_uom"] = row.uom
        if row.price_list in buying_lists:
            entry["purchase_rate"] = row.price_list_rate or 0
            entry["purchase_uom"] = row.uom

    return prices


def is_low_balance(balance, stock_uom):
    uom = (stock_uom or "").strip().lower()
    if "centimeter" in uom or uom == "cm":
        threshold = LOW_BALANCE_THRESHOLD_CENTIMETER
    else:
        threshold = LOW_BALANCE_THRESHOLD_NOS
    return balance <= threshold
