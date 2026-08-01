import frappe
from narjes_custom.storefront import core


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
	return context
