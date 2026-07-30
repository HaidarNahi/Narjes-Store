# Narjes Ledger — theme handover

How the theme works, how to change it, and what to never do. Companion docs:
[AUDIT.md](AUDIT.md) (P0 extraction), [SHIM_REGISTRY.md](SHIM_REGISTRY.md),
[UPGRADE_NOTES.md](UPGRADE_NOTES.md), [CONTRAST.md](CONTRAST.md) (generated),
[ledger-sheet.html](ledger-sheet.html) (the visual reference, generated).

## The one rule

Everything lives in `narjes_custom`. No core edits, no `!important` outside
`_shame.scss`, no hex outside `tokens.json`.

## How a color reaches the screen

```
public/tokens.json                  ← edit here (the ONLY place)
  └─ scripts/generate_tokens.py    → _tokens.scss + css/narjes-vars.css (--n-*)
      ├─ _frappe-map-light.scss    → Frappe's own vars remapped (body.narjes-ledger)
      ├─ _frappe-map-dark.scss     → same under [data-theme="dark"]
      └─ components/views scss     → structural rules, var(--n-*) only
```

**Re-theming = edit tokens.json, run the generator, `bench build --app
narjes_custom`.** Nothing else. The Lever-1 maps carry ≥70% of the theming;
if a visual can be fixed by remapping a Frappe variable there, do that — never
write a structural selector for it (Appendix B rule).

## Layout of `public/`

- `narjes.bundle.scss/js` — desk entry; `narjes-web.bundle.scss/js` — login/web.
- `scss/narjes/` — `_tokens` (generated) · `_fonts` (generated) · `_compat`
  (old `--narjes-*` aliases; delete lines only after grepping) · maps · `_base`
  · `_chrome` · `components/` · `views/` · `pages/` · `_rtl` · `_shame`.
- `js/narjes/` — `brand` (NARJES_BRAND + live accent) · `icons` (`narjes_icon()`)
  · `boot` (kill switch + shims) · `about` · `motion` (`narjes.motion.*`).
- `fonts/` + `patterns/` + `images/` — generated/produced assets (ASSETS.md).

## Kill switch

`site_config.json → "narjes_theme_enabled": 0` → reload. `boot.js` then drops
`body.narjes-ledger` and every map + structural rule disengages (tokens and
namespaced legacy classes stay — custom pages remain functional). Full
uninstall: remove the `app_include_*`/`web_include_*`/`app_logo_url` hook
lines, `bench build`, `bench --site narjes.local clear-cache`.

## The Stamp

Anatomy + variants in `components/_stamps.scss`; state table in the plan P5.4.
Frappe pills inherit it wholesale via the ramp remap. The `stamped` terminal
variant is opt-in (`.n-stamp--stamped`), applied only by `boot.js` to the
form-banner indicator and by `narjes.motion.stamp()` on terminal transitions.
Never apply it in lists.

## Patterns

Vine + grain placement is fixed (plan P1.5): login (strongest), splash, modal
header strip, file-uploader dropzone, canvas grain (light only). Full-opacity
SVGs; strength is set per-surface via `opacity` on the pattern layer.
**Nowhere else** — forms, lists, and reports stay clean paper.

## Seasonal accents (P3.5)

Narjes Settings → Appearance already re-accents live via
`frappe.boot.narjes_theme` (patches `--n-primary` family +
`--narjes-fern` aliases at runtime — `js/narjes/brand.js`).

## Print & comms

`setup/theme_branding.py` (runs on migrate) owns: Letter Head "Narjes",
Print Style "Narjes Ledger", print formats "Narjes Order" (SO) + "Narjes
Driver Slip" (DN, A5), help-menu prune, kanban column ramps.
`hooks.py` owns `default_mail_footer`. PDF engine choice per format is
pending the Arabic test matrix (P9.4) — record decisions here.

## Scripts (run from the app root)

| Script | Purpose |
|---|---|
| `scripts/generate_tokens.py` | tokens.json → scss/css |
| `scripts/fetch_fonts.py` | re-fetch self-hosted fonts (only to change the set) |
| `scripts/build_ledger_sheet.py` | regenerate docs/ledger-sheet.html |
| `scripts/contrast_check.py` | WCAG matrix → docs/CONTRAST.md, non-zero on fail |
| `scripts/theme_doctor.py` | post-build/post-update assertions + budgets |
