import frappe
from narjes_custom.storefront import core, seo


def get_context(context):
	lang = core.resolve_lang(frappe.form_dict.get("lang"))
	core.guard(context)

	slug = frappe.form_dict.get("slug")
	category = None
	if slug:
		category = next((c for c in core.categories(lang) if c["slug"] == slug), None)
		if not category:
			raise frappe.DoesNotExistError

	search = (frappe.form_dict.get("q") or "").strip()[:60]

	# A search-results page is thin, unbounded and duplicates the catalogue it
	# filters — exactly the surface that burns crawl budget without ever
	# ranking. It stays out of the index and points its canonical at the
	# unfiltered listing it is a subset of (plan W10.3).
	core.base_context(context, lang, noindex=bool(search))

	context.category = category
	context.search = search
	context.canonical_path = f"/c/{slug}" if slug else "/shop"
	context.heading = category["title"] if category else core.translations(lang)["all_products"]
	context.products = core.published_items(
		lang, category=category["name"] if category else None, search=search or None
	)

	t = core.translations(lang)
	crumbs = [(t["home"], ""), (t["shop"], "/shop")]
	if category:
		crumbs.append((category["title"], f"/c/{slug}"))
	context.crumbs = crumbs

	seo.graph(
		context,
		seo.collection_page_ld(
			lang,
			path=context.canonical_path,
			name=context.heading,
			description=(category or {}).get("description"),
		),
		seo.item_list_ld(
			context.products, lang, path=context.canonical_path, name=context.heading
		),
		seo.breadcrumb_ld(lang, crumbs),
	)
	return context
