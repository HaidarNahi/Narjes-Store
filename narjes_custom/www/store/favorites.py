import frappe
from narjes_custom.storefront import core


def get_context(context):
	lang = core.resolve_lang()
	core.guard(context)
	# Contents live in the visitor's own browser storage — nothing to crawl.
	core.base_context(context, lang, noindex=True)
	context.canonical_path = "/favorites"
	return context
