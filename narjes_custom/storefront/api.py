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


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@frappe.whitelist(allow_guest=True)
def upload_reference():
	"""Accept a reference image for a custom-design request.

	Frappe's own `upload_file` refuses guests (403), and opening that endpoint
	up would let anyone attach anything to any doctype. This is the narrow
	alternative: images only, size-capped, never attached to a document.
	"""
	if not core.storefront_enabled():
		frappe.throw(frappe._("Uploads are currently unavailable."))

	files = getattr(frappe.request, "files", None)
	uploaded = files.get("file") if files else None
	if not uploaded:
		frappe.throw(frappe._("No file received."))

	content = uploaded.stream.read()
	if not content:
		frappe.throw(frappe._("The file is empty."))
	if len(content) > MAX_UPLOAD_BYTES:
		frappe.throw(frappe._("Images must be under 5 MB."))

	filename = (uploaded.filename or "reference").rsplit("/", 1)[-1]
	extension = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
	if extension not in ALLOWED_EXTENSIONS or (uploaded.mimetype or "") not in ALLOWED_IMAGE_TYPES:
		frappe.throw(frappe._("Only JPG, PNG, WEBP or GIF images are accepted."))

	# Decoding proves it is genuinely an image rather than something renamed.
	try:
		from io import BytesIO

		from PIL import Image

		Image.open(BytesIO(content)).verify()
	except Exception:
		frappe.throw(frappe._("That file is not a readable image."))

	from narjes_custom.storefront.orders import as_system

	with as_system():
		doc = frappe.new_doc("File")
		doc.file_name = filename[:120]
		doc.content = content
		doc.is_private = 0
		doc.folder = "Home"
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

	return {"file_url": doc.file_url}
