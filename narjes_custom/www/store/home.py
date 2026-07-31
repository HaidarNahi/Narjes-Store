import frappe
from narjes_custom.storefront import core


def get_context(context):
	lang = core.resolve_lang(frappe.form_dict.get("lang"))
	core.guard(context)
	core.base_context(context, lang)
	context.canonical_path = ""
	context.featured = core.published_items(lang, featured=True, limit=8)
	context.latest = core.published_items(lang, limit=8)
	return context
