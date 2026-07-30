app_name = "narjes_custom"
app_title = "Narjes Custom"
app_publisher = "Haidar Nahi"
app_description = "Narjes Store ERP System"
app_email = "haimohx@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Narjes entry on the /apps screen (theme plan P8.5)
add_to_apps_screen = [
	{
		"name": "narjes_custom",
		"logo": "/assets/narjes_custom/images/narjes-logo.svg",
		"title": "Narjes",
		"route": "/app/narjes-home",
	}
]

# Includes in <head>
# ------------------
extend_bootinfo = "narjes_custom.api.extend_bootinfo"

# include js, css files in header of desk.html
# Narjes Ledger (docs/THEME.md): everything rides the two bundles. The old
# per-file theme css (tokens/components/kanban/navbar/gallery) is absorbed
# into scss/narjes/ — see docs/AUDIT.md §6 for the absorb map. Kill switch:
# narjes_theme_enabled in site_config (read in api.extend_bootinfo, applied
# as body.narjes-ledger by narjes.bundle.js).
app_include_css = "narjes.bundle.css"
app_include_js = [
    "narjes.bundle.js",
    "/assets/narjes_custom/js/customer_quick_entry.js",
]
app_include_icons = [
    "/assets/narjes_custom/icons/phosphor/icons.svg"
]

# login/website surfaces (theme plan P4.1)
web_include_css = "narjes-web.bundle.css"
web_include_js = "narjes-web.bundle.js"

# navbar/splash brand mark (theme plan P4.2/P8.1)
app_logo_url = "/assets/narjes_custom/images/narjes-logo.svg"

# favicon + splash on every website-rendered page (theme plan P2.2/P2.3)
website_context = {
    "favicon": "/assets/narjes_custom/images/favicon.svg",
    "splash_image": "/assets/narjes_custom/images/splash.svg",
}

# every outgoing email ends on the shop's line, never a framework footer
# (theme plan P8.7/P9.5)
default_mail_footer = """
<div style="padding: 8px 0; font-size: 12px; color: #6A736C;">
    Narjes Store · Baghdad — <a href="mailto:haimohx@gmail.com"
    style="color: #264C3A;">haimohx@gmail.com</a>
</div>
"""

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "narjes_custom/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# Note: narjes-home is intentionally NOT listed here — Frappe's Page.load_assets()
# already auto-loads narjes_home.js/.css by naming convention from the page's own
# folder; adding it here would bundle the same script twice.
page_js = {
    "ai-intake": "narjes_custom/page/ai_intake/ai_intake.js"
}

# include js in doctype views
doctype_js = {
	"Sales Order" : "public/js/sales_order.js",
	"Purchase Order" : "public/js/purchase_order.js"
}
doctype_list_js = {"Sales Order" : "public/js/sales_order_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "narjes_custom/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "narjes_custom.utils.jinja_methods",
# 	"filters": "narjes_custom.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "narjes_custom.install.before_install"
# after_install = "narjes_custom.install.after_install"
after_install = [
	"narjes_custom.setup.custom_fields.run",
	"narjes_custom.setup.branding.run",
	"narjes_custom.setup.workspace_visibility.run",
	"narjes_custom.setup.sidebar_layout.run",
	"narjes_custom.setup.workspace_sidebar.run",
]

# Re-sync custom fields on every migrate too, not just on first install —
# belt-and-suspenders alongside the `fixtures` export above, and what makes
# the local-dev-vs-production drift described in NARJES_STORE_SYSTEM.md §12
# self-correcting going forward instead of something that has to be
# remembered and run by hand. Also self-heals any Quick Shortcut rows still
# holding a pre-Phosphor-reskin emoji value.
after_migrate = [
	"narjes_custom.setup.custom_fields.run",
	"narjes_custom.setup.branding.run",
	"narjes_custom.setup.theme_branding.run",
	"narjes_custom.setup.workspace_visibility.run",
	"narjes_custom.setup.sidebar_layout.run",
	"narjes_custom.setup.workspace_sidebar.run",
	"narjes_custom.setup_narjes_settings_defaults.migrate_shortcut_icons_to_phosphor",
]

# Uninstallation
# ------------

# before_uninstall = "narjes_custom.uninstall.before_uninstall"
# after_uninstall = "narjes_custom.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "narjes_custom.utils.before_app_install"
# after_app_install = "narjes_custom.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "narjes_custom.utils.before_app_uninstall"
# after_app_uninstall = "narjes_custom.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "narjes_custom.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "narjes_custom.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# Every custom field this app depends on is defined once, in
# narjes_custom.setup.custom_fields, and exported here so it travels with
# the app in git and is reproducible on a fresh site (see
# NARJES_STORE_SYSTEM.md §14.1/§14.2 — this used to be either hand-edited
# directly into ERPNext's own core doctype JSON files, or created by half a
# dozen separate one-off scripts with no fixture export at all).
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["dt", "in", ["Customer", "Item", "Sales Order", "Purchase Order"]]],
	},
]

doc_events = {
	"Sales Order": {
		"before_validate": "narjes_custom.api.sales_order_before_validate",
		"validate": "narjes_custom.api.sales_order_validate",
		"on_submit": "narjes_custom.api.automate_so_flow"
	},
	"Sales Invoice": {
		"before_validate": "narjes_custom.api.sales_order_before_validate",
		"validate": "narjes_custom.api.sales_order_validate"
	},
	"Delivery Note": {
		"before_validate": "narjes_custom.api.sales_order_before_validate",
		"validate": "narjes_custom.api.sales_order_validate"
	},
	"Purchase Order": {
		"before_validate": "narjes_custom.api.purchase_order_before_validate",
		"on_submit": "narjes_custom.api.automate_po_flow"
	},
	"Item": {
		"validate": "narjes_custom.api.item_validate"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"narjes_custom.tasks.all"
# 	],
# 	"daily": [
# 		"narjes_custom.tasks.daily"
# 	],
# 	"hourly": [
# 		"narjes_custom.tasks.hourly"
# 	],
# 	"weekly": [
# 		"narjes_custom.tasks.weekly"
# 	],
# 	"monthly": [
# 		"narjes_custom.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "narjes_custom.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "narjes_custom.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "narjes_custom.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "narjes_custom.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["narjes_custom.utils.before_request"]
# after_request = ["narjes_custom.utils.after_request"]

# Job Events
# ----------
# before_job = ["narjes_custom.utils.before_job"]
# after_job = ["narjes_custom.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"narjes_custom.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

