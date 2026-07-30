# Narjes Ledger — P0 Audit & Baseline

Extracted from the running bench on 2026-07-30. This file is the source of truth
the theme's variable maps, icon pipeline, and dark-mode plumbing are built from
(plan P0). Re-run the extraction after every `bench update` (see UPGRADE_NOTES.md).

## 1. Versions & core integrity

| App | Version | Branch | Core diff vs upstream tag |
|---|---|---|---|
| frappe | v16.20.0 | version-16 | **clean** (`git status` + `git diff v16.20.0` empty) |
| erpnext | v16.21.1 | version-16 | **clean** (`git diff v16.21.1` empty) |
| narjes_custom | 0.0.1 | — | our app |
| frappe_desk_theme | 1.1.0 | main | third-party desk theme — **conflicts with Narjes Ledger** |

§14.1 asset-layer gate: **passes** — no hand-edited core scss/js/icons. Nothing to
revert before P4.

**frappe_desk_theme decision:** uninstalled from the site as part of P3. It injects
its own CSS/JS on desk *and* web (`app_include_css/web_include_css` with
timestamp cache-busters) and was only enabled as a stop-gap while the Narjes desk
reskin was switched off (see the old hooks.py comment). Narjes Ledger becomes the
single styling authority. Rollback: `bench --site narjes.local install-app
frappe_desk_theme` — the app stays in `apps/`.

## 2. Dark mode & theme switcher (v16.20 exact behavior)

- Switcher: `frappe/public/js/frappe/ui/theme_switcher.js`. Themes enumerated in
  `fetch_themes()`, hard-coded: `light` ("Frappe Light"), `dark` ("Timeless
  Night"), `automatic` ("Automatic").
- On switch: `<html data-theme-mode="light|dark|automatic">` is set, then
  `frappe.ui.set_theme()` resolves `automatic` via
  `matchMedia("(prefers-color-scheme: dark)")` and sets the **effective**
  attribute: `<html data-theme="light|dark">`.
- Therefore the theme's dark selector is **`[data-theme="dark"]`** (in built CSS
  it appears unquoted: `[data-theme=dark]`, 61 blocks in desk.bundle). Light is
  `:root, [data-theme="light"]`.
- Server persistence: `frappe.core.doctype.user.user.switch_theme` (User.desk_theme).
- Relabeling to "Paper"/"Ink"/"Auto" = JS shim on
  `ThemeSwitcher.prototype.fetch_themes` (SHIM_REGISTRY row 2).

## 3. CSS variable surface (Lever 1 targets)

Sources:
- `apps/frappe/frappe/public/scss/common/css_variables.scss` — 111 semantic vars
  (surfaces, controls, buttons, alerts, icon fill/stroke, navbar, modal, toast,
  scrollbar, checkbox, awesomebar…).
- `apps/frappe/frappe/public/scss/desk/css_variables.scss` — 33 desk vars
  (breakpoints, page head, datepicker, timeline, skeleton, list row…).
- Ramps (defined in scss, confirmed in built `desk.bundle.*.css`):
  `--gray|green|red|orange|yellow|blue|cyan|teal|purple|pink` each as bare +
  `-50…-900`, plus `--primary`, `--primary-color`.
- Dark theme: `desk/dark.scss`, imported by `desk/variables.scss` (line 135) into
  the same desk bundle under `[data-theme="dark"]`.

Key semantic vars the map file must own (light + dark):
`--bg-color, --fg-color, --card-bg, --control-bg, --control-bg-on-gray,
--disabled-control-bg, --modal-bg, --popover-bg, --toast-bg, --navbar-bg,
--fg-hover-color, --subtle-accent, --subtle-fg, --border-color,
--dark-border-color, --table-border-color, --border-primary, --primary,
--primary-color, --btn-primary, --btn-default-bg, --btn-default-hover-bg,
--btn-ghost-hover-bg, --sidebar-select-color, --awesomebar-focus-bg,
--awesomplete-hover-bg, --scrollbar-thumb-color, --scrollbar-track-color,
--icon-stroke, --icon-fill, --icon-fill-bg, --placeholder-color,
--disabled-text-color, --highlight-color, --yellow-highlight-color,
--alert-text/bg-{success,info,warning,danger}, --text-on-{color},
--bg-{color}, --checkbox-*, --skeleton-bg, --date-active-*, --timeline-badge-*,
--shadow-*, --code-block-bg/text, --diff-*` — full inventory greppable from the
two scss files above.

Text color note: `--text-color`, `--text-muted`, `--text-light`,
`--heading-color` live in bootstrap-layer variables (`desk/variables.scss`) as
SCSS, but are *also* emitted as CSS custom properties in the built bundle —
remap them like the rest.

## 4. Icon system

- Frappe v16 ships three sprites via its own `app_include_icons`:
  `icons/lucide/icons.svg` (1625 symbols, ids `icon-*`),
  `icons/timeless/icons.svg` (5 legacy ids), `icons/espresso/icons.svg`
  (274 symbols, ids `es-line-*` / `es-solid-*`). `frappe.utils.icon()` renders
  `es-icon es-line` classed `<use>` refs for espresso names.
- narjes_custom already ships an **additive Phosphor sprite**
  (`public/icons/phosphor/icons.svg`, 46 symbols, ids `ph-*`) through the same
  supported `app_include_icons` hook, plus a `narjes_icon()` JS helper.
  **Decision:** keep the additive-sprite approach (no DOM sprite-swap shim
  needed — Appendix C's swap pipeline is replaced by this simpler supported
  mechanism); extend the sprite with the Appendix C vocabulary; restyle stock
  `es-line-*`/lucide glyph *colors* via `--icon-stroke/--icon-fill` (Lever 1).

## 5. Build conventions

- Entries: `public/*.bundle.scss` / `public/*.bundle.js` → `bench build --app
  narjes_custom`; dev: `bench watch`. esbuild 0.14.54; hashed output +
  `sites/assets/assets.json` mapping; hooks reference bundles by name
  (`"narjes.bundle.css"`), raw files by `/assets/...` path.
- RTL: Frappe auto-builds `css-rtl/` twins of every css bundle (rtlcss) — free
  coverage for P10, provided we use logical properties for anything it can't flip.
- Frappe's own bundles: desk, login, website, email, print, print_format, report,
  web_form.

## 6. Prior custom UI inventory (absorb decisions)

| Asset | Decision |
|---|---|
| `public/css/theme/tokens.css` (`--narjes-*`, both modes) | **Absorb**: superseded by generated `_tokens.scss`; a `_compat.scss` keeps every `--narjes-*` name alive as an alias of the new `--n-*` tokens so existing pages don't break. Removed from hooks. |
| `public/css/theme/components.css` (`.stamp-chip`, `.narjes-icon`, `.narjes-ledger-*`) | **Absorb** into `scss/narjes/components/` (stamps, icons, cards). Removed from hooks. |
| `public/css/theme/frappe_overrides.css`, `desk_shell.css` (OFF) | **Superseded** by `_frappe-map-{light,dark}.scss` + structural partials. Files deleted from hooks (kept on disk for reference until P7 completes). |
| `public/css/theme/login.css` (OFF) | **Superseded** by `pages/_login.scss` in `narjes-web.bundle`. |
| `public/css/narjes_navbar.css` | **Absorb** into chrome partial. |
| `public/css/narjes_kanban.css` | **Absorb** into `views/_kanban.scss`. |
| `public/css/sales_order_gallery.css` | **Absorb** into `views/_gallery.scss` (content ported verbatim, colors re-pointed at tokens). |
| `public/js/narjes_theme.js` (NARJES_BRAND + live accent override) | **Absorb** into `js/narjes.bundle.js` (kept API-compatible: `NARJES_BRAND` global stays). |
| `public/js/narjes_icons.js` (`narjes_icon()`) | **Keep** as-is, loaded from the bundle. |
| `narjes_home.js/css`, `ai_intake.js` (page-local, auto-loaded) | **P7**: page CSS trimmed to consume tokens; structure kept. |
| `setup/branding.py` (Navbar/Website Settings logo+name) | **Keep**; theme adds `setup/theme_branding.py` for Letter Head, Print Style, mail footer, help-menu prune. |
| `extend_bootinfo` accent mechanism (Narjes Settings → boot.narjes_theme) | **Keep** — this is the P3.5 re-themeability mechanism, already live. |

## 7. Environment

- Bench running under honcho: web :8000, watch (esbuild), schedule, workers;
  redis + mariadb up. Site: `narjes.local` (developer_mode 1).
- Browsers supported: last 2 Chrome/Edge/Safari/Firefox + Android Chrome.
- Kill switch: `narjes_theme_enabled` in site_config (default on), read in
  `boot.py`, applied as `body.narjes-ledger` by `narjes.bundle.js`. All
  structural CSS scoped to that class. Full rollback: remove hook lines +
  `bench build --app narjes_custom` (documented in UPGRADE_NOTES.md).

## 8. Baseline

"Before" screenshots (frappe_desk_theme era) not re-captured — the prior theme
is being replaced wholesale; the mock screenshots + Ledger sheet are the
acceptance reference going forward. After-screenshots live in `docs/evidence/`.
