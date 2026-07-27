import frappe

DEFAULT_SIDEBAR_LINKS = [
    {"workspace": "Narjes Dashboard", "label": "Home Dashboard", "link_type": "Page", "link_to": "narjes-home", "icon": "home"},
]

DEFAULT_SHORTCUTS = [
    {"label": "Sales Orders", "icon": "📋", "route": "/app/sales-order"},
    {"label": "Customers", "icon": "👤", "route": "/app/customer"},
    {"label": "Item Master", "icon": "📦", "route": "/app/item"},
    {"label": "Revenue Report", "icon": "📊", "route": "/app/query-report/Sales Revenue Report"},
    {"label": "Delivery Notes", "icon": "🚚", "route": "/app/delivery-note"},
    {"label": "Purchase Orders", "icon": "🛒", "route": "/app/purchase-order"},
    {"label": "AI Order Intake", "icon": "✨", "route": "/app/ai-intake"},
]


def run():
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
