"""Guest-facing storefront endpoints (plan W10.1).

Every method here is reachable by an unauthenticated visitor, so each one:
  * allow-lists the fields it reads (never cost, valuation or supplier data),
  * bounds the size of anything the caller can ask for, and
  * renders through the same templates the server-side pages use, so a card
    can never drift between the two paths.
"""

import json

import frappe

from narjes_custom.storefront import core

MAX_ITEMS = 60


def _render_cards(products, lang):
	context = {
		"lang": lang,
		"t": core.translations(lang),
		"placeholder": core.PLACEHOLDER,
		"orders_enabled": core.orders_enabled(),
	}
	out = []
	for product in products:
		html = frappe.render_template(
			"templates/storefront/includes/product_card.html",
			{**context, "p": product},
		)
		out.append({"item_code": product["item_code"], "html": html})
	return out


@frappe.whitelist(allow_guest=True)
def get_items(item_codes, lang=None):
	"""Resolve a caller-supplied list of item codes to rendered product cards.

	Used by the favourites page, whose list lives in the visitor's browser.
	Only published, non-disabled items are ever returned, so a guessed or
	tampered code cannot surface an unpublished product.
	"""
	if not core.storefront_enabled():
		return []

	lang = core.resolve_lang(lang)
	try:
		codes = json.loads(item_codes) if isinstance(item_codes, str) else list(item_codes or [])
	except (ValueError, TypeError):
		return []

	codes = [str(c) for c in codes if c][:MAX_ITEMS]
	if not codes:
		return []

	rows = frappe.get_all(
		"Item",
		filters={"disabled": 0, "custom_publish_on_website": 1, "item_code": ["in", codes]},
		fields=core.ITEM_WEB_FIELDS,
	)
	# preserve the order the visitor saved them in
	order = {code: i for i, code in enumerate(codes)}
	products = sorted(core.decorate(rows, lang), key=lambda p: order.get(p["item_code"], 999))
	return _render_cards(products, lang)


@frappe.whitelist(allow_guest=True)
def search(q, lang=None):
	"""Instant search over published items."""
	if not core.storefront_enabled():
		return []
	lang = core.resolve_lang(lang)
	term = (q or "").strip()[:60]
	if len(term) < 2:
		return []
	products = core.published_items(lang, search=term, limit=12)
	return [
		{
			"title": p["title"],
			"route": p["route"],
			"image": p["image"],
			"rate": p["rate"],
			"has_price": p["has_price"],
		}
		for p in products
	]
