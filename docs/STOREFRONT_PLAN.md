# Narjes Store — Customer Storefront Build Plan (narjes.store)

**Goal.** A public, bilingual, brand-true storefront at `narjes.store` where customers browse
ready-made pieces, request custom designs, and place Cash-on-Delivery orders that land in the
existing ERP as Sales Orders tagged as coming from the website — with everything (products,
prices, images, copy, offers, contact details) controlled from `admin.narjes.store`.

**Where the code lives.** `narjes_custom`. Same Frappe site, same database, same deploy
pipeline (`scripts/deploy_prod.sh`). Zero core edits.

> **Revision 2** — scope cut after the shop's review: no customer accounts (guest checkout
> only), no Kurdish, no Cloudflare, and missing images/prices are handled with graceful
> fallbacks instead of blocking launch. Traffic expectation for year one is **under ~100
> visitors**; the infrastructure step-up is deliberately deferred to next year. Revision 1 is
> in git history.

---

## 0. Ground truth — verified on the live system

| # | Finding | Consequence |
|---|---|---|
| 1 | **`narjes.store` has no DNS record.** Only `admin.narjes.store` → 72.61.87.227 | The one true blocker. Exact records to add: §1 |
| 2 | No Email Account configured | **No longer blocking** — with accounts cut, nothing transactional is required. Staff get in-desk notifications instead. Optional later for order confirmations |
| 3 | 0 of 40 sales items have an image; only 22 have a Standard Selling price | **No longer blocking** — branded placeholder image + "no price yet" state (§W5). Real photos become an ongoing improvement, not a gate |
| 4 | Item Groups are internal (`Raw Material`, `Sub Assemblies`, `Flower Materail` [sic]…) | Needs a customer-facing category tree; internal groups must never leak to the web |
| 5 | Languages `ar`, `en` present | Ship both. Kurdish cut — which also removes the Sorani font-coverage risk entirely |
| 6 | `Customer.portal_users` exists | Not needed now (no logins), but the door stays open for accounts later |
| 7 | `Website Settings.home_page = None`, signup disabled | Root serves nothing yet; signup stays disabled — correct for this scope |
| 8 | Sales Order has no `source` field | Need `custom_order_source` for the website label (§W8) |
| 9 | 1 vCPU / 4 GB, 10 containers | Fine for <100 visitors/year. Build so the step-up is a config change, not a rewrite (§W9) |
| 10 | Instagram (27K): custom art studio — framed pieces, graduation/wedding/Hajj designs, floral, soft palette, orders by DM | Custom-design requests are a **first-class flow**; mobile-first; Instagram is the main inbound channel |

---

## 1. DNS — exactly what to add

Add these two records wherever `narjes.store`'s DNS is managed (likely Hostinger hPanel, since
`admin.narjes.store` already resolves there):

| Type | Name / Host | Value | TTL |
|---|---|---|---|
| `A` | `@` (or `narjes.store`) | `72.61.87.227` | 300 |
| `A` | `www` | `72.61.87.227` | 300 |

Notes:
- Use TTL **300** while launching (fast to correct), raise to 3600 afterwards.
- No `AAAA`, no `CNAME`, no Cloudflare, no nameserver change.
- If any parking/redirect record already exists on `@` or `www`, delete it.
- Leave `admin` untouched — it keeps working exactly as now.
- Don't touch `MX` records; email is unaffected.

**Then tell me it's done.** I verify propagation, add the Traefik router rule for
`narjes.store` + `www.narjes.store`, and issue Let's Encrypt certificates — the same mechanism
already serving `admin.narjes.store`, so no new infrastructure. Port 80/443 are already open,
which is all the certificate challenge needs.

---

## 2. Architecture

**Server-rendered Frappe Website pages in `narjes_custom`, progressively enhanced with a small
client layer (Alpine.js + View Transitions + CSS animation).**

| Option | Verdict |
|---|---|
| **Frappe Website (Jinja) + Alpine** ✅ | Same site/session/DB, no second process, no CORS. Server-rendered = fast on Iraqi mobile and properly indexable (Instagram bio link → product page previews and ranks). Rich animation still fully available. Cheapest on 1 vCPU, and scales next year by adding workers/RAM, not by rewriting |
| Vue/React SPA | Heavier on mobile data, weak link previews without prerendering, more build complexity. Cart/filters/favourites don't need a SPA |
| Separate Next.js app | Another container + process + CORS on a box that already stalled during one Docker build |
| ERPNext `webshop` | ~90% of its templates would be overridden to hit this brand, duplicates Item into Website Item, third upgrade-fragile app. Also carries a login/account model we no longer want |

---

## 3. Phases

### W0 — Domain, routing, safety rails
1. DNS per §1 *(shop's action)*.
2. Traefik: add `Host(narjes.store) || Host(www.narjes.store)` to the existing router; keep
   `admin.narjes.store` for the desk. Same Frappe site.
3. `www` → apex 301; HTTP → HTTPS; Let's Encrypt certs.
4. Frappe `website_route_rules` + `home_page`; `/app` on the public domain redirects to
   `admin.narjes.store` so staff have one entry point.
5. **Storefront kill switch** — `narjes_storefront_enabled` in site_config + branded
   maintenance page. Pull the store without touching the ERP.
6. `noindex` until launch day.

**Done when.** `narjes.store` serves a placeholder storefront over valid TLS, the desk is
untouched, and the kill switch is proven both ways.

### W1 — Storefront design system (extends Narjes Ledger)
- **Palette.** Same `tokens.json` pipeline. Add a storefront set: **Mint `#A2D4C9` promoted to
  hero/brand accent** (it is the logo), **Fern `#2E5C46`** for primary actions, softer/warmer
  Paper grounds than the desk (the brand's own photography is white/pastel), **Saffron** for
  offers/badges, **Stamp** for sale/urgency. Light + dark, both run through
  `scripts/contrast_check.py`.
- **Type.** Fraunces + IBM Plex Sans + IBM Plex Mono + Plex Arabic/Amiri — all already
  self-hosted and sufficient now that Kurdish is out.
- **Patterns** from the three-petal narcissus, extending `vine-*.svg`: petal lattice (dividers),
  bloom scatter (hero/empty states), ink wash (category headers), paper fibre (card grounds).
  Strict placement map so patterns stay seasoning.
- **Placeholder product image** (needed by W4): the narcissus mark on a soft mint→paper wash
  with a subtle petal lattice — one shared asset, in the product-card aspect ratio, so an
  un-photographed catalogue still looks deliberate rather than broken.
- **Loading animation.** Mark self-draws (`stroke-dashoffset`), three petals bloom and settle,
  <900 ms, reduced-motion collapses to a fade.
- **Icons.** Phosphor (`ph-*` sprite already shipped) — add cart, heart, user, search, funnel,
  truck, WhatsApp, Instagram, globe, sun/moon.
- **Motion.** View Transitions between pages, card hover lift, add-to-cart flight, scroll
  reveals, `prefers-reduced-motion` honoured.

**Done when.** A storefront style sheet shows every component in both modes and both languages.

### W2 — Data model
**New doctypes** (all in `narjes_custom`, fixture-exported):
| Doctype | Purpose |
|---|---|
| `Narjes Storefront Settings` (Single) | Brand strings, logo, contact block (phone/WhatsApp/Instagram/address/map/hours), announcement bar, COD copy, default language, maintenance toggle, SEO defaults + OG image, **"reach us" CTA target** |
| `Narjes Storefront Category` | Customer-facing tree (separate from internal Item Groups): per-language name/description, image, order, visibility |
| `Narjes Web Block` | Homepage sections: hero, featured collection, banner, gallery, rich text — typed, ordered, per-language, toggleable |
| `Narjes Product Media` (child) | Ordered image gallery per item + alt text |
| `Narjes Storefront Translation` (child) | Per-language name/short/long description on Item and Category |
| `Narjes Design Request` + `…File` | Custom-design flow (§W6) |
| `Narjes Promotion` | Storefront *presentation* of an offer (badge, banner, landing block). The money stays in ERPNext **Pricing Rule** |

**Custom fields — Item:** `custom_publish_on_website`, `custom_storefront_category`,
`custom_website_title/short_description`, `custom_web_long_description`, `custom_gallery`,
`custom_is_featured`, `custom_web_badge` (New/Best Seller/Limited/Sale), `custom_display_order`,
`custom_web_route`, `custom_made_to_order`, `custom_lead_time_days`.
**Sales Order:** `custom_order_source`, `custom_web_order_ref`.

**Reused, not reinvented:** Item, Item Price, Bin, Pricing Rule, Sales Order, Customer/Contact/
Address, File, Translation.

**No cart/favourite/account doctypes** — with accounts cut, both live entirely in the browser
(§W7). If accounts return later, they become the server-side persistence layer.

**Done when.** An admin can create, categorise, photograph, price, and publish a product with
no developer involved.

### W3 — Bilingual (ar / en), RTL, dark mode
1. **URL strategy**: path prefix — `/ar/...`, `/en/...`; `/` redirects by `Accept-Language`,
   then the Settings default. Shareable, cacheable, correct `hreflang`.
2. `hreflang` + `x-default`; per-language title/meta/OG.
3. **UI strings** → Frappe Translation (fixture-exported). **Content** → per-language child
   rows with an `ar` → `en` fallback so a half-translated catalogue never renders blank.
4. **RTL**: Arabic. Logical properties are already mandated by the theme, so this is an audit —
   but product grid, cart, carousel direction and breadcrumbs each get an explicit pass.
5. Western digits; `148,000 IQD` stays LTR inside RTL text.
6. **Dark mode**: reuse the Paper/Ink mechanism + header toggle persisted in localStorage.

**Done when.** Every page is correct in both languages, both directions, both modes — Arabic
reviewed by a native reader.

### W4 — Catalogue, with graceful gaps
1. **Missing image → shared branded placeholder** (W1). One asset for every item, so the grid
   stays visually coherent. Real photos drop in per item whenever they're taken.
2. **Missing price → "No price yet — reach us"** in place of the amount, with the add-to-cart
   button replaced by a **contact CTA** (WhatsApp/Instagram/phone from Settings). The item is
   still browsable and shareable; it just can't be carted.
3. Customer-facing category tree; map items to it; internal groups stay hidden.
4. Web copy per item (start Arabic; English falls back).
5. **Stock policy per item**: real stock (Bin) vs `custom_made_to_order` with a lead time.
   Product Bundles show the bundle, never its components.
6. Image pipeline: WebP + `srcset` + lazy load + blur-up, resized on upload.

**Done when.** All 40 items are browsable and none looks broken, whether or not it has a photo
or a price.

### W5 — Storefront pages
- **Home**: hero (brand + custom-design CTA), featured collections, new arrivals, offers,
  "how custom orders work", Instagram strip, contact/trust block.
- **Category / all products**: responsive grid, filters (category, price, occasion —
  graduation/wedding/Hajj, matching `design_type`), sort, paging, skeletons.
- **Product**: gallery with zoom, price or the "reach us" state, options, quantity,
  add-to-cart, favourite, delivery estimate by governorate, share, related items, structured data.
- **Search**: debounced instant search across published items, both languages.
- **Content pages**: About, Contact (map, WhatsApp, Instagram, hours), FAQ, Delivery & Returns,
  Privacy, Terms — all editable as Web Blocks.
- **Error/empty states**: branded 404/500, empty cart, empty search, empty favourites.

**Done when.** Any published product is reachable in 3 taps from home, on a phone.

### W6 — Custom design requests (first-class)
1. Guided flow: occasion (graduation / wedding / Hajj / other) → type (canvas, MDF, frame,
   flowers, gift) → size → reference image upload (type/size limited) → notes → name, phone,
   governorate. **No login at any point.**
2. Creates a `Narjes Design Request` with its own desk list/kanban, plus one-click
   **"Convert to Sales Order"** carrying files, notes and customer across.
3. Optional: run the free-text notes through the existing AI intake extraction to pre-fill
   fields — reuses machinery that already exists.
4. Staff notified in-desk (no SMTP needed).

**Done when.** A request submitted on the site appears in the desk with attachments and
converts to a Draft Sales Order in one click.

### W7 — Cart, favourites, guest checkout
**No accounts, no passwords, no email verification.** Identity is captured at checkout only.
1. **Cart and favourites live in `localStorage`** — instant, no server round-trip, no login.
   Cart is validated server-side at checkout (prices, availability, publish status re-checked;
   never trust the client).
2. **Checkout** (single page, no barriers): name, phone, governorate, address, optional notes
   → delivery fee computed by the *existing* server logic (Narjes Settings, Baghdad vs other)
   → order summary → **Cash on Delivery** confirm → success page showing the order reference.
3. **Customer matching**: on submit, find an existing `Customer` by phone (reusing the AI
   intake's matcher) or create one — `channal = Website`, with governorate and address. So
   orders still sit against a real Customer in the ERP, exactly as before; the customer just
   never had to register.
4. **Order lookup without an account** (optional, cheap): a page where order reference + phone
   shows current status. Gives customers tracking with no login.
5. Cart survives refresh and language/theme switches.

**Done when.** A visitor with no account can order end-to-end, and a correctly linked Customer
and Sales Order exist in the ERP.

### W8 — ERP order integration
1. **The label** — `custom_order_source` (Select): `Website / Instagram / WhatsApp / Phone /
   Walk-in / AI Intake`, default `Walk-in`, set to **`Website`** by the storefront. Chosen over
   a free-text tag because it's filterable in the Kanban and reportable in Sales Revenue. Plus
   `custom_web_order_ref` (the public reference shown to the customer).
2. Orders land as **Draft** in Order Phase `New` — COD carries no payment guarantee, so staff
   confirm. Configurable in Settings.
3. Runs through the existing `sales_order_before_validate` / `validate` hooks, so delivery
   fees, flower charges, canvas/sheet costing and governorate logic apply unchanged.
4. **Stock**: the insufficient-stock warning must never reach a customer. Availability is
   checked before accepting; items either block, offer made-to-order, or flag internally per
   `custom_made_to_order`.
5. **Notifications**: in-desk notification + Kanban card for staff. Customer confirmation email
   deferred until an Email Account exists (then it's a small add).
6. Sales Revenue Report gains an Order Source filter/column, so web revenue is measurable from
   day one.

**Done when.** A website order appears in the Kanban as `New`, labelled `Website`, with correct
delivery fee and totals, against a real Customer.

### W9 — Right-sized performance (and next year's headroom)
For <100 visitors this year the box is fine; the work here is to keep it cheap and leave the
step-up easy.
1. Sensible defaults only: Redis caching of catalogue reads, cached nav/category fragments,
   `Cache-Control` + ETags on static assets, compressed and correctly sized images.
2. Budgets (CI-checked, mirroring the theme's): **HTML < 40 KB**, **CSS ≤ 60 KB gz**,
   **JS ≤ 45 KB gz**, hero image < 150 KB, **LCP < 2.5 s on 4G**. These cost nothing to hold
   now and are painful to retrofit later.
3. Rate-limit guest endpoints (abuse protection, not scale).
4. **Documented step-up path for next year**, so growth is a config change: put a CDN in front,
   raise gunicorn workers, add RAM/vCPU, and split the storefront onto its own container if the
   ERP and store ever contend. No rewrite required — that's why the architecture in §2 was chosen.

**Done when.** Budgets pass and the step-up path is written down.

### W10 — Security, SEO
1. **Security**: guest endpoints whitelisted narrowly and field-allowlisted — **never expose
   `valuation_rate`, `last_purchase_rate`, supplier or cost fields**; CSRF on; rate-limited
   order/request submission; upload type/size limits; no PII in URLs. *Cutting accounts removes
   the entire credential-handling attack surface* — no password storage, no session hijacking,
   no reset-token abuse.
2. **Privacy**: privacy/terms/returns as managed content; state plainly what is stored
   (name, phone, address for delivery). No cookie banner needed if no third-party analytics.
3. **SEO**: per-language `sitemap.xml`, `robots.txt`, canonical + `hreflang`, Product/Offer/
   Organization/BreadcrumbList structured data, OG/Twitter cards (Instagram/WhatsApp link
   previews matter more here than search), readable slugs.
4. **Analytics**: optional and lightweight; can wait until traffic justifies it.

**Done when.** A security review of every guest endpoint passes, and a product URL previews
correctly when pasted into Instagram and WhatsApp.

### W11 — QA & launch
1. **QA matrix**: 2 languages × 2 directions × 2 modes × {390 px, tablet, desktop} across the
   route list (Appendix A), plus keyboard pass and the contrast script.
2. **End-to-end**: browse → cart → checkout → Sales Order in ERP → correct totals; custom
   design → desk → converted SO; missing-image and missing-price states; cart persistence.
3. **Pilot**: staff + a few real customers place live orders before announcing.
4. **Launch**: remove `noindex`, smoke-test, then announce on Instagram. Kill switch is the
   rollback.
5. **Handover**: `STOREFRONT.md` — how to add a product, change content, run an offer, read
   orders — plus a short Arabic-annotated staff guide.

**Done when.** Live for a week with no P1s and staff trained.

---

## 4. Sequencing

| Phase | Focus | Est. |
|---|---|---|
| W0 | Domain, routing, kill switch | 0.5 wk *(gated by DNS)* |
| W1 | Design system, patterns, placeholder, loader | 1.5 wk |
| W2 | Data model + admin control | 1 wk |
| W3 | ar/en, RTL, dark mode | 0.5 wk |
| W4 | Catalogue + graceful gaps | 0.5 wk |
| W5 | Storefront pages | 2 wk |
| W6 | Custom design requests | 1 wk |
| W7 | Cart, favourites, guest checkout | 1 wk |
| W8 | ERP order integration | 0.5 wk |
| W9 | Performance right-sizing | 0.25 wk |
| W10 | Security, SEO | 0.5 wk |
| W11 | QA & launch | 0.75 wk |
| **Total** | | **≈ 10 wk**, and now genuinely unblocked — only DNS gates the start |

**Milestones.** M1 domain live + design system signed off · M2 catalogue browsable ·
M3 first end-to-end web order in the ERP · M4 public launch.

---

## 5. Risk register

| # | Risk | Mitigation |
|---|---|---|
| 1 | DNS not pointed | §1 — the only true blocker; two records |
| 2 | Catalogue looks empty/unfinished without photos | Shared branded placeholder + "reach us" price state; photos improve it incrementally |
| 3 | No email means no customer order confirmation | Order reference shown on screen + optional phone-based lookup; SMTP is a small later add |
| 4 | COD prank/fraud orders | Draft-first (staff confirm), phone captured, rate limiting; phone OTP available later if abused |
| 5 | Web orders bypass staff stock knowledge | Made-to-order flags + availability check before accepting |
| 6 | Cost/valuation leaking through guest APIs | Field-allowlisted endpoints; explicit review of every `allow_guest` method |
| 7 | Traffic grows faster than expected | W9 step-up path written in advance; architecture chosen so it's config, not rewrite |
| 8 | localStorage cart lost when the customer switches device | Accepted for v1 (no accounts). Server-side carts are the natural first feature if accounts return |
| 9 | Scope creep (payments, accounts, loyalty) | Explicitly out of scope — §6 |

---

## 6. Explicitly out of scope for v1

Customer accounts/login, online payment (COD only, modelled for extension), delivery tracking,
loyalty, reviews/ratings, multi-vendor, native app, abandoned-cart automation, Kurdish, CDN.
Each is a clean follow-on.

---

## Appendix A — Route map (also the QA matrix)

`/{lang}/` home · `/{lang}/shop` · `/{lang}/c/{category}` · `/{lang}/p/{slug}` ·
`/{lang}/search` · `/{lang}/cart` · `/{lang}/checkout` · `/{lang}/order/{ref}` confirmation ·
`/{lang}/order-status` lookup · `/{lang}/custom-design` · `/{lang}/favorites` ·
`/{lang}/about` · `/{lang}/contact` · `/{lang}/faq` · `/{lang}/delivery-returns` ·
`/{lang}/privacy` · `/{lang}/terms` · `404` · `500` · `/sitemap.xml` · `/robots.txt`

Each × {ar, en} × {light, dark} × {390 px, tablet, desktop}.

## Appendix B — Definition of done

1. Every Appendix A route passes in 2 languages, 2 directions, 2 modes, 3 widths.
2. A visitor with no account can order end-to-end; the ERP shows a `Website`-labelled Draft
   Sales Order against a correctly matched/created Customer, with correct delivery fee.
3. A custom design request converts to a Sales Order in one click, with files intact.
4. Items with no image and no price still render correctly and offer a contact path.
5. Admin can change any product, price, image, category, offer or contact detail without a
   developer.
6. Contrast and size budgets green and committed.
7. Security review of all guest endpoints signed off; no cost data exposed.
8. Arabic reviewed by a native reader.
9. Kill switch and rollback rehearsed.
