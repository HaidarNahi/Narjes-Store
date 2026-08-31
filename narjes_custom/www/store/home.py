import frappe
from narjes_custom.storefront import core, seo


def get_context(context):
	lang = core.resolve_lang(frappe.form_dict.get("lang"))
	core.guard(context)
	core.base_context(context, lang)
	context.canonical_path = ""
	context.featured = core.published_items(lang, featured=True, limit=8)
	context.latest = core.published_items(lang, limit=8)

	# Organization + WebSite come free with every graph; the home page adds the
	# featured grid it actually renders. Latest is deliberately left out — the
	# two lists overlap, and one ItemList per page is what Google reads.
	seo.graph(
		context,
		seo.item_list_ld(
			context.featured, lang, path="", name=core.translations(lang)["featured"]
		),
	)
	return context
