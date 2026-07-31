# Narjes Store — Customer Storefront Build Plan (narjes.store)

**Goal.** A public, multilingual, brand-true storefront at `narjes.store` where customers
browse ready-made pieces, request custom designs, and place Cash-on-Delivery orders that land
in the existing ERP as Sales Orders tagged as coming from the website — with everything
(products, prices, stock, images, copy, offers, contact details) controlled from
`admin.narjes.store`.

**Where the code lives.** `narjes_custom`. Same Frappe site, same database, same deploy
pipeline (`scripts/deploy_prod.sh`). Zero core edits — the rule from the theme build holds.

---

## 0. Ground truth — verified on the live system, not assumed

Checked against production before writing this plan. These findings shape everything below.

| # | Finding | Consequence |
|---|---|---|
| 1 | **`narjes.store` has no DNS record.** Only `admin.narjes.store` → 72.61.87.227 | Domain + TLS + Traefik routing is a prerequisite task (W1), not an afterthought |
| 2 | **No Email Account is configured** (`Email Account` table empty) | **Hard blocker** for signup verification, password reset, and order emails. Must be solved before accounts ship |
| 3 | **0 of 40 sales items have an image**; only 22 have a Standard Selling price | **The real launch bottleneck is content, not code.** A storefront with no photos cannot open |
| 4 | Item Groups are internal (`Raw Material`, `Sub Assemblies`, `Consumable`, `Flower Materail` [sic], `Products`, `Services`) | Needs a customer-facing category tree; internal groups must never leak to the web |
| 5 | Languages `ar`, `en`, `ku` exist; `ckb` does not | Kurdish ships as `ku`; must confirm Sorani vs Kurmanji and font glyph coverage |
| 6 | `Customer.portal_users` exists | Clean, supported Website User ↔ Customer link — no invented linkage needed |
| 7 | `Website Settings.disable_signup = 1`, `home_page = None` | Signup is currently OFF; root serves nothing |
| 8 | Sales Order has **no** `source` field | Need a custom field for the "came from website" label (§6) |
| 9 | Server is **1 vCPU / 4 GB**, already running 10 containers | Public traffic shares the box with the ERP. Performance is a design constraint, not a polish item (§10) |
| 10 | Instagram (27K followers) = custom art studio: framed pieces, graduation/wedding/Hajj designs, floral, soft palette; orders arrive by DM | Custom-design requests are a **first-class flow**, and the site must be mobile-first with Instagram as its main inbound channel |

---

## 1. Architecture decision

**Recommendation: server-rendered Frappe Website pages in `narjes_custom`, progressively
enhanced with a small client layer (Alpine.js + View Transitions + CSS animation).**

Why this over the alternatives:

| Option | Verdict |
|---|---|
| **Frappe Website (Jinja) + Alpine** ✅ | Same site/session/DB — no CORS, no second process, no extra RAM. Server-rendered = fast first paint on Iraqi mobile and genuinely indexable (critical: Instagram bio link → product pages must preview and rank). Rich animation is still fully available. Cheapest option on 1 vCPU. |
| Vue/React SPA (Frappe UI) | Better for app-like dashboards, worse here: heavier bundle on mobile data, weak SEO/link previews without extra prerendering, more build complexity. The interactivity they want (cart, filters, favourites) does not need a SPA. |
| Separate Next.js app | Needs another container + Node process + CORS + a second deploy path on a box that already fell over during one Docker build. Rejected on infrastructure grounds. |
| ERPNext `webshop` app | Gives cart/wishlist/checkout free, but its Bootstrap templates would be ~90% overridden to hit this brand, it duplicates Item into Website Item, and it is a third app to keep upgrade-safe. Rejected — we already own a design system and a custom app. |

**"Modern and interactive" is delivered by** the View Transitions API for page changes,
scroll-driven reveal animations, optimistic cart/favourite updates via `fetch`, skeleton
loaders, and the motion catalogue we already built (`narjes.motion.*`) — not by shipping a SPA.

---

## 2. Phases

Each phase: **Goal → Tasks → Done when.** W0–W4 are foundations, W5–W9 the store itself,
W10–W12 quality and launch.

### W0 — Prerequisites & decisions (blocking)
**Goal.** Remove the three things that can stall everything else.
1. **DNS**: point `narjes.store` + `www` A records at 72.61.87.227. Decide apex vs www canonical (recommend apex).
2. **Email**: create an outgoing Email Account (recommend a dedicated transactional sender —
   Zoho/Brevo/SES — not a personal Gmail, which throttles and lands in spam). Verify SPF +
   DKIM + DMARC on `narjes.store`. **Nothing account-related can be tested until this exists.**
3. **Cloudflare** (free tier) in front: DNS, TLS, caching, image resizing, bot protection.
   This is how a 1 vCPU box survives an Instagram-story traffic spike.
4. **Content owner + deadline** for photographing the catalogue (§W5). Assign a person.
5. Confirm Kurdish variant (Sorani expected) and supply 2–3 sample sentences for font checking.

**Done when.** `narjes.store` resolves and terminates TLS, a test email is received in an
inbox (not spam), and someone owns the photo shoot with a date.

### W1 — Routing, environment, safety rails
**Goal.** One site, two faces, no accidents.
1. Traefik: add `Host(narjes.store) || Host(www.narjes.store)` to the existing router; keep
   `admin.narjes.store` for the desk. Same Frappe site — no second instance.
2. `www` → apex 301. HTTP → HTTPS. HSTS.
3. Frappe: `website_route_rules` for storefront paths; `home_page` = storefront home.
   Ensure `/app` on the public domain redirects to `admin.narjes.store` (staff-only entry).
4. **Storefront kill switch** — `narjes_storefront_enabled` in site_config + a maintenance
   page, mirroring the theme's kill switch. Lets us pull the store without touching the ERP.
5. Staging: `beta.narjes.store` pointing at the same site with the storefront enabled but
   `noindex`, so the store can be reviewed before the apex goes live.

**Done when.** `narjes.store` serves a placeholder storefront page, `admin.narjes.store`
still serves the desk, and the kill switch is proven both ways.

### W2 — Storefront design system (extends Narjes Ledger)
**Goal.** A retail-facing layer on the tokens we already have — airy and romantic per the
brand's own photography, not the dense ledger look of the admin.

- **Palette.** Keep the token pipeline (`tokens.json` → generated CSS). Add a `storefront`
  token set: **Mint `#A2D4C9` promoted to hero/brand accent** (it is the logo), **Fern
  `#2E5C46`** for primary actions, **Paper/Blush** grounds (softer and warmer than the desk's
  `#F2F4F1` — the Instagram aesthetic is white/pastel), **Saffron** for offers/badges,
  **Stamp** for sale/urgency. Both light and dark, both contrast-checked by the existing
  `scripts/contrast_check.py` (extended to cover storefront pairings).
- **Type.** Fraunces (display) + IBM Plex Sans (body) + IBM Plex Mono (prices/IDs) are already
  self-hosted. Add **Kurdish/Arabic coverage verification** — IBM Plex Sans Arabic must be
  checked for Sorani letters (ڕ ڵ ۆ ێ چ گ ژ پ); if it fails, add Noto Naskh Arabic or
  Vazirmatn for `ku`. **This is a real risk — verify with actual Kurdish strings.**
- **Patterns** (new, derived from the three-petal narcissus, extending `vine-*.svg`):
  1. *Petal lattice* — interlocking arcs, section dividers.
  2. *Bloom scatter* — sparse blooms, hero/empty states.
  3. *Ink wash* — soft mint→paper gradient mesh, category headers.
  4. *Paper fibre* — subtle texture, product-card grounds.
  Strict placement map like the theme's, so patterns stay seasoning.
- **Loading animation.** The narcissus mark self-draws (`stroke-dashoffset`), then the three
  petals bloom outward and settle — under 900 ms, reduced-motion collapses to a fade.
- **Icons.** Phosphor throughout (`ph-*` sprite already shipped) — extend with
  `shopping-cart-simple`, `heart`, `user-circle`, `magnifying-glass`, `funnel-simple`,
  `truck`, `whatsapp-logo`, `instagram-logo`, `globe`, `sun`/`moon`.
- **Motion.** Page changes via View Transitions; card hover lift; add-to-cart flies to the cart
  icon; scroll-reveal on section entry; `prefers-reduced-motion` honoured everywhere.

**Done when.** A storefront style sheet (extending the Ledger sheet) shows every component,
both modes, all three languages, signed off.

### W3 — Data model
**Goal.** Everything the shop can change lives in the admin, and nothing is hard-coded.

**New doctypes** (all in `narjes_custom`, all fixture-exported):
| Doctype | Purpose |
|---|---|
| `Narjes Storefront Settings` (Single) | Brand strings, logo, contact block (phone/WhatsApp/Instagram/address/map/hours), social links, announcement bar, COD copy, default language, maintenance toggle, SEO defaults + OG image |
| `Narjes Storefront Category` | Customer-facing tree (separate from internal Item Groups), with per-language name/description, image, sort order, visibility |
| `Narjes Web Block` | Homepage/landing sections: hero, featured collection, banner, testimonial, gallery, rich text — typed, ordered, per-language, toggleable |
| `Narjes Product Media` (child) | Ordered image gallery per item, with alt text |
| `Narjes Storefront Translation` (child) | Per-language name/short/long description, attached to Item and Category |
| `Narjes Cart` + `Narjes Cart Item` | Server-side cart for logged-in customers (guests use localStorage; merged on login) |
| `Narjes Favorite` | Wishlist rows (customer + item) |
| `Narjes Design Request` + `Narjes Design Request File` | The custom-design flow (§7) |
| `Narjes Promotion` | Storefront *presentation* of an offer (badge, banner, countdown, landing block) — the money itself stays in ERPNext **Pricing Rule** |

**Custom fields on existing doctypes:**
- **Item**: `custom_publish_on_website` (Check), `custom_storefront_category` (Link),
  `custom_website_title/short_description` , `custom_web_long_description` (Text Editor),
  `custom_gallery` (Table → Narjes Product Media), `custom_is_featured`, `custom_web_badge`
  (Select: New / Best Seller / Limited / Sale), `custom_display_order`, `custom_web_route`,
  `custom_made_to_order` (Check — sells without stock), `custom_lead_time_days`.
- **Sales Order**: `custom_order_source` (§6).
- **Customer**: reuse existing `main_phone_number`, `governorate`, `full_address`, `channal`.

**Reused, deliberately not reinvented:** Item + Item Price (pricing), Bin (stock),
Pricing Rule (discounts/offers), Sales Order (orders), Customer/Contact/Address/Portal User
(accounts), File (uploads), Translation (UI strings).

**Done when.** An admin can create a product, categorise it, add photos, set a price, publish
it, and see it appear on a page — with no developer involved.

### W4 — Internationalisation (ar / en / ku), RTL, dark mode
**Goal.** Three languages as first-class, two of them right-to-left.
1. **URL strategy**: path prefix — `/ar/...`, `/en/...`, `/ku/...`, with `/` redirecting to the
   visitor's best match (`Accept-Language`, then default from Settings). Prefixes are
   shareable, cacheable, and give correct `hreflang` — a cookie-only switch is none of those.
2. `hreflang` + `x-default` tags on every page; per-language `<title>`/meta/OG.
3. **UI strings** → Frappe Translation (fixture-exported). **Content** → per-language child
   rows, with a documented fallback chain (`ku` → `ar` → `en`) so a half-translated catalogue
   never renders blank.
4. **RTL**: `ar` and `ku` both RTL. The theme already mandates CSS logical properties, so this
   is an audit, not a rewrite — but the storefront layouts (product grid, cart, carousel
   direction, breadcrumbs) each need an explicit RTL pass.
5. **Numerals**: Western digits, IQD formatting `148,000 IQD` staying LTR inside RTL text.
6. **Dark mode**: reuse the Paper/Ink mechanism, `prefers-color-scheme` + a header toggle
   persisted in localStorage (and on the User for logged-in customers).

**Done when.** Every page renders correctly in all three languages, both directions, both
modes — verified by a native reader for `ar` and `ku`.

### W5 — Catalogue & merchandising ← *the critical-path phase*
**Goal.** Turn 40 internal item records into a shoppable catalogue.
1. **Photography**: every published item needs ≥1 clean image (ideally 3: hero, detail, in
   context). *This is the schedule driver — code will be ready before the photos are.*
2. Customer-facing category tree; map items to it; internal groups stay hidden.
3. Per-item web copy in 3 languages (start with `ar`, fall back for the rest).
4. Prices: fill the 18 items missing a Standard Selling price, or exclude them from the web.
5. **Stock policy per item**: real stock (from Bin) vs made-to-order. Ready-made pieces show
   availability; custom/framed work sells as made-to-order with a lead time. Product Bundles
   must show the bundle, never its components.
6. Image pipeline: WebP + responsive `srcset` + lazy loading + blur-up placeholder.
   Cloudflare Images or a local resize-on-upload hook.

**Done when.** Every published product has an image, a price, a category, and Arabic copy.

### W6 — Storefront pages & the browse experience
**Goal.** The public site.
- **Home**: hero (brand + custom-design call to action), featured collections, new arrivals,
  offers, "how custom orders work", Instagram strip, trust/contact block.
- **Category / all products**: responsive grid, filters (category, price, occasion —
  graduation/wedding/Hajj, matching `design_type`), sort, infinite scroll or paging, skeletons.
- **Product page**: gallery with zoom, price (+ compare-at when discounted), options
  (size/frame/colour where modelled), quantity, add-to-cart, favourite, delivery estimate by
  governorate, share, related items, structured data.
- **Search**: instant search with debounce over published items (name + tags, all languages).
- **Static/content pages**: About, Contact (map, WhatsApp, Instagram, hours), FAQ, Delivery &
  Returns, Privacy, Terms — all editable as Web Blocks.
- **Error/empty states**: branded 404/500, empty cart, empty search, empty favourites.

**Done when.** A visitor can find any published product in 3 taps from the home page, on a phone.

### W7 — Custom design requests (a first-class path)
**Goal.** Match how this business actually sells — "transform your ideas into unique pieces".
1. A guided request flow: occasion (graduation / wedding / Hajj / other) → type (canvas, MDF,
   frame, flowers, gift) → size → reference image upload (multi-file, size/type limited) →
   notes → contact + governorate.
2. Guests may *start* a request; login required to submit (same rule as checkout).
3. Creates a `Narjes Design Request` visible in the desk, with its own list/kanban view, and a
   one-click **"Convert to Sales Order"** that carries files, notes, and the customer across.
4. Optional: route the free-text notes through the existing AI intake extraction to pre-fill
   fields — reuses machinery that already exists.
5. Customer sees request status in their account.

**Done when.** A request submitted on the site appears in the desk with its attachments and
converts to a Draft Sales Order in one click.

### W8 — Accounts, cart, favourites, checkout
**Goal.** Browse freely; identify only when ordering.
1. **Guest browsing** everywhere. Cart and favourites work signed-out via localStorage.
2. **Login/Signup** (branded, per W2): email + password, with phone + governorate captured at
   signup. On signup: create `User` (Website User) → `Customer` (with `main_phone_number`,
   `governorate`, `channal` = Website) → `Contact` → link via `Customer.portal_users`. All in
   one atomic server method, idempotent, with a clear duplicate-email path.
3. **Password reset** via Frappe's built-in flow, branded email template (W0 dependency).
4. **Login prompt appears at checkout only** — never blocks browsing. Guest cart merges into
   the account cart on login (union, quantities summed, no silent loss).
5. **Checkout**: address + governorate → delivery fee computed by the *existing* server logic
   (Narjes Settings; Baghdad vs other) → order summary → COD confirmation → success page with
   order number. Single payment method: **Cash on Delivery**, modelled so other methods can be
   added later without redesign.
6. **Account area**: my orders (with live Order Phase), order detail, design requests,
   favourites, addresses, profile, language/theme preference.

**Done when.** A new customer can register, order, and see the order in their account — and
that customer exists in the ERP with a correctly linked Sales Order.

### W9 — Order integration into the ERP
**Goal.** Web orders behave exactly like staff-entered ones, but are identifiable.
1. **The label** — add `custom_order_source` (Select) on Sales Order:
   `Website / Instagram / WhatsApp / Phone / Walk-in / AI Intake`, default `Walk-in`, set to
   **`Website`** by the storefront. Chosen over a free-text tag because it is filterable,
   reportable, and groupable in the existing Kanban and Sales Revenue Report. Also store
   `custom_web_order_ref` (public order number shown to the customer).
2. Orders are created as **Draft** with Order Phase `New`, so staff confirm before commitment —
   COD with no payment guarantee makes auto-submit unwise. Configurable in Settings.
3. Runs through the existing `sales_order_before_validate` / `validate` hooks, so delivery
   fees, flower charges, canvas/sheet costing and governorate logic all apply unchanged.
4. **Stock**: the new insufficient-stock warning must never `msgprint` at a customer. Web
   orders check availability *before* accepting, and either block, offer made-to-order, or flag
   internally — decided per item by `custom_made_to_order`.
5. Notifications: order confirmation email to the customer; new-order alert to staff
   (email and/or a desk notification).
6. Reporting: Sales Revenue Report gains an Order Source filter/column so web revenue is
   measurable from day one.

**Done when.** A website order appears in the Kanban as `New`, labelled `Website`, with correct
delivery fee and totals, and the customer receives a confirmation email.

### W10 — Performance, caching, and surviving a traffic spike
**Goal.** A 1 vCPU box serving both an ERP and a public store.
1. **Cloudflare** proxying: cache static assets aggressively, HTML at the edge where safe,
   image resizing/WebP, Brotli, "Under Attack" available as an emergency lever.
2. Frappe-side: Redis page/API caching for catalogue reads, cached category/nav fragments,
   `Cache-Control` headers, ETags.
3. Budgets (CI-checked, mirroring the theme's): **HTML < 40 KB**, **CSS ≤ 60 KB gz**,
   **JS ≤ 45 KB gz**, **LCP < 2.5 s on 4G**, hero image < 150 KB. Lighthouse ≥ 90
   performance/accessibility/SEO on mobile.
4. Guest API endpoints rate-limited; product queries indexed and field-restricted.
5. **Load test before launch** at ~50 concurrent users, and decide then whether the VPS needs
   an upgrade. Given the box already stalled during one Docker build, treat a 2 vCPU / 8 GB
   upgrade as *likely* rather than optional before promoting the store on Instagram.

**Done when.** Budgets pass, a load test is green, and there is a written spike playbook.

### W11 — Security, privacy, SEO, analytics
1. **Security**: guest endpoints whitelisted narrowly and field-restricted — **never expose
   `valuation_rate`, `last_purchase_rate`, supplier, or cost fields**; CSRF on, strong password
   policy, rate-limited login/signup/order, file-upload type/size limits, no PII in URLs,
   dependency and permission review of every `allow_guest` method.
2. **Privacy**: privacy policy + terms + returns as managed content; explain what is stored;
   cookie banner only if analytics require it (prefer analytics that don't).
3. **SEO**: per-language `sitemap.xml`, `robots.txt`, canonical + `hreflang`, Product/Offer/
   Organization/BreadcrumbList structured data, OG/Twitter cards (Instagram link previews
   matter more than search here), human-readable slugs.
4. **Analytics**: Cloudflare Web Analytics or GA4 — track product views, add-to-cart, checkout
   funnel, custom-design submissions, and language/mode usage.

**Done when.** A security review passes, a product URL previews correctly when pasted into
Instagram/WhatsApp, and the funnel is measurable.

### W12 — QA, pilot, launch
1. **QA matrix**: 3 languages × 2 directions × 2 modes × {mobile 390, tablet, desktop} across
   the route list (Appendix A), plus keyboard/screen-reader passes and the contrast script.
2. **End-to-end tests**: browse → cart → signup → checkout → order in ERP → status visible;
   custom design → desk → converted SO; password reset; guest-cart merge.
3. **Pilot**: staff + ~10 real customers on `beta.narjes.store` for a week; log issues by
   severity; fix P1s.
4. **Launch**: point DNS, warm caches, smoke-test, announce on Instagram *after* the site has
   held steady for 24 h. Kill switch is the rollback.
5. **Handover**: `STOREFRONT.md` (how to add a product, change content, run an offer, read the
   funnel) + a short Arabic-annotated staff guide.

**Done when.** Live for one week with no P1s, staff trained, docs merged.

---

## 3. Sequencing & realistic timing

| Phase | Focus | Est. |
|---|---|---|
| W0 | Prereqs: DNS, email, Cloudflare, content owner | 0.5 wk *(mostly the shop's action)* |
| W1 | Routing, kill switch, staging | 0.5 wk |
| W2 | Storefront design system, patterns, loader | 1.5 wk |
| W3 | Data model + admin control surfaces | 1 wk |
| W4 | i18n, RTL, dark mode | 1 wk |
| W5 | **Catalogue content** | *shop-dependent — start now* |
| W6 | Storefront pages & browse | 2 wk |
| W7 | Custom design requests | 1 wk |
| W8 | Accounts, cart, favourites, checkout | 1.5 wk |
| W9 | ERP order integration | 0.5 wk |
| W10 | Performance & caching | 0.5 wk |
| W11 | Security, SEO, analytics | 0.5 wk |
| W12 | QA, pilot, launch | 1 wk |
| **Total** | | **≈ 11.5 wk of build**, less with parallelism — **but gated by W0 and W5** |

**Milestones.** M1 domain live + design system signed off (W2) · M2 catalogue browsable
(W6) · M3 first end-to-end web order in the ERP (W9) · M4 public launch (W12).

---

## 4. Risk register

| # | Risk | Mitigation |
|---|---|---|
| 1 | **No product photography** — 0/40 items have images | Start the shoot in W0, before any code needs it. Nothing launches without it |
| 2 | **No SMTP** blocks accounts entirely | W0 blocker; use a real transactional provider with SPF/DKIM |
| 3 | **1 vCPU shared with the ERP**; an Instagram spike could take down *both* | Cloudflare edge caching, budgets, load test, plan a VPS upgrade before promotion |
| 4 | Kurdish glyph coverage in current fonts | Verify with real Sorani strings in W2; add a Kurdish-capable face if needed |
| 5 | Two RTL languages, one LTR | Logical properties already mandated; explicit RTL pass per layout; native review |
| 6 | Cost/valuation data leaking through guest APIs | Field-allowlisted endpoints; explicit security review of every `allow_guest` |
| 7 | COD fraud / prank orders | Draft-first (staff confirm), phone capture, rate limiting, optional phone/OTP later |
| 8 | Web orders bypass staff stock knowledge | Made-to-order flags + availability check before accepting |
| 9 | Prices/stock drift between web and ERP | Single source of truth (Item Price / Bin) read live and cached briefly — never duplicated |
| 10 | Scope creep (payments, delivery tracking, loyalty) | Explicitly out of scope for v1 — see §5 |

---

## 5. Explicitly out of scope for v1

Online payment (COD only, modelled for later extension), delivery-driver tracking, loyalty
points, product reviews/ratings, multi-vendor, a native mobile app, and abandoned-cart
automation. Each is a clean follow-on once v1 is stable.

---

## Appendix A — Route map (also the QA matrix)

`/{lang}/` home · `/{lang}/shop` all products · `/{lang}/c/{category}` · `/{lang}/p/{slug}`
product · `/{lang}/search` · `/{lang}/cart` · `/{lang}/checkout` · `/{lang}/order/{ref}`
confirmation · `/{lang}/custom-design` · `/{lang}/account` (+ `/orders`, `/orders/{id}`,
`/requests`, `/favorites`, `/addresses`, `/profile`) · `/{lang}/login` · `/{lang}/signup` ·
`/{lang}/forgot-password` · `/{lang}/about` · `/{lang}/contact` · `/{lang}/faq` ·
`/{lang}/delivery-returns` · `/{lang}/privacy` · `/{lang}/terms` · `404` · `500` ·
`/sitemap.xml` · `/robots.txt`

Each × {ar, en, ku} × {light, dark} × {390 px, tablet, desktop}.

## Appendix B — Definition of done

1. Every Appendix A route passes in 3 languages, 2 directions, 2 modes, 3 widths.
2. A real customer can register → order → see status; the ERP shows a `Website`-labelled
   Sales Order with correct delivery fee and totals.
3. A custom design request converts to a Sales Order in one click, with files intact.
4. Admin can change any product, price, image, category, offer, or contact detail without a
   developer.
5. Contrast, Lighthouse, and size budgets are green and committed.
6. Security review of all guest endpoints signed off; no cost data exposed.
7. Native `ar` and `ku` readers sign off on copy and layout.
8. Kill switch and rollback rehearsed on staging.
