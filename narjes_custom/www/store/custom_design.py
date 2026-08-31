import frappe
from narjes_custom.storefront import core, seo


def get_context(context):
	lang = core.resolve_lang()
	core.guard(context)
	core.base_context(context, lang, title=core.translations(lang).get("custom_design"))
	context.canonical_path = "/custom-design"
	context.governorates = core.GOVERNORATES if hasattr(core, "GOVERNORATES") else []
	context.no_cache = 1

	# Indexable on purpose: "custom design" is the shop's differentiator and the
	# page is real, static content — unlike the cart and checkout below it.
	t = core.translations(lang)
	seo.graph(
		context,
		seo.page_ld(lang, "WebPage", path="/custom-design", name=t["custom_design"]),
		seo.breadcrumb_ld(lang, [(t["home"], ""), (t["custom_design"], "/custom-design")]),
	)
	return context
