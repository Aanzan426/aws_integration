import os

import frappe
from frappe.utils import cint, now_datetime


def upload_pending_files():
    """Scheduler job: Upload local files to S3.

    Runs periodically based on the hourly scheduler event.
    Processes files in batches, skipping exempt doctypes.
    Deletes local files after upload if configured.

    Returns:
        None
    """
    settings = frappe.get_cached_doc("AWS Settings")
    if not settings.enable_aws or not settings.enable_s3:
        return

    batch_size = cint(settings.s3_batch_size) or 50

    # Build set of exempt doctypes for O(1) lookup
    exempt_doctypes = {d.exempt_doctype for d in settings.exempt_doctypes}

    # Query local files not yet uploaded to S3.
    # file_url starting with "/" means local; is_on_s3 = 0 means not yet migrated.
    filters = {
        "is_folder": 0,
        "file_url": ("like", "/%"),
        "is_on_s3": 0,
    }

    files = frappe.get_all(
        "File",
        filters=filters,
        fields=[
            "name",
            "file_name",
            "file_url",
            "is_private",
            "attached_to_doctype",
            "attached_to_name",
        ],
        limit_page_length=batch_size,
        order_by="creation asc",
    )

    if not files:
        return

    from aws_integration.s3.client import S3Client

    try:
        s3_client = S3Client()
    except Exception as e:
        frappe.log_error(
            title="S3 Upload Error",
            message=f"Failed to initialize S3 client: {str(e)}\n{frappe.get_traceback()}",
        )
        return

    uploaded_count = 0
    failed_count = 0

    for file_data in files:
        # Skip files attached to exempt doctypes
        if file_data.attached_to_doctype and file_data.attached_to_doctype in exempt_doctypes:
            continue

        try:
            file_doc = frappe.get_doc("File", file_data.name)

            # Skip if already on S3 (double-check after fresh fetch)
            if file_doc.is_on_s3:
                continue

            # Skip if file_url already points to the S3 API route
            if file_doc.file_url and file_doc.file_url.startswith("/api/method/"):
                continue

            # Acquire a row-level lock to prevent a concurrent instant-upload
            # worker from uploading the same file at the same time.
            lock_result = frappe.db.sql(
                "SELECT name FROM `tabFile` WHERE name=%s AND is_on_s3=0 FOR UPDATE",
                file_doc.name,
            )
            if not lock_result:
                continue

            # Resolve the absolute path on disk
            file_path = file_doc.get_full_path()
            if not os.path.exists(file_path):
                frappe.log_error(
                    title="S3 Upload Skipped",
                    message=f"File not found on disk: {file_data.name} ({file_path})",
                )
                continue

            # Upload to S3 and receive the object key
            s3_key = s3_client.upload_file(file_doc)

            # Build the new file_url that proxies through the Frappe API
            new_file_url = (
                f"/api/method/aws_integration.api.s3.generate_file"
                f"?key={s3_key}&file_name={file_doc.file_name}"
            )

            # Persist S3 metadata on the File document without touching modified timestamp
            frappe.db.set_value(
                "File",
                file_doc.name,
                {
                    "file_url": new_file_url,
                    "s3_key": s3_key,
                    "is_on_s3": 1,
                    "s3_uploaded_at": now_datetime(),
                },
                update_modified=False,
            )

            # Commit BEFORE removing the local file so that a failed commit
            # never leaves the file permanently lost.
            frappe.db.commit()

            # Optionally remove the local copy after a successful upload
            if settings.delete_local_after_upload and os.path.exists(file_path):
                os.remove(file_path)

            uploaded_count += 1

        except Exception as e:
            failed_count += 1
            frappe.log_error(
                title="S3 Upload Error",
                message=f"Failed to upload {file_data.name}: {str(e)}\n{frappe.get_traceback()}",
            )
            continue

    if failed_count:
        frappe.log_error(
            title="S3 Upload Summary",
            message=f"S3 Upload: {uploaded_count} uploaded, {failed_count} failed",
        )


def bulk_migrate_files():
    """Background job: Migrate all local files to S3.

    Fetches the total count of pending files upfront, then processes them
    in fixed-size batches with a bounded loop. Progress events are broadcast
    via Frappe's realtime channel for the browser UI.
    """
    settings = frappe.get_cached_doc("AWS Settings")
    if not settings.enable_aws or not settings.enable_s3:
        return

    exempt_doctypes = list({d.exempt_doctype for d in settings.exempt_doctypes})
    batch_size = cint(settings.s3_batch_size) or 50

    from aws_integration.s3.client import S3Client

    try:
        s3_client = S3Client()
    except Exception as e:
        frappe.log_error(
            title="S3 Migration Error",
            message=f"Failed to initialize S3 client: {str(e)}\n{frappe.get_traceback()}",
        )
        return

    # Count total pending files upfront to bound the loop
    filters = _get_pending_filters(exempt_doctypes)
    total_pending = frappe.db.count("File", filters)

    if not total_pending:
        return

    max_batches = (total_pending // batch_size) + 2  # small margin for safety
    total_uploaded = 0
    total_failed = 0

    for _ in range(max_batches):
        files = frappe.get_all(
            "File",
            filters=_get_pending_filters(exempt_doctypes),
            fields=["name", "file_name", "file_url", "is_private", "attached_to_doctype"],
            limit_page_length=batch_size,
            order_by="creation asc",
        )

        if not files:
            break

        for file_data in files:
            try:
                file_doc = frappe.get_doc("File", file_data.name)
                file_path = file_doc.get_full_path()

                if not os.path.exists(file_path):
                    # Log and skip — do NOT modify file_url, which would break
                    # the File document and exclude it from all future retry logic.
                    frappe.log_error(
                        title="S3 Migration: File Not Found",
                        message=f"Local file not found for {file_doc.name}: {file_path}",
                    )
                    total_failed += 1
                    continue

                # Acquire a row-level lock to prevent a concurrent instant-upload
                # worker from uploading the same file at the same time.
                lock_result = frappe.db.sql(
                    "SELECT name FROM `tabFile` WHERE name=%s AND is_on_s3=0 FOR UPDATE",
                    file_doc.name,
                )
                if not lock_result:
                    continue

                s3_key = s3_client.upload_file(file_doc)

                new_file_url = (
                    f"/api/method/aws_integration.api.s3.generate_file"
                    f"?key={s3_key}&file_name={file_doc.file_name}"
                )

                frappe.db.set_value(
                    "File",
                    file_doc.name,
                    {
                        "file_url": new_file_url,
                        "s3_key": s3_key,
                        "is_on_s3": 1,
                        "s3_uploaded_at": now_datetime(),
                    },
                    update_modified=False,
                )

                # Commit BEFORE removing the local file so that a failed commit
                # never leaves the file permanently lost.
                frappe.db.commit()

                if settings.delete_local_after_upload and os.path.exists(file_path):
                    os.remove(file_path)

                total_uploaded += 1

            except Exception as e:
                total_failed += 1
                frappe.log_error(
                    title="S3 Migration Error",
                    message=f"Failed to upload {file_data.name}: {str(e)}\n{frappe.get_traceback()}",
                )
        frappe.publish_realtime(
            "s3_migration_progress",
            {"uploaded": total_uploaded, "failed": total_failed, "total": total_pending},
        )

    frappe.publish_realtime(
        "s3_migration_complete",
        {"uploaded": total_uploaded, "failed": total_failed},
    )
    if total_failed:
        frappe.log_error(
            title="S3 Migration Summary",
            message=f"S3 Migration Complete: {total_uploaded} uploaded, {total_failed} failed",
        )


def cleanup_local_s3_files():
    """Background job: Delete local copies of files already uploaded to S3.

    Queries files where is_on_s3=1, checks if a local copy still exists
    on disk, and deletes it. Publishes realtime progress events.
    """
    settings = frappe.get_cached_doc("AWS Settings")
    if not settings.enable_aws or not settings.enable_s3:
        return

    batch_size = cint(settings.s3_batch_size) or 50
    total_deleted = 0
    total_skipped = 0
    total_missing = 0

    total_on_s3 = frappe.db.count("File", {"is_folder": 0, "is_on_s3": 1})
    if not total_on_s3:
        return

    max_batches = (total_on_s3 // batch_size) + 2

    for _ in range(max_batches):
        files = frappe.get_all(
            "File",
            filters={"is_folder": 0, "is_on_s3": 1},
            fields=["name", "file_name", "file_url", "is_private"],
            limit_page_length=batch_size,
            order_by="creation asc",
        )

        if not files:
            break

        for file_data in files:
            try:
                # Build the expected local path from the original file_name
                site_path = frappe.get_site_path(
                    "private" if file_data.is_private else "public",
                    "files",
                    file_data.file_name,
                )

                if os.path.exists(site_path):
                    os.remove(site_path)
                    total_deleted += 1
                else:
                    total_missing += 1

            except Exception as e:
                total_skipped += 1
                frappe.log_error(
                    title="S3 Cleanup Error",
                    message=f"Failed to clean up {file_data.name}: {str(e)}",
                )

        frappe.publish_realtime(
            "s3_cleanup_progress",
            {
                "deleted": total_deleted,
                "missing": total_missing,
                "skipped": total_skipped,
                "total": total_on_s3,
            },
        )

        # All files in this batch are on S3 — the result set is static.
        # Since we process every row, break if this was a partial batch.
        if len(files) < batch_size:
            break

    frappe.publish_realtime(
        "s3_cleanup_complete",
        {
            "deleted": total_deleted,
            "missing": total_missing,
            "skipped": total_skipped,
        },
    )

    if total_skipped:
        frappe.log_error(
            title="S3 Local Cleanup Summary",
            message=f"S3 Local Cleanup: {total_deleted} deleted, {total_missing} already gone, {total_skipped} skipped",
        )


def _get_pending_filters(exempt_doctypes):
    """Build filters dict for querying local files not yet on S3."""
    filters = {
        "is_folder": 0,
        "file_url": ("like", "/%"),
        "is_on_s3": 0,
    }
    if exempt_doctypes:
        filters["attached_to_doctype"] = ("not in", exempt_doctypes)
    return filters
