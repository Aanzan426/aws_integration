app_name = "aws_integration"
app_title = "Aws Integration"
app_publisher = "Hybrowlabs Technologies"
app_description = "AWS Integration for frappe"
app_email = "support@hybrowlabs.com"
app_license = "apache-2.0"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "aws_integration",
# 		"logo": "/assets/aws_integration/logo.png",
# 		"title": "Aws Integration",
# 		"route": "/aws_integration",
# 		"has_permission": "aws_integration.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/aws_integration/css/aws_integration.css"
# app_include_js = "/assets/aws_integration/js/aws_integration.js"

# include js, css files in header of web template
# web_include_css = "/assets/aws_integration/css/aws_integration.css"
# web_include_js = "/assets/aws_integration/js/aws_integration.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "aws_integration/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {
    "File": "public/js/file.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "aws_integration/public/icons.svg"

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
# 	"methods": "aws_integration.utils.jinja_methods",
# 	"filters": "aws_integration.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "aws_integration.install.before_install"
# after_install = "aws_integration.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "aws_integration.uninstall.before_uninstall"
# after_uninstall = "aws_integration.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "aws_integration.utils.before_app_install"
# after_app_install = "aws_integration.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "aws_integration.utils.before_app_uninstall"
# after_app_uninstall = "aws_integration.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "aws_integration.notifications.get_notification_config"

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"aws_integration.utils.email.flush_email_queue"
	],
	"hourly": [
		"aws_integration.s3.scheduler.upload_pending_files"
	],
	"daily": [
		"aws_integration.s3.backup.take_backups_daily",
		"aws_integration.s3.backup.rotate_old_backups_daily"
	],
	"weekly_long": [
		"aws_integration.s3.backup.take_backups_weekly"
	],
	"monthly_long": [
		"aws_integration.s3.backup.take_backups_monthly"
	],
}

default_log_clearing_doctypes = {
	"S3 Backup Log": 90,
}

doc_events = {
	"File": {
		"after_insert": "aws_integration.s3.handlers.on_file_upload",
		"on_trash": "aws_integration.s3.handlers.on_file_delete"
	}
}

override_doctype_class = {
    "File": "aws_integration.s3.overrides.S3File"
}

after_migrate = [
    "aws_integration.s3.setup.after_migrate"
]

# scheduler_events = {
# 	"all": [
# 		"aws_integration.tasks.all"
# 	],
# 	"daily": [
# 		"aws_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"aws_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"aws_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"aws_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "aws_integration.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "aws_integration.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "aws_integration.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["aws_integration.utils.before_request"]
# after_request = ["aws_integration.utils.after_request"]

# Job Events
# ----------
# before_job = ["aws_integration.utils.before_job"]
# after_job = ["aws_integration.utils.after_job"]

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
# 	"aws_integration.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

