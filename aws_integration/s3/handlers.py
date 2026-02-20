import os
from urllib.parse import parse_qs, quote, urlparse

import frappe
from frappe.utils import now_datetime


S3_API_PREFIX = "/api/method/aws_integration.api.s3.generate_file"


def on_file_upload(doc, method):
    """Upload file to S3 immediately after it's created in ERP.

    Enqueues a short background job so the user's request is not blocked.
    Only runs when 'Instant Upload to S3' is enabled in AWS Settings.
    """
    if doc.is_folder or doc.is_on_s3:
        return

    # Only act on local files
    if not doc.file_url or not doc.file_url.startswith("/"):
        return

    # Dedup-created docs copy the S3 API URL from the original file.
    # Mark them as already on S3 instead of trying to upload again.
    if doc.file_url.startswith(S3_API_PREFIX):
        _mark_dedup_file_as_s3(doc)
        return

    if doc.file_url.startswith("/api/method/"):
        return

    try:
        settings = frappe.get_cached_doc("AWS Settings")
        if not settings.enable_aws or not settings.enable_s3:
            return
        if not settings.upload_to_s3_on_save:
            return

        # Check exempt doctypes
        exempt_doctypes = {d.exempt_doctype for d in settings.exempt_doctypes}
        if doc.attached_to_doctype and doc.attached_to_doctype in exempt_doctypes:
            return

        frappe.enqueue(
            "aws_integration.s3.handlers._upload_single_file",
            queue="short",
            timeout=300,
            file_name=doc.name,
        )
    except Exception:
        # Don't block file creation if S3 check fails
        pass


def _upload_single_file(file_name):
    """Background job: Upload a single file to S3.

    Uses a SELECT FOR UPDATE database lock to prevent race conditions when
    both the instant-upload handler and the hourly scheduler attempt to
    upload the same file concurrently. The commit is issued before the local
    file is removed so that a commit failure never leaves the file in a
    permanently lost state.
    """
    from aws_integration.s3.client import S3Client

    file_doc = frappe.get_doc("File", file_name)

    # Re-check is_on_s3 with a fresh DB read to catch any cached-doc stale data
    if frappe.db.get_value("File", file_name, "is_on_s3"):
        return

    # Acquire a row-level lock; if another worker already claimed this file
    # (i.e. set is_on_s3=1 between our check above and now), the result will
    # be empty and we bail out without uploading again.
    lock_result = frappe.db.sql(
        "SELECT name FROM `tabFile` WHERE name=%s AND is_on_s3=0 FOR UPDATE",
        file_name,
    )
    if not lock_result:
        return

    # Dedup-created docs may have an S3 API URL as file_url.
    # Mark them as on S3 and bail out instead of calling get_full_path().
    if file_doc.file_url and file_doc.file_url.startswith(S3_API_PREFIX):
        _mark_dedup_file_as_s3(file_doc)
        frappe.db.commit()
        return

    file_path = file_doc.get_full_path()
    if not os.path.exists(file_path):
        return

    settings = frappe.get_cached_doc("AWS Settings")
    s3_client = S3Client()
    s3_key = s3_client.upload_file(file_doc)

    new_file_url = (
        f"/api/method/aws_integration.api.s3.generate_file"
        f"?key={quote(s3_key, safe='/')}&file_name={quote(file_doc.file_name)}"
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

    # Commit BEFORE removing the local file so that a failed commit never
    # leaves the file permanently lost (is_on_s3 still 0 but file gone).
    frappe.db.commit()

    if settings.delete_local_after_upload and os.path.exists(file_path):
        os.remove(file_path)

    # Notify the browser so the File form auto-refreshes with the S3 indicator
    frappe.publish_realtime("s3_upload_complete", {"file_name": file_doc.name})


def _mark_dedup_file_as_s3(doc):
    """Mark a dedup-created File doc as already on S3.

    When Frappe's content_hash dedup copies an S3 API URL to a new File doc,
    the doc has is_on_s3=0 and no s3_key. This extracts the key from the URL
    and sets the correct S3 fields so the file shows up as "Stored on S3".
    """
    parsed = urlparse(doc.file_url)
    params = parse_qs(parsed.query)
    s3_key = params.get("key", [None])[0]

    if s3_key:
        # Preserve the original upload timestamp from the source file
        original_uploaded_at = frappe.db.get_value(
            "File", {"s3_key": s3_key, "is_on_s3": 1}, "s3_uploaded_at"
        )

        frappe.db.set_value(
            "File",
            doc.name,
            {
                "is_on_s3": 1,
                "s3_key": s3_key,
                "s3_uploaded_at": original_uploaded_at or now_datetime(),
            },
            update_modified=False,
        )


def on_file_delete(doc, method):
    """Handle File deletion - also delete the object from S3 if it was uploaded.

    Called via the doc_events hook on File.on_trash. If AWS or S3 integration
    is disabled, or the file was never uploaded, this is a no-op.

    Args:
        doc: The File document being deleted.
        method (str): The hook method name that triggered this handler
            (always "on_trash" in normal usage).

    Returns:
        None

    Raises:
        Does not raise. Errors are captured with frappe.log_error so that a
        failed S3 deletion does not block the local file deletion.
    """
    if not doc.is_on_s3 or not doc.s3_key:
        return

    try:
        settings = frappe.get_cached_doc("AWS Settings")
        if not settings.enable_aws or not settings.enable_s3:
            return

        if not settings.delete_s3_on_trash:
            return

        from aws_integration.s3.client import S3Client

        s3_client = S3Client()
        s3_client.delete_file(doc.s3_key)

    except Exception as e:
        frappe.log_error(
            title="S3 Delete Error",
            message=f"Failed to delete {doc.s3_key} from S3: {str(e)}\n{frappe.get_traceback()}",
        )
