import frappe
from narjes_custom.storefront import core, seo


def get_context(context):
	lang = core.resolve_lang(frappe.form_dict.get("lang"))
	core.guard(context)
	core.base_context(context, lang)

	product = core.item_by_slug(frappe.form_dict.get("slug") or "", lang)
	if not product:
		raise frappe.DoesNotExistError

	context.p = product
	context.canonical_path = f"/p/{frappe.form_dict.get('slug')}"
	context.storefront_title = f"{product['title']} · " + ("النرجس" if lang == "ar" else "Narjes")
	context.storefront_description = product.get("short") or context.storefront_description
	context.related = [
		r for r in core.published_items(lang, category=product.get("category"), limit=5)
		if r["item_code"] != product["item_code"]
	][:4]

	# The item's own photo is what a pasted link should preview — but only a
	# real one. The shared placeholder would make every priceless item look
	# identical in a WhatsApp thread, so it falls through to the shop's OG card.
	if product.get("has_image") and core.public_file(product.get("image")):
		context.share_image = product.get("image")

	# Breadcrumb mirrors the trail rendered on the page, including the category
	# when the item has one, so the markup never claims a path the visitor
	# cannot walk.
	t = core.translations(lang)
	crumbs = [(t["home"], ""), (t["shop"], "/shop")]
	category = next(
		(c for c in context.categories if c["name"] == product.get("category")), None
	)
	if category:
		crumbs.append((category["title"], f"/c/{category['slug']}"))
	crumbs.append((product["title"], context.canonical_path))
	context.crumbs = crumbs

	seo.graph(
		context,
		seo.product_ld(product, lang, gallery=product.get("gallery")),
		seo.breadcrumb_ld(lang, crumbs),
	)
	return context
