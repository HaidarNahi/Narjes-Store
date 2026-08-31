"""
Unit tests for the storefront SEO layer — pure Python, zero Frappe DB
dependency, same spirit as test_business_logic.py. Run via:

    python -m pytest apps/narjes_custom/narjes_custom/tests/test_seo.py -v

These cover the two behaviours that are silent when they break and expensive
when they stay broken:

* `_prune` — an empty Settings field must vanish from the graph rather than
  emit `"telephone": ""`. Google reads an empty string as a claim and errors
  on it; absence it simply ignores.
* `product_ld` offers — an unpriced item must omit `offers` entirely. The bug
  this replaced emitted `"offers": null`, which invalidates the whole Product
  node and costs the rich result.

Everything DB-backed (sitemap contents, page rendering) is exercised by
rendering the real routes against a site; see docs/SEO.md.
"""

import unittest
from unittest import mock

from narjes_custom.storefront import core, seo


class TestPrune(unittest.TestCase):
	def test_drops_none_and_empty(self):
		got = seo._prune({"a": 1, "b": None, "c": "", "d": [], "e": {}})
		self.assertEqual(got, {"a": 1})

	def test_keeps_zero_and_false(self):
		"""A price of 0 and an explicit `false` are assertions, not blanks."""
		got = seo._prune({"price": 0, "flag": False})
		self.assertEqual(got, {"price": 0, "flag": False})

	def test_recurses_into_nested(self):
		got = seo._prune({"offer": {"price": 5, "seller": None}, "tags": ["a", "", None]})
		self.assertEqual(got, {"offer": {"price": 5}, "tags": ["a"]})

	def test_drops_dict_that_empties_out(self):
		self.assertEqual(seo._prune({"address": {"street": "", "city": None}}), {})

	def test_strips_whitespace(self):
		self.assertEqual(seo._prune({"name": "  Narjes  "}), {"name": "Narjes"})


class TestSanitizeSlug(unittest.TestCase):
	def test_strips_url_unsafe_characters(self):
		self.assertEqual(core.sanitize_slug("mdf 50*80"), "mdf-50-80")
		self.assertEqual(core.sanitize_slug("FRAME (A3)"), "FRAME-A3")
		self.assertEqual(core.sanitize_slug("q?x=1&y=2"), "q-x-1-y-2")

	def test_collapses_runs_and_trims(self):
		self.assertEqual(core.sanitize_slug("a--b__c"), "a-b-c")
		self.assertEqual(core.sanitize_slug("  -x-  "), "x")

	def test_preserves_arabic(self):
		"""An Arabic slug is a legitimate URL and must survive intact."""
		self.assertEqual(core.sanitize_slug("ورد-أحمر"), "ورد-أحمر")

	def test_empty(self):
		self.assertEqual(core.sanitize_slug(""), "")
		self.assertEqual(core.sanitize_slug(None), "")


@mock.patch.object(seo, "shop_name", lambda lang: "Narjes")
@mock.patch.object(seo, "get_url", lambda: "https://narjes.store")
class TestProductLd(unittest.TestCase):
	def _item(self, **overrides):
		item = {
			"item_code": "ROSE-01",
			"title": "Rose",
			"short": "A rose",
			"image": "/files/rose.jpg",
			"route": "/ar/p/rose",
			"has_price": True,
			"rate": 10000.0,
			"in_stock": True,
			"made_to_order": False,
			"lead_time": 0,
			"category": "Flowers",
		}
		item.update(overrides)
		return item

	def test_priced_item_has_offer(self):
		node = seo.product_ld(self._item(), "ar")
		self.assertEqual(node["offers"]["price"], 10000.0)
		self.assertEqual(node["offers"]["priceCurrency"], "IQD")
		self.assertEqual(node["offers"]["availability"], "https://schema.org/InStock")

	def test_unpriced_item_omits_offers_entirely(self):
		"""Not `null`, not a zero-price Offer — absent."""
		node = seo.product_ld(self._item(has_price=False, rate=None), "ar")
		self.assertNotIn("offers", node)

	def test_out_of_stock_availability(self):
		node = seo.product_ld(self._item(in_stock=False), "ar")
		self.assertEqual(node["offers"]["availability"], "https://schema.org/OutOfStock")

	def test_images_absolutised(self):
		node = seo.product_ld(self._item(), "ar")
		self.assertEqual(node["image"], ["https://narjes.store/files/rose.jpg"])

	def test_gallery_used_when_given(self):
		node = seo.product_ld(
			self._item(),
			"ar",
			gallery=[{"image": "/files/a.jpg"}, {"image": "/files/b.jpg"}],
		)
		self.assertEqual(
			node["image"],
			["https://narjes.store/files/a.jpg", "https://narjes.store/files/b.jpg"],
		)

	def test_made_to_order_lead_time_exposed(self):
		node = seo.product_ld(self._item(made_to_order=True, lead_time=5), "ar")
		self.assertEqual(node["additionalProperty"]["value"], 5)

	def test_no_lead_time_property_when_not_made_to_order(self):
		self.assertNotIn("additionalProperty", seo.product_ld(self._item(), "ar"))

	def test_no_inlanguage(self):
		"""inLanguage is a CreativeWork property; Product is not one."""
		self.assertNotIn("inLanguage", seo.product_ld(self._item(), "ar"))


@mock.patch.object(seo, "shop_name", lambda lang: "Narjes")
@mock.patch.object(seo, "get_url", lambda: "https://narjes.store")
class TestBreadcrumbLd(unittest.TestCase):
	def test_positions_are_one_based_and_ordered(self):
		node = seo.breadcrumb_ld("ar", [("Home", ""), ("Shop", "/shop")])
		positions = [e["position"] for e in node["itemListElement"]]
		self.assertEqual(positions, [1, 2])
		self.assertEqual(node["itemListElement"][1]["item"], "https://narjes.store/ar/shop")

	def test_empty_returns_none(self):
		self.assertIsNone(seo.breadcrumb_ld("ar", []))


@mock.patch.object(seo, "shop_name", lambda lang: "Narjes")
@mock.patch.object(seo, "get_url", lambda: "https://narjes.store")
class TestItemListLd(unittest.TestCase):
	def test_empty_returns_none(self):
		self.assertIsNone(seo.item_list_ld([], "ar"))

	def test_counts_and_links_every_product(self):
		products = [
			{"title": "A", "route": "/ar/p/a"},
			{"title": "B", "route": "/ar/p/b"},
		]
		node = seo.item_list_ld(products, "ar", path="/shop")
		self.assertEqual(node["numberOfItems"], 2)
		self.assertEqual(
			[e["url"] for e in node["itemListElement"]],
			["https://narjes.store/ar/p/a", "https://narjes.store/ar/p/b"],
		)


class TestPublicFile(unittest.TestCase):
	def test_private_uploads_rejected(self):
		"""A /private/ upload 403s for guests, so it must never be advertised."""
		self.assertIsNone(core.public_file("/private/files/logo.jpg"))

	def test_public_upload_passes_through(self):
		self.assertEqual(core.public_file("/files/logo.jpg"), "/files/logo.jpg")

	def test_empty(self):
		self.assertIsNone(core.public_file(""))
		self.assertIsNone(core.public_file(None))


class TestShopName(unittest.TestCase):
	@mock.patch.object(core, "settings", lambda: {"shop_name_ar": "النرجس"})
	def test_uses_dedicated_field(self):
		self.assertEqual(seo.shop_name("ar"), "النرجس")

	@mock.patch.object(core, "settings", lambda: {"meta_title_ar": "لوحات وإطارات وهدايا تُصنع بعناية"})
	def test_ignores_meta_title(self):
		"""meta_title is a page title, not the brand — it must not leak in."""
		self.assertEqual(seo.shop_name("ar"), "النرجس")

	@mock.patch.object(core, "settings", lambda: {})
	def test_falls_back_per_language(self):
		self.assertEqual(seo.shop_name("ar"), "النرجس")
		self.assertEqual(seo.shop_name("en"), "Narjes Store")


class TestSitemapUrl(unittest.TestCase):
	@mock.patch.object(seo, "get_url", lambda: "https://narjes.store")
	def test_percent_encodes_and_xml_escapes(self):
		"""Frappe's Jinja env has autoescape off, so this must escape itself."""
		self.assertEqual(
			seo._sitemap_url("ar", "/p/ورد"),
			"https://narjes.store/ar/p/%D9%88%D8%B1%D8%AF",
		)


if __name__ == "__main__":
	unittest.main()
