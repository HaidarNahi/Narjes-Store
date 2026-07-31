import frappe
from narjes_custom.storefront import core


def get_context(context):
	lang = core.resolve_lang(frappe.form_dict.get("lang"))
	core.guard(context)
	core.base_context(context, lang)

	slug = frappe.form_dict.get("slug")
	category = None
	if slug:
		category = next((c for c in core.categories(lang) if c["slug"] == slug), None)
		if not category:
			raise frappe.DoesNotExistError

	search = (frappe.form_dict.get("q") or "").strip()[:60]
	context.category = category
	context.search = search
	context.canonical_path = f"/c/{slug}" if slug else "/shop"
	context.heading = category["title"] if category else (
		context.t["no_results"] if False else context.t["all_products"]
	)
	context.products = core.published_items(
		lang, category=category["name"] if category else None, search=search or None
	)
	return context
