# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

"""Customer Orders — one row per order, the way the shop keeps it on paper.

Mirrors the order sheet staff already use: who ordered, what kind of order it
was, the price with and without delivery, the governorate and the address.

Which orders count: every live order in the date range. That means submitted
orders *and* drafts, because an order here stays a draft while it moves across
the Order Phases board and is only submitted when it reaches Done — leaving
drafts out would hide every order still in progress. Cancelled orders (either
cancelled documents or drafts moved to the Cancelled/Returned phases) are left
out: they never earned anything.

Prices: "with delivery" is `total_with_delivery_fees`, the figure printed on the
box sticker and collected by the courier. "Without delivery" is that minus the
delivery fee. It is deliberately not read from `grand_total`: on older orders
the fee was booked inside grand_total as a tax row, on newer ones beside it, so
subtracting the fee from the customer's total is the one definition that is
right for both.
"""

import frappe
from frappe import _
from frappe.utils import escape_html, flt, getdate

from narjes_custom.reports_meta import card

DEAD_PHASES = ("Cancelled", "Returned")
NOT_SET = "Not set"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.from_date and filters.to_date and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date must be before To Date."))

	rows = _orders(filters)
	data = [
		{
			"sales_order": r.name,
			"transaction_date": r.transaction_date,
			"customer_name": r.customer_name or r.customer,
			"order_type": r.design_type or "",
			"price_without_delivery": flt(r.total_with_delivery_fees) - flt(r.delivery_fees),
			"price_with_delivery": flt(r.total_with_delivery_fees),
			"governorate": r.governorate_of_delivery or "",
			"address": r.full_address or "",
		}
		for r in rows
	]

	return (
		get_columns(),
		data,
		_insights(data),
		_chart(data),
		_summary(data),
	)


def _orders(filters):
	so = frappe.qb.DocType("Sales Order")
	cust = frappe.qb.DocType("Customer")
	q = (
		frappe.qb.from_(so)
		.left_join(cust)
		.on(cust.name == so.customer)
		.select(
			so.name,
			so.transaction_date,
			so.customer,
			so.customer_name,
			so.design_type,
			so.total_with_delivery_fees,
			so.delivery_fees,
			so.governorate_of_delivery,
			cust.full_address,
		)
		.where(so.docstatus < 2)
		.where((so.order_phase.isnull()) | (so.order_phase.notin(DEAD_PHASES)))
		.where(so.transaction_date[filters.from_date : filters.to_date])
		.orderby(so.transaction_date)
		.orderby(so.creation)
	)
	if filters.governorate:
		q = q.where(so.governorate_of_delivery == filters.governorate)
	if filters.order_type:
		q = q.where(so.design_type == filters.order_type)
	if filters.customer:
		q = q.where(so.customer == filters.customer)
	return q.run(as_dict=True)


# ------------------------------------------------------------------ summary


def _summary(data):
	orders = len(data)
	sales = sum(d["price_without_delivery"] for d in data)
	with_delivery = sum(d["price_with_delivery"] for d in data)
	# Orders with no governorate are left out of the share rather than
	# guessed into either side.
	located = sum(1 for d in data if d["governorate"])
	outside = sum(1 for d in data if d["governorate"] and d["governorate"] != "بغداد")
	return [
		card("Orders", orders, indicator="Blue", datatype="Int"),
		card("Sales (without delivery)", sales, indicator="Green", datatype="Currency"),
		card("Customers pay (with delivery)", with_delivery, datatype="Currency"),
		card("Delivery fees", with_delivery - sales, datatype="Currency"),
		card("Average order", (sales / orders) if orders else 0, datatype="Currency"),
		card(
			"Outside Baghdad",
			round(100 * outside / located) if located else 0,
			datatype="Percent",
		),
	]


# ------------------------------------------------------------------- charts


def _chart(data):
	"""Sales per day — the rhythm of the period at a glance."""
	if not data:
		return None
	by_day = {}
	for d in data:
		key = str(d["transaction_date"])
		by_day[key] = by_day.get(key, 0) + d["price_without_delivery"]
	days = sorted(by_day)
	return {
		"title": _("Sales per day (without delivery)"),
		"data": {
			# "03 Oct" rather than "2026-10-03": the year is in the filter, and
			# full dates get truncated to "2..." once a month of bars is shown.
			"labels": [getdate(k).strftime("%d %b") for k in days],
			"datasets": [{"name": _("Sales"), "values": [round(by_day[k]) for k in days]}],
		},
		"type": "bar",
		"colors": ["#2E5C46"],
		"fieldtype": "Currency",
		"barOptions": {"spaceRatio": 0.35},
	}


def _group(data, key):
	"""[(label, orders, sales)] sorted by orders, most first."""
	out = {}
	for d in data:
		label = d[key] or NOT_SET
		n, s = out.get(label, (0, 0))
		out[label] = (n + 1, s + d["price_without_delivery"])
	return sorted(((k, n, s) for k, (n, s) in out.items()), key=lambda x: (-x[1], -x[2]))


def _bars(title, groups, total_orders, colour, limit=8):
	if len(groups) > limit:
		rest = groups[limit - 1 :]
		other = (_("Other ({0})").format(len(rest)), sum(g[1] for g in rest), sum(g[2] for g in rest))
		groups = [*groups[: limit - 1], other]
	peak = max((g[1] for g in groups), default=1) or 1
	rows = []
	for label, n, sales in groups:
		share = round(100 * n / total_orders) if total_orders else 0
		muted = " co-muted" if label == NOT_SET else ""
		rows.append(
			f"""<div class="co-row{muted}">
				<div class="co-label" dir="auto" title="{escape_html(label)}">{escape_html(_(label) if label == NOT_SET else label)}</div>
				<div class="co-track"><div class="co-fill" style="width:{max(3, round(100 * n / peak))}%;background:{colour}"></div></div>
				<div class="co-num">{n} <span>· {share}%</span></div>
				<div class="co-money">{frappe.format_value(sales, {"fieldtype": "Currency"})}</div>
			</div>"""
		)
	return f"""<div class="co-card"><div class="co-title">{escape_html(title)}</div>{"".join(rows)}</div>"""


def _insights(data):
	"""Two breakdowns the single Frappe chart can't hold: where orders go and
	what kind they are. Rendered as plain HTML bars so they paint together with
	the table — no second request, no second loading state."""
	if not data:
		return None
	total = len(data)
	by_gov = _group(data, "governorate")
	by_type = _group(data, "order_type")
	return f"""
<style>
.co-insights{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin:4px 0 8px}}
.co-card{{border:1px solid var(--border-color);border-radius:var(--border-radius-md,8px);padding:12px 14px;background:var(--card-bg,var(--fg-color))}}
.co-title{{font-weight:600;font-size:var(--text-sm,13px);color:var(--text-color);margin-bottom:10px}}
.co-row{{display:grid;grid-template-columns:minmax(80px,1.1fr) 2fr auto minmax(90px,auto);align-items:center;gap:10px;padding:3px 0;font-size:var(--text-sm,13px)}}
.co-label{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-color)}}
.co-track{{height:8px;border-radius:4px;background:var(--gray-100,#f3f3f3);overflow:hidden}}
.co-fill{{height:100%;border-radius:4px}}
.co-num{{font-variant-numeric:tabular-nums;font-weight:500;white-space:nowrap}}
.co-num span{{color:var(--text-muted);font-weight:400}}
.co-money{{font-variant-numeric:tabular-nums;color:var(--text-muted);text-align:right;white-space:nowrap}}
.co-muted .co-label{{color:var(--text-muted);font-style:italic}}
.co-muted .co-fill{{background:var(--gray-400,#bbb)!important}}
</style>
<div class="co-insights">
	{_bars(_("Orders by governorate"), by_gov, total, "#2E5C46")}
	{_bars(_("Orders by order type"), by_type, total, "#B7791F")}
</div>"""


# ------------------------------------------------------------------ columns


def get_columns():
	return [
		{
			"fieldname": "sales_order",
			"label": _("Order"),
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 140,
		},
		{"fieldname": "transaction_date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data", "width": 170},
		{"fieldname": "order_type", "label": _("Order Type"), "fieldtype": "Data", "width": 110},
		{
			"fieldname": "price_without_delivery",
			"label": _("Price without Delivery"),
			"fieldtype": "Currency",
			"width": 175,
		},
		{
			"fieldname": "price_with_delivery",
			"label": _("Price with Delivery"),
			"fieldtype": "Currency",
			"width": 165,
		},
		{"fieldname": "governorate", "label": _("Governorate"), "fieldtype": "Data", "width": 110},
		{"fieldname": "address", "label": _("Address"), "fieldtype": "Data", "width": 300},
	]
