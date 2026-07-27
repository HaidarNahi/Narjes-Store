# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

import frappe
from frappe import _


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

    data = []
    for row in orders:
        # Selling Rate = Grand Total - Delivery Fees
        delivery_fees = row.delivery_fees or 0
        selling_rate = (row.grand_total or 0) - delivery_fees

        # Buying Rate = sum of (valuation_rate * qty) for all items in this SO
        buying_data = frappe.db.sql("""
            SELECT IFNULL(SUM(soi.valuation_rate * soi.qty), 0) AS total_buying
            FROM `tabSales Order Item` soi
            WHERE soi.parent = %s
        """, row.sales_order, as_dict=True)
        buying_rate = buying_data[0].total_buying if buying_data else 0

        # Packaging + Painting costs
        packaging_costs = row.packaging_costs or 0
        painting_costs = row.custom_total_painting_cost or 0
        packaging_and_painting = packaging_costs + painting_costs

        # Profit = Selling Rate - Buying Rate - (Packaging + Painting)
        profit = selling_rate - buying_rate - packaging_and_painting

        # Profit Percentage
        profit_percentage = (profit / selling_rate * 100) if selling_rate else 0

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
            "profit": profit,
            "profit_percentage": profit_percentage,
            "items_detail": row.sales_order
        })

    return data


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
    """Return items detail for the popup dialog."""
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
    return items
