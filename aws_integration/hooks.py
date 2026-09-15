app_name = "aws_integration"
app_title = "AWS Integration"
app_publisher = "Hybrowlabs Technologies"
app_description = "AWS Integration for frappe"
app_email = "support@hybrowlabs.com"
app_license = "apache-2.0"

# Includes in <head>
# ------------------

# include js in doctype views
doctype_js = {
	"File": "public/js/file.js"
}

# DocType Class
# ---------------

override_doctype_class = {
	"File": "aws_integration.s3.overrides.S3File"
}

# Document Events
# ---------------

doc_events = {
	"File": {
		"after_insert": "aws_integration.s3.handlers.on_file_upload",
		"on_trash": "aws_integration.s3.handlers.on_file_delete"
	}
}

# Email hooks
# ---------------

# email-governance-engine Part 2: inject X-SES-Configuration-Set (always,
# when configured) and List-Unsubscribe (only for sends explicitly marked
# promotional=True) onto every outbound email in this bench. See
# aws_integration/utils/email_headers.py for full design rationale — in
# particular why List-Unsubscribe-Post (RFC 8058 one-click) is deliberately
# NOT injected yet (deferred to Part 3's suppression doctype + POST
# endpoint).
make_email_body_message = "aws_integration.utils.email_headers.inject_governance_headers"

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

# Log Clearing
# ---------------

default_log_clearing_doctypes = {
	"S3 Backup Log": 90,
}

# Migrations
# ---------------

after_migrate = [
	"aws_integration.s3.setup.after_migrate"
]
