import frappe
from narjes_custom.storefront import core, seo


def get_context(context):
	lang = core.resolve_lang()
	core.guard(context)
	core.base_context(context, lang)
	context.canonical_path = "/contact"

	t = core.translations(lang)
	crumbs = [(t["home"], ""), (t["contact"], "/contact")]
	seo.graph(
		context,
		seo.page_ld(lang, "ContactPage", path="/contact", name=t["contact"]),
		seo.breadcrumb_ld(lang, crumbs),
	)
	return context
