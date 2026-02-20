import os
import traceback

import boto3
import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.backups import new_backup


@frappe.whitelist()
def take_s3_backup():
	"""Whitelisted API: create a backup log and enqueue the job."""
	frappe.only_for("System Manager")
	return _enqueue_backup()


def _enqueue_backup():
	"""Create an S3 Backup Log entry (Queued) and enqueue the actual backup job.

	Separated from the whitelisted endpoint so the scheduler can call it
	without hitting the role guard.
	"""
	settings = frappe.get_cached_doc("AWS Settings")
	if not settings.enable_s3_backups:
		frappe.throw(_("S3 Backups are not enabled in AWS Settings"))

	log = frappe.get_doc({
		"doctype": "S3 Backup Log",
		"status": "Queued",
	})
	log.insert(ignore_permissions=True)
	frappe.db.commit()

	frappe.enqueue(
		_run_backup,
		queue="long",
		timeout=6000,
		log_name=log.name,
		retry_count=0,
	)

	return {"log_name": log.name}


def _run_backup(log_name, retry_count=0):
	"""Background job: generate backup, upload to S3, update log."""
	log = frappe.get_doc("S3 Backup Log", log_name)
	try:
		# Mark In Progress
		log.status = "In Progress"
		log.started_at = now_datetime()
		log.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.publish_realtime(
			"s3_backup_progress",
			{"status": "generating", "log_name": log_name},
			user=frappe.session.user,
		)

		# Read settings fresh (not cached) for background jobs
		settings = frappe.get_doc("AWS Settings")
		include_files = settings.s3_backup_files
		bucket = settings.s3_backup_bucket_name or settings.s3_bucket_name
		folder = settings.s3_backup_folder_prefix or frappe.local.site
		notify_email = settings.s3_backup_notify_email
		notify_success = settings.s3_backup_notify_success

		# Generate backup files
		odb = new_backup(
			ignore_files=not include_files,
			force=True,
		)

		backup_paths = {
			"db": odb.backup_path_db,
			"conf": odb.backup_path_conf,
		}
		if include_files:
			backup_paths["files"] = odb.backup_path_files
			backup_paths["private"] = odb.backup_path_private_files

		frappe.publish_realtime(
			"s3_backup_progress",
			{"status": "uploading", "log_name": log_name},
			user=frappe.session.user,
		)

		# Build S3 client
		s3_client = _get_s3_client(settings)

		# Upload each file to S3
		uploaded = {}
		total_size = 0
		db_size = 0
		files_size = 0

		for key, path in backup_paths.items():
			if not path or not os.path.exists(path):
				continue
			file_name = os.path.basename(path)
			s3_key = f"{folder}/{file_name}"
			file_size = os.path.getsize(path)

			s3_client.upload_file(path, bucket, s3_key)
			uploaded[key] = s3_key
			total_size += file_size

			if key == "db":
				db_size = file_size
			elif key in ("files", "private"):
				files_size += file_size

		# Update log with results
		log.reload()
		log.status = "Success"
		log.completed_at = now_datetime()
		log.s3_bucket = bucket
		log.s3_folder = folder
		log.db_file_url = uploaded.get("db", "")
		log.site_config_url = uploaded.get("conf", "")
		log.files_archive_url = uploaded.get("files", "")
		log.private_archive_url = uploaded.get("private", "")
		log.db_size = db_size
		log.files_size = files_size
		log.total_size = total_size
		log.save(ignore_permissions=True)
		frappe.db.commit()

		# Clean up local backup files
		_cleanup_local_backups(log, list(backup_paths.values()))

		frappe.publish_realtime(
			"s3_backup_progress",
			{"status": "success", "log_name": log_name},
			user=frappe.session.user,
		)

		# Send success notification
		if notify_email and notify_success:
			_send_notification(notify_email, log, success=True)

	except Exception:
		tb = traceback.format_exc()

		# Retry up to 2 times
		if retry_count < 2:
			frappe.enqueue(
				_run_backup,
				queue="long",
				timeout=6000,
				log_name=log_name,
				retry_count=retry_count + 1,
			)
			return

		_mark_failed(log, tb)

		frappe.publish_realtime(
			"s3_backup_progress",
			{"status": "failed", "log_name": log_name},
			user=frappe.session.user,
		)

		settings = frappe.get_doc("AWS Settings")
		notify_email = settings.s3_backup_notify_email
		if notify_email:
			_send_notification(notify_email, log, success=False)

		return

	# Rotate old backups OUTSIDE the try/except so rotation errors
	# don't trigger backup retries
	try:
		_rotate_old_backups(s3_client, settings, exclude_log=log_name)
	except Exception:
		frappe.log_error(
			title="S3 Backup Rotation Error",
			message=traceback.format_exc(),
		)


def _get_s3_client(settings):
	"""Create a boto3 S3 client from AWS Settings credentials."""
	client_kwargs = {
		"region_name": settings.s3_bucket_region or settings.region,
		"aws_access_key_id": settings.aws_access_key_id,
		"aws_secret_access_key": settings.get_password("aws_secret_access_key"),
	}
	if settings.s3_endpoint_url:
		client_kwargs["endpoint_url"] = settings.s3_endpoint_url

	return boto3.client("s3", **client_kwargs)


def _cleanup_local_backups(log, paths):
	"""Delete local backup files after successful S3 upload."""
	for path in paths:
		if path and os.path.exists(path):
			os.remove(path)

	log.reload()
	log.local_cleaned = 1
	log.save(ignore_permissions=True)
	frappe.db.commit()


def _mark_failed(log, traceback_text):
	"""Set log to Failed status with traceback."""
	log.reload()
	log.status = "Failed"
	log.completed_at = now_datetime()
	log.error = traceback_text
	log.save(ignore_permissions=True)
	frappe.db.commit()

	frappe.log_error(title="S3 Backup Failed", message=traceback_text)


def _send_notification(email, log, success=True):
	"""Send backup notification email."""
	site = frappe.local.site

	if success:
		subject = _("S3 Backup Successful - {0}").format(site)
		message = _(
			"S3 backup completed successfully.<br><br>"
			"<b>Log:</b> {log_name}<br>"
			"<b>Bucket:</b> {bucket}<br>"
			"<b>Database:</b> {db_file}<br>"
			"<b>Total Size:</b> {total_size}"
		).format(
			log_name=log.name,
			bucket=log.s3_bucket,
			db_file=log.db_file_url,
			total_size=_fmt_size(log.total_size),
		)
	else:
		subject = _("S3 Backup Failed - {0}").format(site)
		message = _(
			"S3 backup failed.<br><br>"
			"<b>Log:</b> {log_name}<br>"
			"<b>Error:</b> Check the backup log for details."
		).format(log_name=log.name)

	try:
		frappe.sendmail(
			recipients=[email],
			subject=subject,
			message=message,
		)
	except Exception:
		frappe.log_error(title="S3 Backup Email Failed", message=traceback.format_exc())


def _rotate_old_backups(s3_client, settings, exclude_log=None):
	"""Delete old backups from S3 based on retention settings.

	Supports two modes (either or both can be active):
	- Keep last N backups (s3_backup_retention_count)
	- Delete backups older than N days (s3_backup_retention_days)

	The current backup (exclude_log) is never deleted.
	"""
	retention_count = settings.s3_backup_retention_count or 0
	retention_days = settings.s3_backup_retention_days or 0

	if not retention_count and not retention_days:
		return

	logs_to_delete = set()

	if retention_count > 0:
		all_logs = frappe.get_all(
			"S3 Backup Log",
			filters={"status": "Success"},
			fields=["name"],
			order_by="creation desc",
		)
		if len(all_logs) > retention_count:
			for entry in all_logs[retention_count:]:
				logs_to_delete.add(entry.name)

	if retention_days > 0:
		from frappe.utils import add_days
		cutoff = add_days(now_datetime(), -retention_days)
		old_logs = frappe.get_all(
			"S3 Backup Log",
			filters={"status": "Success", "completed_at": ["<", cutoff]},
			fields=["name"],
		)
		for entry in old_logs:
			logs_to_delete.add(entry.name)

	# Never delete the backup that was just created
	if exclude_log:
		logs_to_delete.discard(exclude_log)

	if not logs_to_delete:
		return

	for log_name in logs_to_delete:
		try:
			_delete_backup_from_s3(s3_client, log_name)
		except Exception:
			frappe.log_error(
				title=f"S3 Backup Rotation Failed: {log_name}",
				message=traceback.format_exc(),
			)


def _delete_backup_from_s3(s3_client, log_name):
	"""Delete all S3 objects for a backup log entry, then delete the log."""
	log = frappe.get_doc("S3 Backup Log", log_name)
	bucket = log.s3_bucket

	if not bucket:
		frappe.delete_doc("S3 Backup Log", log_name, ignore_permissions=True)
		return

	s3_keys = [
		log.db_file_url,
		log.site_config_url,
		log.files_archive_url,
		log.private_archive_url,
	]
	objects = [{"Key": key} for key in s3_keys if key]

	if objects:
		s3_client.delete_objects(
			Bucket=bucket,
			Delete={"Objects": objects, "Quiet": True},
		)

	frappe.delete_doc("S3 Backup Log", log_name, ignore_permissions=True)
	frappe.db.commit()


def _fmt_size(size_bytes):
	"""Format bytes into a human-readable string."""
	if not size_bytes:
		return "0 B"
	units = ["B", "KB", "MB", "GB", "TB"]
	i = 0
	size = float(size_bytes)
	while size >= 1024 and i < len(units) - 1:
		size /= 1024
		i += 1
	return f"{size:.1f} {units[i]}"


# --- Scheduler functions ---

def take_backups_daily():
	"""Called by scheduler daily event."""
	_take_backups_if("Daily")


def take_backups_weekly():
	"""Called by scheduler weekly event."""
	_take_backups_if("Weekly")


def take_backups_monthly():
	"""Called by scheduler monthly event."""
	_take_backups_if("Monthly")


def _take_backups_if(freq):
	"""Create a backup if the configured frequency matches."""
	settings = frappe.get_cached_doc("AWS Settings")
	if not settings.enable_s3_backups:
		return
	if not settings.enable_aws or not settings.enable_s3:
		return
	if settings.s3_backup_frequency != freq:
		return

	_enqueue_backup()
