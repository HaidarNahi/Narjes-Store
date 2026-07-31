import frappe
from narjes_custom.storefront import core


def get_context(context):
	lang = core.resolve_lang()
	core.guard(context)
	core.base_context(context, lang, title=core.translations(lang).get("cart"))
	context.no_cache = 1
	return context
