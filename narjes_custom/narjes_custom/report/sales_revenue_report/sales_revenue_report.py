# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from narjes_custom.business_logic import compute_profit, compute_profit_percentage


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "sales_order",
            "label": _("Sales Order"),
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 160
        },
        {
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150
        },
        {
            "fieldname": "governorate",
            "label": _("Governorate"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "discount_value",
            "label": _("Discount"),
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "fieldname": "delivery_fees",
            "label": _("Delivery Fees"),
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "fieldname": "selling_rate",
            "label": _("Selling Rate"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            # Broken out because it is the part of Selling Rate that comes
            # from the Flower Items table rather than from Items — the two
            # used to be impossible to tell apart in this report.
            "fieldname": "flower_sales",
            "label": _("of which Flowers"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "buying_rate",
            "label": _("Buying Rate"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "packaging_and_painting",
            "label": _("Packaging + Painting"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "profit",
            "label": _("Profit"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "profit_percentage",
            "label": _("Profit %"),
            "fieldtype": "Percent",
            "width": 90
        },
        {
            "fieldname": "items_detail",
            "label": _("Items"),
            "fieldtype": "Data",
            "width": 80
        }
    ]


def get_data(filters):
    conditions = get_conditions(filters)

    orders = frappe.db.sql("""
        SELECT
            so.name AS sales_order,
            so.customer,
            so.governorate_of_delivery AS governorate,
            so.transaction_date AS date,
            so.discount_amount AS discount_value,
            so.delivery_fees,
            so.grand_total,
            so.packaging_costs,
            so.custom_total_painting_cost
        FROM `tabSales Order` so
        WHERE so.docstatus = 1
        {conditions}
        ORDER BY so.transaction_date DESC
    """.format(conditions=conditions), filters, as_dict=True)

    # Buying Rate = sum of (valuation_rate * qty) for all items in each SO.
    # Batched into a single grouped query instead of one query per order —
    # the previous per-row query doesn't cause wrong results, just an
    # avoidable N+1 round trip that scales with how many orders are in the
    # filtered date range (see NARJES_STORE_SYSTEM.md §5.2).
    order_names = [row.sales_order for row in orders]
    buying_rates = {}
    flower_costs = {}
    flower_sales = {}
    if order_names:
        buying_rows = frappe.db.sql("""
            SELECT soi.parent, IFNULL(SUM(soi.valuation_rate * soi.qty), 0) AS total_buying
            FROM `tabSales Order Item` soi
            WHERE soi.parent IN %(order_names)s
            GROUP BY soi.parent
        """, {"order_names": order_names}, as_dict=True)
        buying_rates = {r.parent: r.total_buying for r in buying_rows}

        # Flowers live in their own child table, so they are absent from
        # `tabSales Order Item` entirely. Their revenue reaches this report
        # through grand_total, but their COST did not — every flower sold was
        # counted as pure profit. Cost them the same way stock items are.
        flower_rows = frappe.db.sql("""
            SELECT parent, flower_item, IFNULL(SUM(qty), 0) AS qty,
                   IFNULL(SUM(amount), 0) AS amount
            FROM `tabFlower Item`
            WHERE parent IN %(order_names)s AND parenttype = 'Sales Order'
            GROUP BY parent, flower_item
        """, {"order_names": order_names}, as_dict=True)

        unit_costs = get_item_unit_costs({r.flower_item for r in flower_rows if r.flower_item})
        for r in flower_rows:
            flower_costs[r.parent] = flower_costs.get(r.parent, 0) + unit_costs.get(r.flower_item, 0) * (r.qty or 0)
            flower_sales[r.parent] = flower_sales.get(r.parent, 0) + (r.amount or 0)

    data = []
    for row in orders:
        # Selling Rate = Grand Total.
        #
        # The subtraction that used to be here is gone because the fee is no
        # longer inside grand_total: delivery is display-only now, collected
        # and kept by the courier, so grand_total is already purely the shop's
        # own revenue. Subtracting again would have understated every order by
        # its delivery fee. The column is still shown, for reference.
        delivery_fees = row.delivery_fees or 0
        selling_rate = row.grand_total or 0

        buying_rate = buying_rates.get(row.sales_order, 0) + flower_costs.get(row.sales_order, 0)

        # Packaging + Painting costs
        packaging_costs = row.packaging_costs or 0
        painting_costs = row.custom_total_painting_cost or 0
        packaging_and_painting = packaging_costs + painting_costs

        profit = compute_profit(selling_rate, buying_rate, packaging_and_painting)
        profit_percentage = compute_profit_percentage(profit, selling_rate)

        data.append({
            "sales_order": row.sales_order,
            "customer": row.customer,
            "governorate": row.governorate,
            "date": row.date,
            "discount_value": row.discount_value,
            "delivery_fees": delivery_fees,
            "selling_rate": selling_rate,
            "buying_rate": buying_rate,
            "packaging_and_painting": packaging_and_painting,
            "flower_sales": flower_sales.get(row.sales_order, 0),
            "profit": profit,
            "profit_percentage": profit_percentage,
            "items_detail": row.sales_order
        })

    return data


def get_item_unit_costs(item_codes):
    """Best available unit cost per item, in order of reliability:
    stock valuation, then the buying price list, then the last purchase rate.

    Flower items are typically bought per order and often carry no stock
    valuation, which is why the price-list fallback matters — without it their
    cost reads as 0 and the whole flower amount is booked as profit.
    """
    item_codes = {code for code in (item_codes or []) if code}
    if not item_codes:
        return {}

    costs = {}
    for item in frappe.db.get_all(
        "Item",
        filters={"name": ["in", list(item_codes)]},
        fields=["name", "valuation_rate", "last_purchase_rate"],
    ):
        costs[item.name] = {
            "valuation_rate": item.valuation_rate or 0,
            "last_purchase_rate": item.last_purchase_rate or 0,
            "buying_price": 0,
        }

    buying_lists = frappe.db.get_all("Price List", filters={"buying": 1}, pluck="name")
    if buying_lists:
        for price in frappe.db.get_all(
            "Item Price",
            filters={"item_code": ["in", list(item_codes)], "price_list": ["in", buying_lists]},
            fields=["item_code", "price_list_rate"],
            order_by="valid_from asc, modified asc",
        ):
            if price.item_code in costs:
                costs[price.item_code]["buying_price"] = price.price_list_rate or 0

    return {
        code: (c["valuation_rate"] or c["buying_price"] or c["last_purchase_rate"] or 0)
        for code, c in costs.items()
    }


def get_conditions(filters):
    conditions = ""

    if filters.get("customer"):
        conditions += " AND so.customer = %(customer)s"

    if filters.get("from_date"):
        conditions += " AND so.transaction_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND so.transaction_date <= %(to_date)s"

    return conditions


@frappe.whitelist()
def get_order_items(sales_order):
    """Return items detail for the popup dialog.

    Explicit permission check: frappe.whitelist() alone only requires a
    logged-in session, not doctype-level read access — without this check
    any authenticated user could call this method directly with a guessed
    Sales Order name and read that order's cost/margin data, bypassing both
    this report's own System Manager-only role restriction and Sales
    Order's normal read permissions (see NARJES_STORE_SYSTEM.md §5.2).
    """
    frappe.has_permission("Sales Order", doc=sales_order, throw=True)

    items = frappe.db.sql("""
        SELECT
            soi.item_code,
            soi.item_name,
            soi.qty,
            soi.rate AS selling_rate,
            soi.valuation_rate AS buying_rate,
            (soi.rate - soi.valuation_rate) * soi.qty AS profit
        FROM `tabSales Order Item` soi
        WHERE soi.parent = %s
        ORDER BY soi.idx
    """, sales_order, as_dict=True)

    for row in items:
        row["source"] = _("Item")

    # Flower items are a separate child table, so they never appeared in this
    # popup even though they are part of what the customer bought and are
    # counted in the order's revenue.
    flowers = frappe.db.sql("""
        SELECT fi.flower_item AS item_code, fi.qty, fi.rate AS selling_rate
        FROM `tabFlower Item` fi
        WHERE fi.parent = %s AND fi.parenttype = 'Sales Order'
        ORDER BY fi.idx
    """, sales_order, as_dict=True)

    if flowers:
        unit_costs = get_item_unit_costs({f.item_code for f in flowers})
        item_names = {
            r.name: r.item_name
            for r in frappe.db.get_all(
                "Item",
                filters={"name": ["in", list({f.item_code for f in flowers if f.item_code})]},
                fields=["name", "item_name"],
            )
        }
        for f in flowers:
            buying_rate = unit_costs.get(f.item_code, 0)
            f["item_name"] = item_names.get(f.item_code, f.item_code)
            f["buying_rate"] = buying_rate
            f["profit"] = ((f.selling_rate or 0) - buying_rate) * (f.qty or 0)
            f["source"] = _("Flower")
        items.extend(flowers)

    return items
