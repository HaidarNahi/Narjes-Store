app_name = "narjes_custom"
app_title = "Narjes Custom"
app_publisher = "Haidar Nahi"
app_description = "Narjes Store ERP System"
app_email = "haimohx@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "narjes_custom",
# 		"logo": "/assets/narjes_custom/logo.png",
# 		"title": "Narjes Custom",
# 		"route": "/narjes_custom",
# 		"has_permission": "narjes_custom.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
    "/assets/narjes_custom/css/sales_order_gallery.css",
    "/assets/narjes_custom/css/narjes_kanban.css"
]
app_include_js = [
    "/assets/narjes_custom/js/customer_quick_entry.js"
]

# include js, css files in header of web template
# web_include_css = "/assets/narjes_custom/css/narjes_custom.css"
# web_include_js = "/assets/narjes_custom/js/narjes_custom.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "narjes_custom/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
page_js = {"ai-intake": "narjes_custom/page/ai_intake/ai_intake.js"}

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

doc_events = {
	"Sales Order": {
		"before_validate": "narjes_custom.api.sales_order_before_validate",
		"validate": "narjes_custom.api.sales_order_validate"
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
		"before_validate": "narjes_custom.api.purchase_order_before_validate"
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

