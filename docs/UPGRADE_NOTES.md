# Upgrade playbook — absorbing a `bench update` without improvising

Pin frappe/erpnext between planned updates. On update day:

1. **Re-run the P0 extraction diff** (documented in AUDIT.md §2–5):
   - `grep -oE "^\s*--[a-z0-9-]+" apps/frappe/frappe/public/scss/common/css_variables.scss | sort -u`
     and the desk file — diff against AUDIT.md §3. New vars → add to the two
     map files; removed vars → delete (they're harmless but noisy).
   - Confirm the dark selector is still `[data-theme="dark"]` and the switcher
     still hard-codes light/dark/automatic in `fetch_themes()` (shim #1).
   - Sprite check: `grep -c '<symbol id=' apps/frappe/frappe/public/icons/lucide/icons.svg`
     (1625 at v16.20) and espresso (274). The Narjes sprite is additive
     (`ph-*` ids) so core changes can't collide, but `frappe.utils.icon`'s
     class emission (`es-icon es-line`) is worth a glance.
2. `bench build --app narjes_custom`
3. **`python3 scripts/theme_doctor.py`** — must be all green.
4. **`python3 scripts/contrast_check.py`** — must exit 0.
5. Walk the SHIM_REGISTRY rows (5 shims): open the switcher, the About box,
   the awesomebar, a workspace sidebar, and a submitted+cancelled SO form.
6. Visual walk of the Appendix E top-10 (light + dark): login · narjes-home ·
   SO list · SO form (draft/submitted/cancelled) · Kanban Order Phases ·
   Items Balance · Sales Revenue · dashboard · AI intake · /apps.
7. Fix, log anything moved in AUDIT.md, commit.

## Rollback (rehearsed)

- Instant: `"narjes_theme_enabled": 0` in site_config → reload (kill switch).
- Full: remove `app_include_css/js`, `web_include_css/js`, `app_logo_url`,
  `website_context`, `default_mail_footer` from hooks.py → `bench build --app
  narjes_custom` → `bench --site narjes.local clear-cache`.
- The old frappe_desk_theme app remains in `apps/` if stock-plus-theme is ever
  wanted back: `bench --site narjes.local install-app frappe_desk_theme`.
