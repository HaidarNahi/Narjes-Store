"""Wires the Narjes Store logo into the real, supported branding fields —
Navbar Settings.app_logo (desk topbar + the login page, which reads the same
field via get_app_logo()) and Website Settings.app_logo/app_name/favicon —
instead of hand-editing any core template.

Unconditionally sets these fields to the Narjes brand values rather than
skip-if-already-set: on this bench they held leftover placeholder values
(a stray uploaded file GUID, the literal default "Frappe") from before this
app had any real branding step, not a deliberate admin customization worth
preserving. Re-running always converges to the same correct brand state,
which is idempotent in the sense that matters here.

Run via: bench execute narjes_custom.setup.branding.run
"""

import frappe

LOGO_PATH = "/assets/narjes_custom/images/narjes-logo.svg"
APP_NAME = "Narjes Store"


def run():
	navbar_settings = frappe.get_single("Navbar Settings")
	navbar_settings.app_logo = LOGO_PATH
	navbar_settings.save(ignore_permissions=True)

	website_settings = frappe.get_single("Website Settings")
	website_settings.app_logo = LOGO_PATH
	website_settings.app_name = APP_NAME
	website_settings.favicon = LOGO_PATH
	website_settings.save(ignore_permissions=True)

	frappe.db.commit()
	print("Set Navbar Settings + Website Settings branding fields")
