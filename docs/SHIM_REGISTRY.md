# Shim registry — every JS override of Frappe UI, each a named liability

Re-verify each row after every `bench update` (UPGRADE_NOTES.md). Target ≤ 10.

| # | File | Touches | Reason | Verified against |
|---|---|---|---|---|
| 1 | `js/narjes/boot.js` `relabel_theme_switcher` | `frappe.ui.ThemeSwitcher.prototype.fetch_themes` | "Frappe Light"/"Timeless Night" → "Paper"/"Ink" (P3.4); skins, doesn't fork, Auto kept | v16.20 `theme_switcher.js` |
| 2 | `js/narjes/about.js` | `frappe.ui.misc.about` | Branded About box, no framework credits (P8.3) | v16.20 |
| 3 | `js/narjes/boot.js` `set_search_placeholder` | `#navbar-search` placeholder attr | "Search orders, customers…" (P4.3) | v16.20 navbar DOM |
| 4 | `js/narjes/boot.js` `white_label_sidebar` | `.body-sidebar .sidebar-header` logo img + subtitle text | App-switcher shows "ERPNext" + module icon; rebrand to Narjes mark (P8.1). MutationObserver — re-check selector on update | v16.20 sidebar DOM |
| 5 | `js/narjes/boot.js` `stamp_terminal_indicator` | `.page-head .indicator-pill` classList | Applies `.n-stamp--stamped` to terminal states only (P5.4) — additive class, no API touched | v16.20 page-head DOM |

Total: 5 of 10 budget. `narjes.motion.*` and `narjes_icon()` are additive APIs,
not shims. CSS-only hides (onboarding widget) live in scss, not here.
