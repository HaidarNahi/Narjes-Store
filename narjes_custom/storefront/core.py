"""Storefront core: language resolution, settings, and catalogue reads.

Every function here is used by guest (unauthenticated) page renders, so field
selection is explicit and allow-listed throughout — cost, valuation and
supplier data must never reach a public page (plan W10.1).
"""

import frappe
from frappe.utils import cint, flt

LANGS = ("ar", "en")
RTL_LANGS = {"ar"}
DEFAULT_LANG = "ar"
PRICE_LIST = "Standard Selling"
PLACEHOLDER = "/assets/narjes_custom/images/storefront/placeholder-product.svg"

# Fields safe to read from Item for a public page. Anything not listed here is
# never queried, so a future core field can't silently start leaking.
ITEM_WEB_FIELDS = [
	"name", "item_name", "item_code", "image", "description",
	"custom_publish_on_website", "custom_storefront_category", "custom_web_badge",
	"custom_is_featured", "custom_made_to_order", "custom_lead_time_days",
	"custom_display_order", "custom_web_route",
	"custom_web_title_ar", "custom_web_short_ar", "custom_web_long_ar",
	"custom_web_title_en", "custom_web_short_en", "custom_web_long_en",
	"stock_uom", "is_stock_item",
]


# --------------------------------------------------------------- language

def resolve_lang(path_lang=None):
	"""Pick the display language: the URL's own prefix wins, then the visitor's
	Accept-Language, then the configured default.

	The prefix is read from the request path rather than a route-rule default —
	Frappe's `website_route_rules` only pass `<param>` captures into form_dict,
	there is no mechanism for injecting a constant per rule.
	"""
	if path_lang in LANGS:
		return path_lang

	try:
		first = (frappe.local.request.path or "").strip("/").split("/")[0]
		if first in LANGS:
			return first
	except Exception:
		pass

	header = (frappe.request.headers.get("Accept-Language") or "") if frappe.request else ""
	for chunk in header.split(","):
		code = chunk.split(";")[0].strip().lower()[:2]
		if code in LANGS:
			return code

	return settings().get("default_language") or DEFAULT_LANG


def is_rtl(lang):
	return lang in RTL_LANGS


def pick(doc, base, lang):
	"""Per-language field with an ar -> en -> blank fallback chain, so a
	half-translated catalogue never renders an empty string (plan W3.3)."""
	order = [lang] + [l for l in LANGS if l != lang]
	for code in order:
		value = (doc or {}).get(f"{base}_{code}")
		if value:
			return value
	return ""


# --------------------------------------------------------------- settings

def settings():
	"""Storefront Settings as a plain dict, cached per request."""
	if not hasattr(frappe.local, "_narjes_storefront_settings"):
		try:
			doc = frappe.get_cached_doc("Narjes Storefront Settings")
			frappe.local._narjes_storefront_settings = doc.as_dict()
		except Exception:
			frappe.local._narjes_storefront_settings = {}
	return frappe.local._narjes_storefront_settings


def storefront_enabled():
	"""Two independent switches: the site_config flag is the developer kill
	switch, the Settings checkbox is the shop's own."""
	if not cint(frappe.conf.get("narjes_storefront_enabled", 1)):
		return False
	s = settings()
	return bool(cint(s.get("storefront_enabled", 1))) if s else True


def orders_enabled():
	s = settings()
	return bool(cint(s.get("orders_enabled", 1))) if s else True


# ---------------------------------------------------------------- pricing

def price_map(item_codes):
	"""{item_code: rate} from the selling price list. Missing entries are
	simply absent — the caller renders the 'reach us' state (plan W4.2)."""
	if not item_codes:
		return {}
	rows = frappe.get_all(
		"Item Price",
		filters={
			"price_list": PRICE_LIST,
			"item_code": ["in", list(item_codes)],
			"selling": 1,
		},
		fields=["item_code", "price_list_rate", "valid_from"],
		order_by="valid_from asc",
	)
	prices = {}
	for row in rows:
		if flt(row.price_list_rate) > 0:
			prices[row.item_code] = flt(row.price_list_rate)
	return prices


def stock_map(item_codes):
	"""{item_code: actual_qty} aggregated across warehouses."""
	if not item_codes:
		return {}
	# Summed in Python rather than SQL: v16 rejects aggregate functions passed
	# as strings in `fields`, and the catalogue is small enough that a couple
	# of hundred Bin rows is cheaper than the query gymnastics.
	rows = frappe.get_all(
		"Bin",
		filters={"item_code": ["in", list(item_codes)]},
		fields=["item_code", "actual_qty"],
	)
	totals = {}
	for row in rows:
		totals[row.item_code] = totals.get(row.item_code, 0) + flt(row.actual_qty)
	return totals


# --------------------------------------------------------------- catalogue

def slug_for(item):
	return item.get("custom_web_route") or frappe.scrub(item.get("item_code", "")).replace("_", "-")


def decorate(items, lang, prices=None, stocks=None):
	"""Turn raw Item rows into what a template needs — including the two
	graceful-gap behaviours the shop asked for: a shared placeholder when
	there is no photo, and a contact prompt when there is no price."""
	codes = [i["item_code"] for i in items]
	prices = price_map(codes) if prices is None else prices
	stocks = stock_map(codes) if stocks is None else stocks

	out = []
	for item in items:
		rate = prices.get(item["item_code"])
		qty = stocks.get(item["item_code"], 0)
		made_to_order = bool(cint(item.get("custom_made_to_order")))
		out.append({
			"item_code": item["item_code"],
			"title": pick(item, "custom_web_title", lang) or item.get("item_name") or item["item_code"],
			"short": pick(item, "custom_web_short", lang),
			"long": pick(item, "custom_web_long", lang),
			"image": item.get("image") or PLACEHOLDER,
			"has_image": bool(item.get("image")),
			"badge": item.get("custom_web_badge"),
			"rate": rate,
			"has_price": rate is not None,
			"route": f"/{lang}/p/{slug_for(item)}",
			"in_stock": made_to_order or qty > 0,
			"made_to_order": made_to_order,
			"lead_time": cint(item.get("custom_lead_time_days")),
			"category": item.get("custom_storefront_category"),
			# orderable only when it has a price AND is obtainable — an item
			# with no price is browsable but routes to the contact CTA
			"orderable": rate is not None and (made_to_order or qty > 0),
		})
	return out


def published_items(lang, *, category=None, search=None, featured=False, limit=None, start=0):
	filters = {"disabled": 0, "custom_publish_on_website": 1}
	if category:
		filters["custom_storefront_category"] = category
	if featured:
		filters["custom_is_featured"] = 1

	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = [
			["item_name", "like", like],
			["item_code", "like", like],
			["custom_web_title_ar", "like", like],
			["custom_web_title_en", "like", like],
		]

	items = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=ITEM_WEB_FIELDS,
		order_by="custom_display_order asc, modified desc",
		limit_page_length=limit,
		limit_start=start,
	)
	return decorate(items, lang)


def item_by_slug(slug, lang):
	"""Resolve a product URL. Matches the explicit slug first, then falls back
	to the generated one, so items published without a slug still work."""
	rows = frappe.get_all(
		"Item",
		filters={"disabled": 0, "custom_publish_on_website": 1, "custom_web_route": slug},
		fields=ITEM_WEB_FIELDS,
		limit_page_length=1,
	)
	if not rows:
		candidates = frappe.get_all(
			"Item",
			filters={"disabled": 0, "custom_publish_on_website": 1},
			fields=ITEM_WEB_FIELDS,
		)
		rows = [i for i in candidates if slug_for(i) == slug][:1]
	if not rows:
		return None

	item = decorate(rows, lang)[0]
	item["gallery"] = _gallery(rows[0]["name"], item["image"], item["has_image"])
	return item


def _gallery(item_name, main_image, has_image):
	media = frappe.get_all(
		"Narjes Product Media",
		filters={"parent": item_name, "parenttype": "Item"},
		fields=["image", "alt_text"],
		order_by="idx asc",
	)
	shots = ([{"image": main_image, "alt_text": ""}] if has_image else []) + [
		m for m in media if m.get("image")
	]
	return shots or [{"image": PLACEHOLDER, "alt_text": ""}]


def categories(lang):
	rows = frappe.get_all(
		"Narjes Storefront Category",
		filters={"published": 1},
		fields=["name", "category_name_en", "category_name_ar", "slug", "image",
		        "description_en", "description_ar", "display_order"],
		order_by="display_order asc, category_name_en asc",
	)
	return [{
		"name": r["name"],
		"title": pick(r, "category_name", lang) or r["name"],
		"description": pick(r, "description", lang),
		"slug": r.get("slug") or frappe.scrub(r["name"]).replace("_", "-"),
		"image": r.get("image"),
		"route": f"/{lang}/c/{r.get('slug') or frappe.scrub(r['name']).replace('_', '-')}",
	} for r in rows]


# ----------------------------------------------------------------- context

def guard(context):
	"""Refuse to render any storefront page while the store is switched off.
	Raises the standard 404 so a disabled shop leaks nothing about itself."""
	if not storefront_enabled():
		raise frappe.DoesNotExistError


def base_context(context, lang, *, title=None, description=None):
	"""Shared context for every storefront page."""
	s = settings()
	context.no_cache = 1
	context.lang = lang
	context.text_direction = "rtl" if is_rtl(lang) else "ltr"
	context.alt_lang = "en" if lang == "ar" else "ar"
	context.s = s
	context.categories = categories(lang)
	context.storefront_title = title or pick(s, "meta_title", lang) or "Narjes Store"
	context.storefront_description = description or pick(s, "meta_description", lang) or ""
	context.announcement = pick(s, "announcement", lang)
	context.orders_enabled = orders_enabled()
	context.noindex = bool(cint(s.get("noindex", 1))) if s else True
	context.placeholder = PLACEHOLDER
	context.whatsapp = (s.get("whatsapp") or "").strip()
	context.t = translations(lang)
	return context


def translations(lang):
	"""UI strings. Kept in code rather than the Translation doctype because
	they are structural to the templates and must never be half-missing;
	shop-editable copy lives in Storefront Settings instead."""
	ar = {
		"shop": "المتجر", "home": "الرئيسية", "about": "عن نرجس", "contact": "تواصل معنا",
		"custom_design": "تصميم خاص", "cart": "السلة", "favorites": "المفضلة",
		"search": "ابحث", "add_to_cart": "أضف إلى السلة", "added": "أُضيف إلى السلة",
		"view": "عرض", "featured": "مختارات", "new_arrivals": "وصل حديثاً",
		"categories": "الأقسام", "all_products": "كل المنتجات",
		"no_price": "لم يُحدد السعر بعد — تواصل معنا",
		"ask_price": "اسأل عن السعر", "out_of_stock": "غير متوفر حالياً",
		"made_to_order": "يُصنع حسب الطلب", "days": "يوم",
		"empty_cart": "سلتك فارغة", "checkout": "إتمام الطلب",
		"subtotal": "المجموع", "delivery": "التوصيل", "total": "الإجمالي",
		"cod": "الدفع عند الاستلام", "order_now": "اطلب الآن",
		"browse": "تصفح المتجر", "quantity": "الكمية",
		"currency": "د.ع", "language": "English", "theme": "المظهر",
		"no_results": "لا توجد نتائج", "explore": "استكشف",
	}
	en = {
		"shop": "Shop", "home": "Home", "about": "About", "contact": "Contact",
		"custom_design": "Custom Design", "cart": "Cart", "favorites": "Favourites",
		"search": "Search", "add_to_cart": "Add to cart", "added": "Added to cart",
		"view": "View", "featured": "Featured", "new_arrivals": "New arrivals",
		"categories": "Categories", "all_products": "All products",
		"no_price": "No price yet — reach us",
		"ask_price": "Ask about price", "out_of_stock": "Out of stock",
		"made_to_order": "Made to order", "days": "days",
		"empty_cart": "Your cart is empty", "checkout": "Checkout",
		"subtotal": "Subtotal", "delivery": "Delivery", "total": "Total",
		"cod": "Cash on delivery", "order_now": "Order now",
		"browse": "Browse the shop", "quantity": "Quantity",
		"currency": "IQD", "language": "العربية", "theme": "Theme",
		"no_results": "No results", "explore": "Explore",
	}
	return ar if lang == "ar" else en
