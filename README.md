# AWS Integration for Frappe/ERPNext

A comprehensive AWS integration app for [Frappe Framework](https://frappeframework.com/) that provides **S3 file storage**, **S3 site backups**, and **SES email sending** — all configurable from a single **AWS Settings** DocType.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [General AWS Settings](#general-aws-settings)
  - [S3 File Storage](#s3-file-storage)
  - [S3 Backups](#s3-backups)
  - [SES Email](#ses-email)
- [Usage Guide](#usage-guide)
  - [File Storage Operations](#file-storage-operations)
  - [Backup Operations](#backup-operations)
  - [Email Operations](#email-operations)
- [Architecture](#architecture)
- [S3-Compatible Providers](#s3-compatible-providers)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### 📦 S3 File Storage
- **Automatic uploads** — Files attached to documents are uploaded to S3 instantly (via background job) or on a scheduled hourly basis
- **Presigned URL file access** — Secure, time-limited URLs with built-in Frappe permission checks for private files
- **Folder-mirrored key structure** — S3 keys mirror Frappe's folder hierarchy (`{prefix}/{private|public}/{folder}/{filename}`)
- **Collision-safe naming** — Automatic content-hash prefixing when files with the same name but different content are detected
- **Multipart uploads** — Files larger than 5 MB use S3 multipart upload for reliability
- **DocType exemptions** — Exclude specific DocTypes from S3 upload (e.g., keep Print Format PDFs local)
- **Bulk migration** — One-click migration of all existing local files to S3 with real-time progress tracking
- **Local file cleanup** — Delete local copies of files already on S3 to reclaim disk space, with path traversal protection
- **Per-file controls** — "Upload to S3" and "Delete Local File" buttons on individual File documents
- **Content dedup support** — Frappe's content-hash deduplication works seamlessly with S3-stored files
- **S3-compatible providers** — Works with Backblaze B2, Wasabi, MinIO, and any S3-compatible service via custom endpoint URLs

### 💾 S3 Site Backups
- **On-demand and scheduled** — Take backups manually or automatically (Daily / Weekly / Monthly)
- **Full site backup** — Database dump (`.sql.gz`), site config (`.json`), public files (`.tar`), and private files (`.tar`)
- **Dedicated backup bucket** — Optionally store backups in a separate S3 bucket from file storage
- **Retention policies** — Automatically delete old backups by count ("keep last N") and/or age ("delete older than N days")
- **Backup log tracking** — Every backup is tracked in an `S3 Backup Log` DocType with status, size, timestamps, and S3 keys
- **Real-time progress UI** — Live pipeline visualization (Queued → Generating → Uploading → Done) with animated indicators
- **Upload existing backups** — Scan the local backup directory and upload previously generated backups to S3
- **Presigned download URLs** — Download backup files directly from S3 via time-limited URLs
- **Email notifications** — Get notified on backup success and/or failure
- **Auto-retry** — Failed backups are automatically retried up to 2 times before marking as failed
- **Local cleanup** — Automatic or manual deletion of local backup files after successful S3 upload
- **Configurable timeout** — Adjust the background job timeout for large sites (default: 100 minutes)
- **Confirmation dialogs** — All destructive actions require explicit confirmation

### 📧 SES Email
- **Amazon SES v2 integration** — Send emails via AWS SES with full HTML support
- **Email queue override** — Replaces Frappe's default email queue flusher with SES-powered sending
- **Batch sending** — Configurable batch size with rate limiting (1-second pause between batches)
- **SES logging** — All sent emails are logged in the `AWS SES Logs` DocType with message ID, recipients (To/CC/BCC), and status
- **Automatic handler switching** — Enabling/disabling AWS automatically toggles between SES and Frappe's default email queue

---

## Prerequisites

- **Frappe Framework** v15.x (`>=15.0.0, <16.0.0`)
- **Python** 3.11+
- **boto3** (installed automatically as a dependency)
- An **AWS Account** with:
  - IAM credentials (Access Key ID + Secret Access Key)
  - S3 bucket(s) created with appropriate permissions
  - SES verified sender identity (for email features)

---

## Installation

### Install the app

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/UnityAppSuite/aws_integration.git --branch develop
bench --site <your-site> install-app aws_integration
```

### Post-installation setup

```bash
bench --site <your-site> migrate    # Creates custom fields on File DocType
bench build --app aws_integration   # Builds client-side assets
bench --site <your-site> clear-cache
```

### Verify installation

Navigate to **AWS Settings** in Frappe Desk (`/app/aws-settings`) to begin configuration.

---

## Configuration

All settings are managed from the **AWS Settings** DocType (`/app/aws-settings`).

### General AWS Settings

| Field | Description |
|---|---|
| **Enable AWS** | Master toggle — must be enabled for any AWS feature to work |
| **AWS Access Key ID** | Your IAM user's access key |
| **AWS Secret Access Key** | Your IAM user's secret key (stored as Frappe Password field) |
| **Region** | Default AWS region (e.g., `ap-south-1`, `us-east-1`) |

### S3 File Storage

Navigate to the **S3 Storage** tab:

| Field | Description | Default |
|---|---|---|
| **Enable S3 File Storage** | Toggle S3 file storage on/off | Off |
| **S3 Bucket Name** | Target bucket for file uploads | *Required* |
| **S3 Bucket Region** | Override region for S3 (leave blank to use general region) | — |
| **S3 Endpoint URL** | For S3-compatible providers (Backblaze, MinIO, Wasabi) | — |
| **S3 Folder Prefix** | Key prefix for all uploads (defaults to site name) | Site name |
| **Instant Upload to S3** | Upload files immediately upon attachment (via background job) | Off |
| **Delete Local File After S3 Upload** | Remove local copy once S3 upload succeeds | On |
| **Delete S3 File on ERP Deletion** | Delete S3 object when File doc is trashed | On |
| **Batch Size** | Files per batch for scheduled uploads, migration, and cleanup | 50 |
| **Presigned URL Expiry** | URL validity in seconds (1–604800) | 900 (15 min) |

#### Exempt DocTypes

Add DocTypes to the **Exempt DocTypes** child table to prevent their file attachments from being uploaded to S3. Files attached to exempt DocTypes remain local.

### S3 Backups

Navigate to the **S3 Backups** tab:

| Field | Description | Default |
|---|---|---|
| **Enable S3 Backups** | Toggle backup functionality | Off |
| **Backup Frequency** | Daily / Weekly / Monthly / None | Daily |
| **Backup Files** | Include public and private file tarballs | On |
| **Backup Job Timeout** | Max job duration in seconds | 6000 (100 min) |
| **Backup Bucket Name** | Separate bucket for backups (leave blank to use main bucket) | — |
| **Backup Folder Path** | S3 key prefix for backup files | — |
| **Keep Last N Backups** | Count-based retention (0 = disabled) | 0 |
| **Delete Backups Older Than (days)** | Age-based retention (0 = disabled) | 0 |
| **Notify Email** | Email address for backup notifications | *Required* |
| **Notify on Success** | Send email even when backup succeeds | Off |

### SES Email

Navigate to the **SES Settings** tab:

| Field | Description | Default |
|---|---|---|
| **Source Email** | Verified SES sender email address | — |
| **Sender Name** | Display name shown in email headers | — |
| **Email Batch Size** | Number of emails per batch | 1 |

---

## Usage Guide

### File Storage Operations

#### Automatic Upload (Instant Mode)
When **Instant Upload to S3** is enabled:
1. Attach a file to any document
2. A background job immediately uploads it to S3
3. The `file_url` is rewritten to the S3 presigned URL API route
4. The File form auto-refreshes with a green **"Stored on S3"** indicator

#### Scheduled Upload (Hourly)
When instant upload is disabled, files are uploaded by the hourly scheduler job in batches.

#### Bulk Migration
To migrate all existing local files to S3:
1. Go to **AWS Settings**
2. Click **S3 Files → Migrate All Files to S3**
3. Confirm the dialog
4. Monitor progress via the real-time progress bar

#### Check S3 Status
Click **S3 Files → S3 Status** to see:
- Files on S3 vs. pending upload
- Storage sizes
- Migration progress percentage
- Recent error count

#### Per-File Actions
On any **File** document:
- **Upload to S3** — Queue a single file for upload (shown when file is local)
- **Delete Local File** — Remove the local copy after S3 upload (shown when file is on S3)

#### Local File Cleanup
Click **S3 Files → Clean Up Local Files** to bulk-delete local copies of all S3-uploaded files.

### Backup Operations

#### Take a Backup
1. Go to **AWS Settings**
2. Click **S3 Backups → Take Backup Now**
3. Watch the live status pipeline: **Queued → Generating → Uploading → Done**
4. View details in **S3 Backups → Backup Logs**

#### Upload Existing Local Backups
Click **S3 Backups → Upload Local Backups** to scan `{site}/private/backups/` and upload any local backups not yet on S3.

#### Download Backup from S3
1. Open an **S3 Backup Log** entry
2. Click the download button for any backup file (DB, config, files, private files)
3. A presigned URL is generated and the download starts automatically

#### Automatic Scheduling
Backups run automatically based on the configured frequency:
- **Daily** — Runs via `scheduler_events.daily`
- **Weekly** — Runs via `scheduler_events.weekly_long`
- **Monthly** — Runs via `scheduler_events.monthly_long`

### Email Operations

When AWS is enabled, the app automatically:
1. Replaces Frappe's default `frappe.email.queue.flush` with the SES-powered `flush_email_queue`
2. Processes the email queue in batches using SES v2 API
3. Logs every sent email in **AWS SES Logs** with message ID, recipients, and status

#### Batch Sending API
For sending custom emails in bulk:

```python
from aws_integration.utils.email import send_email_in_batches

data = {
    "key1": {
        "subject": "Welcome!",
        "content": "<h1>Hello</h1>",
        "recepients": ["user@example.com"],
        "cc_recepients": [],
        "bcc_recepients": [],
    }
}
send_email_in_batches(data)
```

---

## Architecture

```
aws_integration/
├── api/
│   └── s3.py                  # Whitelisted APIs (file serving, migration, status, cleanup)
├── aws_integration/
│   └── doctype/
│       ├── aws_settings/       # Central configuration DocType
│       ├── aws_ses_logs/       # SES email log DocType
│       ├── s3_backup_log/      # Backup tracking DocType
│       └── s3_exempt_doctype/  # Child table for exempt DocTypes
├── public/
│   └── js/
│       └── file.js            # File DocType UI enhancements (S3 indicator, buttons)
├── s3/
│   ├── client.py              # S3Client wrapper (upload, download, delete, presign)
│   ├── handlers.py            # Document event handlers (after_insert, on_trash)
│   ├── overrides.py           # File DocType class override (S3 URL validation bypass)
│   ├── scheduler.py           # Scheduled jobs (upload pending, bulk migrate, cleanup)
│   ├── backup.py              # Full backup lifecycle (generate, upload, rotate, notify)
│   └── setup.py               # Custom field creation on File DocType (after_migrate)
├── utils/
│   └── email.py               # SES email sending, queue flushing
└── hooks.py                   # Scheduler events, doc_events, overrides, after_migrate
```

### Key Design Decisions

- **Presigned URLs** — Files are never streamed through the Frappe server; presigned URLs redirect directly to S3
- **Row-level locking** — `SELECT ... FOR UPDATE` prevents race conditions between instant upload and scheduled upload workers
- **Commit-before-delete** — S3 metadata is committed to the database before local file deletion to prevent data loss
- **Path traversal protection** — All local file operations validate paths against expected base directories
- **Dedup compatibility** — Frappe's content-hash deduplication is fully supported; dedup-created File docs are detected and marked as S3-stored without re-uploading
- **Graceful degradation** — If S3 is disabled while files exist on S3, a warning is shown but the save is not blocked

---

## S3-Compatible Providers

This app works with any S3-compatible storage provider. Set the **S3 Endpoint URL** field:

| Provider | Endpoint URL Format |
|---|---|
| **AWS S3** | Leave blank (uses default) |
| **Backblaze B2** | `https://s3.{region}.backblazeb2.com` |
| **Wasabi** | `https://s3.{region}.wasabisys.com` |
| **MinIO** | `https://your-minio-server:9000` |
| **DigitalOcean Spaces** | `https://{region}.digitaloceanspaces.com` |

---

## API Reference

### File APIs (`aws_integration.api.s3`)

| Method | Description | Auth |
|---|---|---|
| `generate_file(key, file_name)` | Redirect to presigned S3 URL | Guest (with permission check) |
| `test_s3_connection()` | Test S3 bucket connectivity | System Manager |
| `migrate_files_to_s3()` | Start bulk file migration | System Manager |
| `get_s3_status()` | Get upload statistics | System Manager |
| `cleanup_local_s3_files()` | Delete local copies of S3 files | System Manager |
| `upload_single_file_to_s3(file_name)` | Queue a single file for upload | System Manager |
| `get_file_preview(file_name, file_url)` | Get presigned preview URL | Logged in |
| `delete_local_file(file_name)` | Delete local copy of an S3 file | System Manager |

### Backup APIs (`aws_integration.s3.backup`)

| Method | Description | Auth |
|---|---|---|
| `take_s3_backup()` | Queue a new site backup | System Manager |
| `get_backup_download_url(log_name, file_field)` | Get presigned download URL for backup file | System Manager |
| `cleanup_backup_local_files(log_name)` | Delete local backup files for a log | System Manager |
| `upload_local_backups()` | Upload existing local backups to S3 | System Manager |

### Custom Fields on File DocType

These fields are automatically created via `after_migrate`:

| Field | Type | Description |
|---|---|---|
| `s3_key` | Small Text | S3 object key (relative, without prefix) |
| `is_on_s3` | Check | Whether the file has been uploaded to S3 |
| `s3_uploaded_at` | Datetime | Timestamp of S3 upload |
| `local_deleted` | Check | Whether the local copy has been deleted |

---

## Troubleshooting

### Files not uploading to S3
1. Verify **Enable AWS** and **Enable S3 File Storage** are both checked
2. Check that the file's DocType is not in the **Exempt DocTypes** list
3. If using **Instant Upload**, ensure the Frappe worker queue is running (`bench start` or `supervisor`)
4. Check **Error Log** for entries containing "S3 Upload"

### "Bucket does not exist" error
- Verify the bucket name is correct (case-sensitive)
- Ensure the bucket exists in the specified region
- Check IAM permissions include `s3:HeadBucket`, `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`

### Presigned URLs expiring too quickly
- Increase the **Presigned URL Expiry** value in AWS Settings (max: 604800 seconds / 7 days)
- Note: IAM temporary credentials may impose their own shorter limits

### Backups failing
1. Check the **S3 Backup Log** for the error traceback
2. Ensure the backup bucket has write permissions
3. For large sites, increase the **Backup Job Timeout** value
4. Verify disk space for temporary backup file generation

### SES emails not sending
1. Verify the **Source Email** is a verified SES identity
2. Check if your SES account is still in sandbox mode (sandbox only allows verified recipients)
3. Review **AWS SES Logs** for sent status and **Error Log** for failures

---

## Contributing

This app uses `pre-commit` for code formatting and linting:

```bash
cd apps/aws_integration
pre-commit install
```

Pre-commit tools:
- **ruff** — Python linting and formatting
- **eslint** — JavaScript linting
- **prettier** — Code formatting
- **pyupgrade** — Python syntax modernization

---

## License

[Apache-2.0](license.txt)
