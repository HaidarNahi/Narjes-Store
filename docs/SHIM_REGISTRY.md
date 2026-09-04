# Shim registry — every JS override of Frappe UI, each a named liability

Re-verify each row after every `bench update` (UPGRADE_NOTES.md). Target ≤ 10.

| # | File | Touches | Reason | Verified against |
|---|---|---|---|---|
| 1 | `js/narjes/boot.js` `relabel_theme_switcher` | `frappe.ui.ThemeSwitcher.prototype.fetch_themes` | "Frappe Light"/"Timeless Night" → "Paper"/"Ink" (P3.4); skins, doesn't fork, Auto kept | v16.20 `theme_switcher.js` |
| 2 | `js/narjes/about.js` | `frappe.ui.misc.about` | Branded About box, no framework credits (P8.3) | v16.20 |
| 3 | `js/narjes/boot.js` `set_search_placeholder` | `#navbar-search` placeholder attr | "Search orders, customers…" (P4.3) | v16.20 navbar DOM |
| 4 | `js/narjes/boot.js` `stamp_terminal_indicator` | `.page-head .indicator-pill` classList | Applies `.n-stamp--stamped` to terminal states only (P5.4) — additive class, no API touched | v16.20 page-head DOM |
| 5 | `js/narjes/boot.js` `remove_legacy_home_button` | removes `#narjes-navbar-home-btn` | Deletes the pre-theme duplicate Home button that stale browser caches of the un-versioned `customer_quick_entry.js` still inject. **Temporary** — delete a few releases after 2026-07-30 | our own markup, not Frappe |
| 6 | `js/narjes/explainers.js` | `frappe.utils.build_summary_item` | Appends the "what is this?" button to report summary cards that ship an `explanation`. Additive — the original builds the card, the wrap adds to it, and a card with no explanation is returned untouched | v16.20 `utils.js` |

Total: 5 of 10 budget (one of them self-expiring). `narjes.motion.*` and
`narjes_icon()` are additive APIs, not shims.

## Deliberately *not* shims

- **Workspace sidebar brand** (module icon + "ERPNext" app name): was shim #4.
  Frappe re-renders that header *after* `page-change`, so a JS swap always
  loses the race — it showed the stock icon again on every workspace switch.
  Now done race-free in `_chrome.scss` (`.header-logo` gets the mark as a
  background with its children hidden; `.header-subtitle` is overwritten via
  `::after`). If a Frappe update renames those classes, the brand silently
  reverts to stock — check it in the upgrade walk.
- Onboarding-widget hide and other pure-CSS suppressions live in scss.
