import frappe
from narjes_custom.storefront import core, seo


def get_context(context):
	lang = core.resolve_lang()
	core.guard(context)
	core.base_context(context, lang)
	context.canonical_path = "/about"

	t = core.translations(lang)
	crumbs = [(t["home"], ""), (t["about"], "/about")]
	seo.graph(
		context,
		seo.page_ld(lang, "AboutPage", path="/about", name=t["about"]),
		seo.breadcrumb_ld(lang, crumbs),
	)
	return context
