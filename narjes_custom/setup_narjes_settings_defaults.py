import frappe

DEFAULT_SIDEBAR_LINKS = [
    {"workspace": "Narjes Dashboard", "label": "Home Dashboard", "link_type": "Page", "link_to": "narjes-home", "icon": "home"},
]

DEFAULT_SHORTCUTS = [
    {"label": "Sales Orders", "icon": "📋", "route": "/app/sales-order"},
    {"label": "Customers", "icon": "👤", "route": "/app/customer"},
    {"label": "Item Master", "icon": "📦", "route": "/app/item"},
    {"label": "Revenue Report", "icon": "📊", "route": "/app/query-report/Sales Revenue Report"},
    # Previously had no shortcut, sidebar entry, or Workspace reference
    # anywhere — reachable only by typing the report's URL directly. See
    # NARJES_STORE_SYSTEM.md §5.1/§15 (Recommended Enhancement 3).
    {"label": "Items Balance", "icon": "📉", "route": "/app/query-report/Items Balance"},
    {"label": "Delivery Notes", "icon": "🚚", "route": "/app/delivery-note"},
    {"label": "Purchase Orders", "icon": "🛒", "route": "/app/purchase-order"},
    {"label": "AI Order Intake", "icon": "✨", "route": "/app/ai-intake"},
]


def run():
    """One-time bootstrap for a fresh Narjes Settings — only seeds each
    table the first time it's completely empty. See ensure_defaults() below
    for adding a single new default to a site that has already been seeded
    (e.g. production, where quick_shortcuts is no longer empty)."""
    settings = frappe.get_single("Narjes Settings")
    changed = False

    if not settings.sidebar_links:
        for link in DEFAULT_SIDEBAR_LINKS:
            settings.append("sidebar_links", link)
        changed = True
        print("Seeded default sidebar links")

    if not settings.quick_shortcuts:
        for sc in DEFAULT_SHORTCUTS:
            settings.append("quick_shortcuts", sc)
        changed = True
        print("Seeded default quick shortcuts")

    if changed:
        settings.save(ignore_permissions=True)
        frappe.db.commit()
        print("Done!")
    else:
        print("Narjes Settings already configured — nothing to seed.")


def ensure_defaults():
    """Idempotently make sure every entry in DEFAULT_SHORTCUTS /
    DEFAULT_SIDEBAR_LINKS exists, even on a site where the tables are no
    longer empty (so run() above would no-op). Matches on (label, route)
    for shortcuts and (workspace, label) for sidebar links — adds only
    what's missing, never touches or duplicates existing rows."""
    settings = frappe.get_single("Narjes Settings")
    changed = False

    existing_shortcuts = {(row.label, row.route) for row in settings.quick_shortcuts}
    for sc in DEFAULT_SHORTCUTS:
        if (sc["label"], sc["route"]) not in existing_shortcuts:
            settings.append("quick_shortcuts", sc)
            changed = True
            print(f"Added missing shortcut: {sc['label']}")

    existing_links = {(row.workspace, row.label) for row in settings.sidebar_links}
    for link in DEFAULT_SIDEBAR_LINKS:
        if (link["workspace"], link["label"]) not in existing_links:
            settings.append("sidebar_links", link)
            changed = True
            print(f"Added missing sidebar link: {link['label']}")

    if changed:
        settings.save(ignore_permissions=True)
        frappe.db.commit()
        print("Done!")
    else:
        print("Nothing missing — all defaults already present.")
