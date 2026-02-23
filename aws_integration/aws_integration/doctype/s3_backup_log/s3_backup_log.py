# Copyright (c) 2026, Hybrowlabs Technologies and contributors
# For license information, please see license.txt

import secrets

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now
from frappe.utils import now_datetime


class S3BackupLog(Document):

	def autoname(self):
		if self.name:
			return

		base = now_datetime().strftime("BKUP-%Y%m%d-%H%M%S")
		if frappe.db.exists("S3 Backup Log", base):
			base = f"{base}-{secrets.token_hex(2)}"
		self.name = base

	def on_trash(self):
		"""Delete S3 objects when a backup log is manually deleted."""
		if not self.s3_bucket:
			return

		s3_keys = [
			self.db_file_url,
			self.site_config_url,
			self.files_archive_url,
			self.private_archive_url,
		]
		objects = [{"Key": key} for key in s3_keys if key]
		if not objects:
			return

		try:
			settings = frappe.get_doc("AWS Settings")
			if not settings.enable_aws or not settings.enable_s3:
				return

			from aws_integration.s3.backup import _get_s3_client

			s3_client = _get_s3_client(settings)
			s3_client.delete_objects(
				Bucket=self.s3_bucket,
				Delete={"Objects": objects, "Quiet": True},
			)
		except Exception:
			frappe.log_error(
				title=f"S3 Backup Delete Failed: {self.name}",
				message=frappe.get_traceback(),
			)

	@staticmethod
	def clear_old_logs(days=90):
		table = frappe.qb.DocType("S3 Backup Log")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))
