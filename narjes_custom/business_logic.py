"""
narjes_custom.business_logic
=============================
Pure calculation functions with NO Frappe/ERPNext import — deliberately
kept dependency-free so they can be unit tested directly (see
narjes_custom/tests/test_business_logic.py) without a running site.

Importing narjes_custom.api directly pulls in ERPNext's full controller
import chain (Sales Invoice -> deferred revenue -> stock utils -> ... ->
frappe.logger(), which needs an initialized site to open its log file), so
these can't live there and still be testable standalone. They're imported
by api.py, the Sales Revenue Report, and the AI intake confirm flow instead
of being redefined in each place.
"""


def compute_delivery_fee(governorate, baghdad_fee, other_governorate_fee):
    """Delivery fee for a Sales Order/Sales Invoice/Delivery Note, based on
    the governorate of delivery. Baghdad gets the (usually cheaper) flat
    baghdad_fee; any other non-empty governorate gets other_governorate_fee;
    no governorate set means no fee yet."""
    if not governorate:
        return 0
    if governorate == 'بغداد':
        return baghdad_fee or 0
    return other_governorate_fee or 0


def compute_canvas_cost(total_area, rate_per_cm):
    """Canvas items are priced by area: total cm² across the order × a
    rate per cm² (Narjes Settings.painting_rate_per_cm)."""
    return (total_area or 0) * (rate_per_cm or 0)


def compute_sheet_cost(qty, rate_per_sheet):
    """Sheet items are priced flat per unit, not by area (Narjes
    Settings.sheet_rate_per_item)."""
    return (qty or 0) * (rate_per_sheet or 0)


def compute_profit(selling_rate, buying_rate, packaging_and_painting):
    """Sales Revenue Report's per-order profit: revenue net of delivery
    fees, minus cost of goods, minus packaging/painting overhead."""
    return (selling_rate or 0) - (buying_rate or 0) - (packaging_and_painting or 0)


def compute_profit_percentage(profit, selling_rate):
    """Guarded against divide-by-zero: an order with 0 selling rate
    (e.g. fully comped) reports 0% rather than raising."""
    if not selling_rate:
        return 0
    return (profit / selling_rate) * 100


def is_discount_excessive(discount_amount, order_subtotal, max_percentage):
    """AI Order Intake's discount sanity backstop (see
    NARJES_STORE_SYSTEM.md §8.4/§15): True if discount_amount is more than
    max_percentage of order_subtotal. An order with a zero/negative
    subtotal is never flagged here — that's a different validation
    problem, not a discount problem."""
    if order_subtotal <= 0:
        return False
    return discount_amount > order_subtotal * (max_percentage / 100)
