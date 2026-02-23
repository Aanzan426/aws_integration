# PRD: S3 File Storage Integration for Frappe/ERPNext

**Version:** 2.0
**Date:** 2026-02-20
**App:** AWS Integration (`aws_integration`)
**Status:** Implemented (Stages 1-4)

---

## 1. Executive Summary

This PRD documents the S3 file storage integration for Frappe/ERPNext. Files uploaded to ERP are offloaded to Amazon S3, reducing local disk usage while maintaining seamless file preview and download via presigned URLs. The solution extends the existing **AWS Integration** app which already manages AWS credentials and SES email.

### Key Objectives
- Reduce server storage consumption by migrating files to S3
- Maintain seamless file preview and attachment functionality
- Mirror Frappe's folder structure in S3 (stripping the `Home/` prefix)
- Support selective exemption of specific DocTypes
- Support both instant upload (on file creation) and scheduled batch upload
- Configurable S3 file deletion when files are removed from ERP
- Handle database backup uploads to S3 (planned)

---

## 2. AWS Settings DocType

The existing `AWS Settings` Single DocType has been extended with S3 configuration via **Tab Breaks**.

### 2.1 Form Layout (Tabs)

| Tab | Depends On | Contents |
|-----|-----------|----------|
| *(Top-level)* | - | `enable_aws` (Check), `enable_s3` (Check, depends_on: enable_aws) |
| **General** | `enable_aws` | AWS Credentials: access key, secret key, region |
| **SES Settings** | `enable_aws` | Email config: source email, sender name, batch size |
| **S3 Storage** | `enable_s3` | S3 Configuration + Upload Settings + Exempt DocTypes |
| **S3 Backups** | `enable_s3` | Backup bucket, retention settings |

### 2.2 S3 Storage Tab Fields

#### S3 Configuration Section
| Field | Type | Label | Notes |
|-------|------|-------|-------|
| `s3_bucket_name` | Data | S3 Bucket Name | `mandatory_depends_on: enable_s3` |
| `s3_bucket_region` | Select | S3 Bucket Region | Falls back to General region if blank |
| `s3_folder_prefix` | Data | S3 Folder Prefix | Defaults to site name if blank |

#### Upload Settings Section (`depends_on: enable_s3`)
| Field | Type | Default | Label | Description |
|-------|------|---------|-------|-------------|
| `upload_to_s3_on_save` | Check | 0 | Instant Upload to S3 | Upload files immediately on attachment via background job |
| `delete_local_after_upload` | Check | 1 | Delete Local File After S3 Upload | Remove local copy after confirmed S3 upload |
| `delete_s3_on_trash` | Check | 1 | Delete S3 File on ERP Deletion | Delete S3 object when File doc is trashed |
| `s3_upload_batch_size` | Int | 50 | Upload Batch Size | Files per scheduler run |
| `s3_presigned_url_expiry` | Int | 900 | Presigned URL Expiry (seconds) | Default: 15 minutes |

#### Exempt DocTypes Section (`depends_on: enable_s3`)
| Field | Type | Label | Options |
|-------|------|-------|---------|
| `exempt_doctypes` | Table | Exempt DocTypes | S3 Exempt DocType (child table) |

### 2.3 S3 Backups Tab Fields

| Field | Type | Default | Label |
|-------|------|---------|-------|
| `enable_s3_backups` | Check | 0 | Enable S3 Backups |
| `s3_backup_frequency` | Select | Daily | Backup Frequency (Daily/Weekly/Monthly/None) |
| `s3_backup_files` | Check | 1 | Backup Files (include public/private tarballs) |
| `s3_backup_timeout` | Int | 6000 | Backup Job Timeout (seconds) |
| `s3_backup_bucket_name` | Data | - | Backup Bucket Name (defaults to main bucket) |
| `s3_backup_folder_prefix` | Data | - | Backup Folder Path (S3 key prefix) |
| `s3_backup_retention_count` | Int | 0 | Keep Last N Backups (0 = disabled) |
| `s3_backup_retention_days` | Int | 0 | Delete Backups Older Than N days (0 = disabled) |
| `s3_backup_notify_email` | Data | - | Notify Email |
| `s3_backup_notify_success` | Check | 0 | Send Email for Successful Backup |

### 2.4 DocType Settings
- `issingle: 1`
- `track_changes: 1`
- Permissions: System Manager (full CRUD)

---

## 3. Child Table: S3 Exempt DocType

**`istable: 1`** - Used in `exempt_doctypes` field of AWS Settings.

| Field | Type | Label | Required |
|-------|------|-------|----------|
| `exempt_doctype` | Link (DocType) | DocType | Yes |
| `reason` | Small Text | Reason | No |

Files attached to exempt DocTypes are skipped by both the scheduler and instant upload.

---

## 4. S3 Key Structure

S3 keys mirror Frappe's folder hierarchy with `Home/` stripped:

```
{prefix}/{private|public}/{folder}/{hash}_{filename}
```

### Key Generation Rules
- `prefix` = `s3_folder_prefix` or `frappe.local.site` (e.g. `unity`)
- `private/public` = based on `file_doc.is_private`
- `folder` = Frappe folder with `Home/` stripped:
  - `Home/Attachments` -> `Attachments`
  - `Home/Baby Walnut Wakad-2026-2027` -> `Baby Walnut Wakad-2026-2027`
  - `Home` -> *(no subfolder)*
- `hash` = 8-char random uppercase string (collision avoidance)

### Examples
```
unity/public/Baby Walnut Wakad-2026-2027/ZHUENX2M_JA84-WAJA84-(2026-2027)-001.jpg
unity/private/Attachments/A3BKX9QP_salary_slip.pdf
unity/public/X7KMRT4P_logo.png
```

---

## 5. File URL Rewriting

After S3 upload, the File document's `file_url` is rewritten to the API endpoint:

```
# Before (local)
/files/JA84-WAJA84-(2026-2027)-001.jpg
/private/files/salary_slip.pdf

# After (S3)
/api/method/aws_integration.api.s3.generate_file?key=public/Baby%20Walnut%20Wakad-2026-2027/ZHUENX2M_JA84-WAJA84-(2026-2027)-001.jpg&file_name=JA84-WAJA84-(2026-2027)-001.jpg
```

The `generate_file` API generates a presigned URL and redirects the browser to it.

---

## 6. Custom Fields on File DocType

Added via `after_migrate` (not fixtures) in `aws_integration.s3.setup.after_migrate`:

| Field | Type | Label | Section |
|-------|------|-------|---------|
| `s3_key` | Small Text (Read Only) | S3 Key | S3 Info (collapsible) |
| `is_on_s3` | Check (Read Only) | Uploaded to S3 | S3 Info |
| `s3_uploaded_at` | Datetime (Read Only) | S3 Upload Date | S3 Info |
| `local_deleted` | Check (Read Only) | Local File Deleted | S3 Info |

---

## 7. Upload Mechanisms

### 7.1 Instant Upload (on file creation)

When `upload_to_s3_on_save` is enabled:

1. `File.after_insert` hook fires `on_file_upload`
2. Checks: S3 enabled? Instant upload on? Not exempt doctype? Is local file?
3. Enqueues `_upload_single_file` on `short` queue (non-blocking, 300s timeout)
4. Background job: uploads to S3, rewrites `file_url`, optionally deletes local file and sets `local_deleted=1`

### 7.2 Scheduled Batch Upload (hourly)

Runs via `scheduler_events.hourly`:

1. `upload_pending_files` queries local files (`file_url LIKE "/%"`, `is_on_s3 = 0`)
2. Excludes exempt doctypes at query level
3. Processes in batches of `s3_upload_batch_size` (default: 50)
4. For each file: upload to S3, rewrite `file_url`, optionally delete local and set `local_deleted=1`
5. Logs success/failure counts

### 7.3 Bulk Migration (one-time)

Triggered via "Migrate All Files to S3" button in AWS Settings:

1. Enqueued as background job on `long` queue (3600s timeout)
2. Bounded loop: `max_batches = (total_pending // 100) + 2`
3. Excludes exempt doctypes at query level
4. Publishes realtime progress events (`s3_migration_progress`, `s3_migration_complete`)
5. Breaks on empty batch or no progress (prevents infinite loop)

---

## 8. API Endpoints

All in `aws_integration/api/s3.py`:

### 8.1 `generate_file` (allow_guest=True)
- **Params:** `key` (S3 key), `file_name` (display name)
- **Flow:** Find File by s3_key -> check permissions for private files -> generate presigned URL -> redirect
- **Used as:** The `file_url` stored on File documents after S3 upload

### 8.2 `get_file_preview`
- **Params:** `file_name` (File doc name) or `file_url`
- **Returns:** `{"url": presigned_url, "content_type": "...", "file_name": "..."}`
- **Used by:** File form "View on S3" button

### 8.3 `test_s3_connection`
- **Requires:** System Manager role
- **Returns:** `{"success": bool, "message": str}`
- **Uses:** `head_bucket` API call

### 8.4 `migrate_files_to_s3`
- **Requires:** System Manager role
- **Returns:** Status message with file count
- **Action:** Enqueues `bulk_migrate_files` background job

---

## 9. Hooks Configuration

```python
# hooks.py

doctype_js = {
    "File": "public/js/file.js"
}

scheduler_events = {
    "all": ["aws_integration.utils.email.flush_email_queue"],
    "hourly": ["aws_integration.s3.scheduler.upload_pending_files"]
}

doc_events = {
    "File": {
        "after_insert": "aws_integration.s3.handlers.on_file_upload",
        "on_trash": "aws_integration.s3.handlers.on_file_delete"
    }
}

after_migrate = ["aws_integration.s3.setup.after_migrate"]
```

---

## 10. Frontend

### 10.1 AWS Settings JS (`aws_settings.js`)

**S3 Files** dropdown:
- **Test S3 Connection** — verify bucket access
- **Migrate All Files to S3** — enqueue bulk migration with realtime progress bar
- **S3 Status** — dashboard showing file counts, sizes, migration progress, recent errors
- **Clean Up Local Files** — delete local copies with realtime progress bar

**S3 Backups** dropdown:
- **Take Backup Now** — queue a backup job with status pipeline UI
- **Upload Local Backups** — scan and upload pre-existing local backup files
- **Backup Logs** — navigate to S3 Backup Log list

Realtime listeners for: `s3_migration_progress/complete`, `s3_cleanup_progress/complete`, `s3_backup_progress`

### 10.2 File Form JS (`public/js/file.js`)
- Green **"Stored on S3"** indicator pill when `is_on_s3=1`
- Green **"Stored on S3 (local deleted)"** indicator when `is_on_s3=1` and `local_deleted=1`
- **"Upload to S3"** button for local files not yet on S3
- Auto-refreshes when background S3 upload completes (via realtime events)

### 10.3 S3 Backup Log JS (`s3_backup_log.js`)
- **Download icons** on file URL fields — click to get presigned S3 download URL
- **Size formatting** — file sizes displayed in human-readable format (KB, MB, GB)
- **Delete Local Files** button — visible when `status=Success` and `local_cleaned=0`

---

## 11. S3 Client (`s3/client.py`)

`S3Client` class wrapping boto3:

| Method | Purpose |
|--------|---------|
| `get_s3_key(file_doc)` | Generate folder-mirrored key with hash prefix |
| `get_full_s3_key(key)` | Prepend site prefix to relative key |
| `upload_file(file_doc)` | Upload with multipart for files > 5MB; returns relative key |
| `generate_presigned_url(key, expiry, file_name)` | Time-limited GET URL with content disposition |
| `download_file(key)` | Returns raw bytes |
| `delete_file(key)` | Deletes S3 object |
| `test_connection()` | `head_bucket` probe; returns `{"success": bool, "message": str}` |
| `file_exists(key)` | `head_object` probe; returns bool |

---

## 12. File Structure (Implemented)

```
aws_integration/
  aws_integration/
    aws_integration/
      doctype/
        aws_settings/
          aws_settings.json           # Tabs, S3 fields, backup settings, track_changes
          aws_settings.py             # test_s3_connection method
          aws_settings.js             # S3 Files/Backups buttons, status dashboard, realtime listeners
        s3_exempt_doctype/            # Child table DocType
          __init__.py
          s3_exempt_doctype.json
          s3_exempt_doctype.py
        s3_backup_log/                # Backup tracking DocType
          s3_backup_log.json          # Status, file URLs, sizes, retention fields
          s3_backup_log.py            # Controller: autoname, clear_old_logs
          s3_backup_log.js            # Download icons, size formatting, delete local button
    s3/                               # S3 module
      __init__.py
      client.py                       # S3Client class (boto3 wrapper)
      scheduler.py                    # upload_pending_files, bulk_migrate_files, cleanup_local_s3_files
      handlers.py                     # on_file_upload, _upload_single_file, on_file_delete
      setup.py                        # after_migrate: custom fields on File (s3_key, is_on_s3, s3_uploaded_at, local_deleted)
      backup.py                       # take_s3_backup, _run_backup, rotation, scheduler, download URLs
    api/                              # API module
      __init__.py
      s3.py                           # generate_file, test_s3_connection, migrate, cleanup, status, preview
    public/
      js/
        file.js                       # File form: S3 indicator + Upload to S3 button
    hooks.py                          # scheduler, doc_events, after_migrate, doctype_js
```

---

## 13. Data Flow Diagrams

### 13.1 Instant Upload Flow

```
[User attaches file to ERP]
        |
        v
[File saved locally + File doc created]
        |
        v
[after_insert hook: on_file_upload]
        |
        v
[Check: S3 enabled? Instant upload on? Not exempt?]
        |
    [No] --> [Done - scheduler picks up later]
    [Yes]
        |
        v
[Enqueue _upload_single_file (short queue)]
        |
        v
[Background: Upload to S3]
        |
        v
[Rewrite file_url to generate_file API URL]
        |
        v
[Delete local file (if configured)]
```

### 13.2 File Access Flow

```
[Browser requests file_url]
        |
        v
[/api/method/aws_integration.api.s3.generate_file?key=...&file_name=...]
        |
        v
[Find File doc by s3_key]
        |
        v
[Private?] --[Yes]--> [Check user permissions on attached doc]
        |
        v
[Generate presigned URL (15 min expiry)]
        |
        v
[HTTP 302 Redirect to presigned S3 URL]
        |
        v
[Browser loads file directly from S3]
```

### 13.3 File Deletion Flow

```
[User deletes File from ERP]
        |
        v
[on_trash hook: on_file_delete]
        |
        v
[Check: is_on_s3? delete_s3_on_trash enabled?]
        |
    [No] --> [Done - S3 object preserved]
    [Yes]
        |
        v
[S3Client.delete_file(s3_key)]
```

---

## 14. Implementation Status

| Phase | Status | Details |
|-------|--------|---------|
| **Stage 1: Foundation** | Done | AWS Settings fields (tabs), S3Client, S3 Exempt DocType, after_migrate setup, Test Connection |
| **Stage 2: File Upload** | Done | Hourly scheduler, instant upload on save, bulk migration, exemption logic |
| **Stage 3: File Serving** | Done | generate_file API, presigned URL redirect, on_trash handler, File form JS |
| **Stage 4: Backups** | Done | S3 Backup Log, scheduled backups, retention, progress UI, download URLs, local cleanup tracking |
| **Stage 5: Local Tracking** | Done | `local_deleted` field on File, path traversal protection, cleanup optimization |

---

## 15. Pending Work

### Stage 6: Polish
- Restore file from S3 back to local storage
- File list view S3 indicator/badge

---

## 16. Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `boto3` | >= 1.26.0 | AWS SDK for Python (already in app) |
| Frappe Framework | >= 15.0 | Core framework |

---

## 17. Security

- S3 bucket must NOT have public access
- All file access goes through `generate_file` API with permission checks
- Private files require login + permission on `attached_to_doctype`
- Presigned URLs expire after configurable duration (default: 15 minutes)
- AWS credentials stored using Frappe's Password fieldtype
- `test_s3_connection` and `migrate_files_to_s3` restricted to System Manager role
