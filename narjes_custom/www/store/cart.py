import frappe
from narjes_custom.storefront import core


def get_context(context):
	lang = core.resolve_lang()
	core.guard(context)
	# Per-visitor page with nothing to rank — kept out of the index (W10.3).
	core.base_context(context, lang, title=core.translations(lang).get("cart"), noindex=True)
	context.canonical_path = "/cart"
	context.no_cache = 1
	return context
