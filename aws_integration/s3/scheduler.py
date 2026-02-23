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
        "s3_upload_skipped": 0,
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
                frappe.db.set_value("File", file_data.name, "s3_upload_skipped", 1, update_modified=False)
                frappe.db.commit()
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
                frappe.db.set_value("File", file_doc.name, "local_deleted", 1, update_modified=False)
                frappe.db.commit()

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
    """Coordinator: fan out file migration into parallel batch jobs."""
    settings = frappe.get_cached_doc("AWS Settings")
    if not settings.enable_aws or not settings.enable_s3:
        return

    # Prevent duplicate migrations from overlapping clicks
    lock_key = "s3_bulk_migration_running"
    if frappe.cache.get_value(lock_key):
        return
    frappe.cache.set_value(lock_key, 1, expires_in_sec=3600)

    exempt_doctypes = list({d.exempt_doctype for d in settings.exempt_doctypes})
    batch_size = cint(settings.s3_batch_size) or 50

    filters = _get_pending_filters(exempt_doctypes)
    pending_files = frappe.get_all(
        "File", filters=filters, fields=["name"], order_by="creation asc",
        limit_page_length=0,
    )

    if not pending_files:
        frappe.cache.delete_value(lock_key)
        return

    total = len(pending_files)
    chunks = []
    for i in range(0, total, batch_size):
        chunks.append([f.name for f in pending_files[i:i + batch_size]])

    migration_id = frappe.generate_hash(length=10)

    # Store progress in cache. Updates are protected by a Redis lock
    # in _update_migration_progress. TTL ensures cleanup on crash.
    frappe.cache.set_value(f"s3_migration:{migration_id}", {
        "total_batches": len(chunks),
        "completed_batches": 0,
        "uploaded": 0,
        "failed": 0,
    }, expires_in_sec=3600)

    for chunk in chunks:
        frappe.enqueue(
            _migrate_file_batch,
            queue="short",
            timeout=600,
            file_names=chunk,
            migration_id=migration_id,
            total=total,
        )


def _migrate_file_batch(file_names, migration_id, total):
    """Worker: upload a batch of files to S3."""
    settings = frappe.get_cached_doc("AWS Settings")
    from aws_integration.s3.client import S3Client

    try:
        s3_client = S3Client()
    except Exception as e:
        frappe.log_error(title="S3 Migration Error", message=f"Failed to init S3 client: {e}")
        _update_migration_progress(migration_id, 0, len(file_names), total)
        return

    uploaded = 0
    failed = 0

    for file_name in file_names:
        try:
            file_doc = frappe.get_doc("File", file_name)

            lock_result = frappe.db.sql(
                "SELECT name FROM `tabFile` WHERE name=%s AND is_on_s3=0 FOR UPDATE",
                file_doc.name,
            )
            if not lock_result:
                continue

            file_path = file_doc.get_full_path()

            if not os.path.exists(file_path):
                frappe.db.set_value("File", file_name, "s3_upload_skipped", 1, update_modified=False)
                frappe.db.commit()
                failed += 1
                continue

            s3_key = s3_client.upload_file(file_doc)
            new_file_url = (
                f"/api/method/aws_integration.api.s3.generate_file"
                f"?key={s3_key}&file_name={file_doc.file_name}"
            )

            frappe.db.set_value("File", file_doc.name, {
                "file_url": new_file_url,
                "s3_key": s3_key,
                "is_on_s3": 1,
                "s3_uploaded_at": now_datetime(),
            }, update_modified=False)
            frappe.db.commit()

            if settings.delete_local_after_upload and os.path.exists(file_path):
                os.remove(file_path)
                frappe.db.set_value("File", file_doc.name, "local_deleted", 1, update_modified=False)
                frappe.db.commit()

            uploaded += 1

        except Exception:
            failed += 1
            frappe.log_error(
                title="S3 Migration Error",
                message=f"Failed to upload {file_name}: {frappe.get_traceback()}",
            )

    _update_migration_progress(migration_id, uploaded, failed, total)


def _update_migration_progress(migration_id, batch_uploaded, batch_failed, total):
    """Update migration progress under a Redis lock for atomicity."""
    cache_key = f"s3_migration:{migration_id}"
    lock_key = f"s3_migration_lock:{migration_id}"

    with frappe.cache.lock(lock_key, timeout=5):
        progress = frappe.cache.get_value(cache_key) or {}

        progress["uploaded"] = progress.get("uploaded", 0) + batch_uploaded
        progress["failed"] = progress.get("failed", 0) + batch_failed
        progress["completed_batches"] = progress.get("completed_batches", 0) + 1

        frappe.cache.set_value(cache_key, progress, expires_in_sec=3600)

    frappe.publish_realtime("s3_migration_progress", {
        "uploaded": progress["uploaded"],
        "failed": progress["failed"],
        "total": total,
    })

    if progress["completed_batches"] >= progress.get("total_batches", 0):
        frappe.publish_realtime("s3_migration_complete", {
            "uploaded": progress["uploaded"],
            "failed": progress["failed"],
        })
        frappe.cache.delete_value(cache_key)
        frappe.cache.delete_value("s3_bulk_migration_running")


def cleanup_local_s3_files():
    """Background job: Delete local copies of files already uploaded to S3.

    Queries files where is_on_s3=1 and local_deleted=0, checks if a local
    copy still exists on disk, and deletes it. Publishes realtime progress events.
    """
    settings = frappe.get_cached_doc("AWS Settings")
    if not settings.enable_aws or not settings.enable_s3:
        return

    batch_size = cint(settings.s3_batch_size) or 50
    total_deleted = 0
    total_skipped = 0
    total_missing = 0

    cleanup_filters = {"is_folder": 0, "is_on_s3": 1, "local_deleted": 0}
    total_pending = frappe.db.count("File", cleanup_filters)
    if not total_pending:
        return

    max_batches = (total_pending // batch_size) + 2

    for _ in range(max_batches):
        files = frappe.get_all(
            "File",
            filters=cleanup_filters,
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

                # Validate resolved path stays within the expected directory
                real_path = os.path.realpath(site_path)
                expected_base = os.path.realpath(
                    frappe.get_site_path(
                        "private" if file_data.is_private else "public", "files"
                    )
                )
                if not real_path.startswith(expected_base + os.sep):
                    frappe.log_error(
                        title="S3 Cleanup: Path Traversal Blocked",
                        message=f"Blocked deletion of {site_path} for {file_data.name}",
                    )
                    total_skipped += 1
                    continue

                if os.path.exists(real_path):
                    os.remove(real_path)
                    total_deleted += 1
                else:
                    total_missing += 1

                # Mark as locally deleted whether the file existed or was already gone
                frappe.db.set_value("File", file_data.name, "local_deleted", 1, update_modified=False)

            except Exception as e:
                total_skipped += 1
                frappe.log_error(
                    title="S3 Cleanup Error",
                    message=f"Failed to clean up {file_data.name}: {str(e)}",
                )

        # Commit after each batch so progress is not lost on crash
        frappe.db.commit()

        frappe.publish_realtime(
            "s3_cleanup_progress",
            {
                "deleted": total_deleted,
                "missing": total_missing,
                "skipped": total_skipped,
                "total": total_pending,
            },
        )

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
        "s3_upload_skipped": 0,
    }
    if exempt_doctypes:
        filters["attached_to_doctype"] = ("not in", exempt_doctypes)
    return filters
