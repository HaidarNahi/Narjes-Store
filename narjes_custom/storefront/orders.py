"""Guest checkout and custom-design submission (plan W6–W8).

Both entry points are reachable without an account, so both treat everything
the browser sends as untrusted: the cart is priced from the database, never
from the payload, and the only thing the visitor really controls is *which*
published item and how many.
"""

import json

import frappe
from frappe.utils import cint, flt, now_datetime

from narjes_custom.ai_intake.matching import match_customer, normalize_phone
from narjes_custom.storefront import core

MAX_LINES = 30
MAX_QTY_PER_LINE = 99
ORDER_SOURCE = "From the Website"


class CheckoutError(frappe.ValidationError):
	pass


def _t(lang):
	return core.translations(lang)


def _fail(msg):
	frappe.throw(msg, exc=CheckoutError)


def _clean(value, limit=140):
	return (str(value or "").strip())[:limit]


# ---------------------------------------------------------------- cart pricing


def price_cart(lines, lang="ar"):
	"""Resolve a client cart into priced server-side lines.

	Returns (rows, totals). Anything unpublished, unpriced or unknown is
	dropped and reported, so a stale localStorage cart degrades into a clear
	message instead of a broken order.
	"""
	t = _t(lang)
	try:
		raw = json.loads(lines) if isinstance(lines, str) else (lines or [])
	except (ValueError, TypeError):
		raw = []

	wanted = {}
	for entry in raw[:MAX_LINES]:
		code = _clean(isinstance(entry, dict) and entry.get("item_code"), 140)
		qty = cint(isinstance(entry, dict) and entry.get("qty")) or 1
		if not code:
			continue
		wanted[code] = min(max(qty, 1), MAX_QTY_PER_LINE)

	if not wanted:
		return [], {"total": 0, "count": 0}, []

	items = frappe.get_all(
		"Item",
		filters={
			"disabled": 0,
			"custom_publish_on_website": 1,
			"item_code": ["in", list(wanted)],
		},
		fields=core.ITEM_WEB_FIELDS,
	)
	products = {p["item_code"]: p for p in core.decorate(items, lang)}

	rows, dropped, total = [], [], 0.0
	for code, qty in wanted.items():
		product = products.get(code)
		if not product:
			dropped.append({"item_code": code, "reason": t.get("unavailable", "Unavailable")})
			continue
		# an item with no price cannot be ordered online — the storefront shows
		# a "reach us" contact prompt for these instead of an add-to-cart button
		if not product.get("has_price"):
			dropped.append({"item_code": code, "title": product["title"],
			                "reason": t.get("ask_price", "Ask for price")})
			continue

		rate = flt(product["rate"])
		amount = rate * qty
		total += amount
		rows.append({
			"item_code": code,
			"title": product["title"],
			"image": product["image"],
			"has_image": product["has_image"],
			"route": product["route"],
			"rate": rate,
			"qty": qty,
			"amount": amount,
		})

	return rows, {"total": total, "count": sum(r["qty"] for r in rows)}, dropped


@frappe.whitelist(allow_guest=True)
def quote(lines, governorate=None, lang=None):
	"""Live cart/checkout summary: server prices + the delivery fee for the
	chosen governorate, using the same Narjes Settings values the desk uses."""
	if not core.storefront_enabled():
		return {}
	lang = core.resolve_lang(lang)
	rows, totals, dropped = price_cart(lines, lang)

	fee = 0.0
	if governorate:
		settings = frappe.get_cached_doc("Narjes Settings")
		from narjes_custom.api import compute_delivery_fee

		fee = flt(compute_delivery_fee(
			_clean(governorate, 60),
			settings.baghdad_delivery_fee,
			settings.other_governorate_delivery_fee,
		))

	return {
		"lines": rows,
		"dropped": dropped,
		"subtotal": totals["total"],
		"count": totals["count"],
		"delivery_fee": fee,
		"grand_total": totals["total"] + fee,
		"currency": "IQD",
	}


# ------------------------------------------------------------------- customer


def _resolve_customer(name, phone, governorate, address):
	"""Match an existing Customer by phone, else create one.

	Reuses the AI-intake matcher so a customer who has ordered by WhatsApp
	before is recognised as the same person here rather than duplicated.
	"""
	normalized = normalize_phone(phone)
	if not normalized:
		_fail(frappe._("A valid phone number is required."))

	match = match_customer([normalized], name) or {}
	existing = match.get("customer") or match.get("name")
	if existing and frappe.db.exists("Customer", existing):
		customer = frappe.get_doc("Customer", existing)
		dirty = False
		# fill gaps only — never overwrite what staff have curated
		for field, value in (
			("governorate", governorate),
			("full_address", address),
		):
			if value and customer.meta.has_field(field) and not customer.get(field):
				customer.set(field, value)
				dirty = True
		if dirty:
			customer.save(ignore_permissions=True)
		return customer.name

	customer = frappe.new_doc("Customer")
	customer.customer_name = name or normalized
	customer.customer_type = "Individual"
	for field, value in (
		("main_phone_number", normalized),
		("governorate", governorate),
		("full_address", address),
		("channal", "Website"),
	):
		if value and customer.meta.has_field(field):
			customer.set(field, value)
	customer.insert(ignore_permissions=True)
	return customer.name


# ---------------------------------------------------------------- place order


@frappe.whitelist(allow_guest=True)
def place_order(payload):
	"""Create a Draft Sales Order from a guest cart.

	Draft, not submitted: cash on delivery carries no payment guarantee, so
	staff confirm from the Kanban before the order is committed.
	"""
	if not core.storefront_enabled() or not core.orders_enabled():
		_fail(frappe._("Ordering is currently unavailable."))

	try:
		data = json.loads(payload) if isinstance(payload, str) else (payload or {})
	except (ValueError, TypeError):
		_fail(frappe._("Invalid order data."))

	lang = core.resolve_lang(data.get("lang"))
	name = _clean(data.get("name"))
	phone = _clean(data.get("phone"), 40)
	governorate = _clean(data.get("governorate"), 60)
	address = _clean(data.get("address"), 500)
	notes = _clean(data.get("notes"), 1000)

	if not name or not phone or not governorate:
		_fail(frappe._("Please fill in your name, phone and governorate."))

	rows, totals, dropped = price_cart(data.get("lines"), lang)
	if not rows:
		_fail(frappe._("Your cart is empty."))

	# guest submissions run with elevated rights deliberately: a visitor has no
	# permission to write Customer or Sales Order, and everything written here
	# is server-derived rather than caller-supplied
	customer = _resolve_customer(name, phone, governorate, address)

	order = frappe.new_doc("Sales Order")
	order.customer = customer
	order.transaction_date = frappe.utils.nowdate()
	order.delivery_date = frappe.utils.add_days(frappe.utils.nowdate(), 3)
	order.order_type = "Sales"

	for field, value in (
		("custom_order_source", ORDER_SOURCE),
		("governorate_of_delivery", governorate),
		("custom_web_notes", notes),
	):
		if value and order.meta.has_field(field):
			order.set(field, value)

	for row in rows:
		order.append("items", {
			"item_code": row["item_code"],
			"qty": row["qty"],
			"rate": row["rate"],
			"delivery_date": order.delivery_date,
		})

	order.flags.ignore_permissions = True
	order.insert(ignore_permissions=True)

	reference = order.name
	if order.meta.has_field("custom_web_order_ref"):
		frappe.db.set_value("Sales Order", order.name, "custom_web_order_ref", reference)

	_notify_staff(order, name, phone, governorate)
	frappe.db.commit()

	return {
		"ok": True,
		"reference": reference,
		"redirect": f"/{lang}/order/{reference}",
		"dropped": dropped,
	}


def _notify_staff(order, name, phone, governorate):
	"""In-desk notification — deliberately not email, because this site has no
	outgoing mail configured yet (see the storefront plan, ground truth #2)."""
	try:
		recipients = [
			u.name
			for u in frappe.get_all(
				"Has Role",
				filters={"role": "Sales Manager", "parenttype": "User"},
				fields=["parent as name"],
				limit=5,
			)
		] or ["Administrator"]
		for user in set(recipients):
			note = frappe.new_doc("Notification Log")
			note.subject = frappe._("New website order from {0}").format(name)
			note.email_content = f"{name} · {phone} · {governorate}"
			note.for_user = user
			note.document_type = "Sales Order"
			note.document_name = order.name
			note.type = "Alert"
			note.insert(ignore_permissions=True)
	except Exception:
		# a notification must never cost the customer their order
		frappe.log_error(frappe.get_traceback(), "Storefront: staff notification failed")


# --------------------------------------------------------- design requests


@frappe.whitelist(allow_guest=True)
def submit_design_request(payload):
	"""Create a Narjes Design Request from the custom-design form."""
	if not core.storefront_enabled():
		_fail(frappe._("Requests are currently unavailable."))

	try:
		data = json.loads(payload) if isinstance(payload, str) else (payload or {})
	except (ValueError, TypeError):
		_fail(frappe._("Invalid request data."))

	name = _clean(data.get("name"))
	phone = _clean(data.get("phone"), 40)
	governorate = _clean(data.get("governorate"), 60)
	if not name or not phone:
		_fail(frappe._("Please fill in your name and phone."))

	doc = frappe.new_doc("Narjes Design Request")
	doc.customer_name = name
	doc.phone = normalize_phone(phone) or phone
	for field, value in (
		("governorate", governorate),
		("occasion", _clean(data.get("occasion"), 60)),  # canonical English values; the form shows localised labels
		("design_type", _clean(data.get("design_type"), 60)),
		("size_note", _clean(data.get("size"), 140)),
		("notes", _clean(data.get("notes"), 2000)),
	):
		if doc.meta.has_field(field):
			doc.set(field, value)

	for url in (data.get("files") or [])[:8]:
		url = _clean(url, 400)
		if url.startswith("/files/") or url.startswith("/private/files/"):
			doc.append("attachments", {"file_url": url})

	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True, "reference": doc.name}
