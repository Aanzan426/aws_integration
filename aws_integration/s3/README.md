# S3 File Storage Integration

Offload Frappe/ERPNext file attachments to Amazon S3, reducing local disk usage while keeping seamless file access via presigned URLs.

## Features

- **Automatic S3 Upload** - Hourly scheduler uploads local files to S3 in configurable batches
- **Instant Upload** - Optional immediate upload on file attachment (via background job)
- **Presigned URL Access** - Files served through time-limited S3 presigned URLs (default: 15 min)
- **Folder Mirroring** - S3 keys mirror Frappe's folder structure (`Home/` prefix stripped)
- **DocType Exemption** - Exclude specific DocTypes from S3 upload (e.g., Item, Product)
- **Configurable Deletion** - Control whether deleting a file from ERP also deletes it from S3
- **Bulk Migration** - One-click migration of all existing local files to S3
- **Permission-Gated** - Private files require authentication and document-level permissions
- **Multipart Upload** - Files larger than 5 MB use S3 multipart upload

## Setup

### 1. Enable S3 in AWS Settings

Navigate to **AWS Settings** and:

1. Check **Enable AWS** and provide your AWS credentials (Access Key, Secret Key, Region)
2. Check **Enable S3 File Storage**
3. Go to the **S3 Storage** tab and fill in:
   - **S3 Bucket Name** (required)
   - **S3 Bucket Region** (optional, falls back to general region)
   - **S3 Folder Prefix** (optional, defaults to site name)
4. Click **S3 > Test S3 Connection** to verify

### 2. Configure Upload Behavior

In the **Upload Settings** section:

| Setting | Default | Description |
|---------|---------|-------------|
| Instant Upload to S3 | Off | Upload immediately when file is attached |
| Delete Local File After S3 Upload | On | Remove local copy after confirmed upload |
| Delete S3 File on ERP Deletion | On | Delete S3 object when File is trashed |
| Upload Batch Size | 50 | Files processed per hourly scheduler run |
| Presigned URL Expiry | 900s | How long generated URLs remain valid |

### 3. Exempt DocTypes (Optional)

In the **Exempt DocTypes** section, add any DocTypes whose attachments should remain local (e.g., Item, Product).

### 4. Run Migration

```bash
bench --site <site> migrate
bench build --app aws_integration
bench --site <site> clear-cache
```

The `migrate` command creates custom fields (`s3_key`, `is_on_s3`, `s3_uploaded_at`) on the File DocType.

### 5. Migrate Existing Files

Click **S3 > Migrate All Files to S3** in AWS Settings to upload all existing local files. This runs as a background job with progress updates.

## How It Works

### File Upload

Files are uploaded to S3 via two mechanisms:

1. **Instant** (if enabled): `File.after_insert` enqueues a background job on the `short` queue
2. **Scheduled**: Hourly scheduler processes remaining local files in batches

After upload, the File document's `file_url` is rewritten to:
```
/api/method/aws_integration.api.s3.generate_file?key={s3_key}&file_name={display_name}
```

### File Access

When a browser requests the file URL:
1. The `generate_file` API looks up the File document by `s3_key`
2. For private files, it checks permissions on the attached document
3. Generates a presigned S3 URL (default: 15 min expiry)
4. Returns an HTTP 302 redirect to the presigned URL
5. Browser loads the file directly from S3

### S3 Key Structure

```
{prefix}/{private|public}/{folder}/{hash}_{filename}
```

Examples:
```
unity/public/Baby Walnut Wakad-2026-2027/ZHUENX2M_photo.jpg
unity/private/Attachments/A3BKX9QP_salary_slip.pdf
unity/public/X7KMRT4P_logo.png
```

## File Structure

```
aws_integration/
  s3/
    client.py         # S3Client - boto3 wrapper
    scheduler.py      # Hourly upload + bulk migration
    handlers.py       # after_insert + on_trash hooks
    setup.py          # after_migrate: custom fields on File
  api/
    s3.py             # generate_file, test_s3_connection, migrate_files_to_s3, get_file_preview
  public/js/
    file.js           # File form: "View on S3" button + S3 indicator
```

## API Reference

| Endpoint | Auth | Description |
|----------|------|-------------|
| `aws_integration.api.s3.generate_file` | Guest (permission-checked) | Presigned URL redirect for file access |
| `aws_integration.api.s3.get_file_preview` | Logged in | Returns presigned URL + metadata |
| `aws_integration.api.s3.test_s3_connection` | System Manager | Test S3 bucket connectivity |
| `aws_integration.api.s3.migrate_files_to_s3` | System Manager | Enqueue bulk migration job |

---

# S3 Backups

Automated site backups (database, site config, public/private files) uploaded directly to S3 with scheduling, progress tracking, email notifications, and retention-based rotation.

## Features

- **On-Demand Backup** — "Take Backup Now" button in AWS Settings
- **Scheduled Backups** — Daily, Weekly, or Monthly via Frappe scheduler
- **Realtime Progress** — Progress bar in AWS Settings (generating → uploading → success/failed)
- **Backup Log** — `S3 Backup Log` DocType tracks every run with status, S3 keys, file sizes, and errors
- **Retention Policies** — Keep last N backups and/or delete backups older than N days from S3
- **Email Notifications** — Configurable email alerts on success and/or failure
- **Local Cleanup** — Local backup files are deleted after successful S3 upload
- **Auto Log Clearing** — Old log records purged after 90 days via Frappe's Log Settings

## Setup

### 1. Enable S3 Backups

In **AWS Settings**, ensure AWS and S3 are enabled, then:

1. Check **Enable S3 Backups**
2. Go to the **S3 Backups** tab

### 2. Configure Backup Settings

#### Backup Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Backup Frequency | Daily | `Daily`, `Weekly`, `Monthly`, or `None` (manual only) |
| Backup Files | On | Include public and private file tarballs in backup |

#### Backup Storage

| Setting | Default | Description |
|---------|---------|-------------|
| Backup Bucket Name | *(main bucket)* | Separate bucket for backups. Leave blank to use the main S3 bucket |
| Backup Folder Path | *(site name)* | S3 key prefix for backup files |

#### Retention

| Setting | Default | Description |
|---------|---------|-------------|
| Keep Last N Backups | 0 (disabled) | Keep only the N most recent successful backups on S3, delete older ones |
| Delete Backups Older Than (days) | 0 (disabled) | Delete backups older than N days from S3 |

Either or both retention policies can be active. Set to `0` to disable. Retention runs after every successful backup.

#### Notifications

| Setting | Default | Description |
|---------|---------|-------------|
| Notify Email | *(required)* | Email address to receive backup notifications |
| Send Email for Successful Backup | Off | Send notification even on success (failures always notify) |

### 3. Run Migration

```bash
bench --site <site> migrate
bench --site <site> clear-cache
```

This creates the `S3 Backup Log` DocType table.

## How It Works

### Backup Flow

1. **Trigger** — User clicks "Take Backup Now" or scheduler fires
2. **Queue** — A `S3 Backup Log` entry is created with status `Queued`, background job is enqueued on the `long` queue
3. **Generate** — Frappe's `new_backup()` creates the database dump (`.sql.gz`), site config (`.json`), and optionally file archives (`.tar`)
4. **Upload** — Each file is uploaded to S3 at `{folder}/{timestamp}-{site}-{type}.{ext}`
5. **Record** — Log entry is updated with S3 keys, file sizes, and status `Success`
6. **Cleanup** — Local backup files are deleted, `local_cleaned` is set
7. **Rotate** — Old backups are deleted from S3 based on retention settings
8. **Notify** — Email notification is sent if configured

### Retry Behavior

If the backup or upload fails, the job retries up to 2 times automatically. After exhausting retries, the log is marked `Failed` with the traceback, and a failure notification is sent.

### Retention / Rotation

Runs after every successful backup. Two independent policies:

- **Count-based**: Queries all `Success` logs ordered by creation, deletes everything beyond position N
- **Age-based**: Queries `Success` logs where `completed_at` is older than the cutoff date

For each old log, all S3 objects (db, config, files, private files) are deleted via `delete_objects`, then the log record is removed. The current backup is always excluded from rotation.

### Scheduler Events

| Event | Function | Fires |
|-------|----------|-------|
| `daily` | `take_backups_daily` | Every day |
| `weekly_long` | `take_backups_weekly` | Every week |
| `monthly_long` | `take_backups_monthly` | Every month |

Each checks `enable_s3_backups` and `s3_backup_frequency` before proceeding.

## S3 Backup Log

One record per backup run. Read-only from the UI (Administrator can delete).

| Field | Type | Description |
|-------|------|-------------|
| Status | Select | `Queued` → `In Progress` → `Success` / `Failed` |
| Started At | Datetime | When the background job started |
| Completed At | Datetime | When the job finished (success or failure) |
| Database File | Data | S3 key of the `.sql.gz` file |
| Site Config File | Data | S3 key of the `.json` file |
| Files Archive | Data | S3 key of the public files `.tar` |
| Private Files Archive | Data | S3 key of the private files `.tar` |
| Database Size | Int | Size in bytes |
| Files Size | Int | Combined public + private archive size in bytes |
| Total Size | Int | Total bytes uploaded |
| S3 Bucket | Data | Bucket used for this backup |
| S3 Folder | Data | Folder prefix used |
| Local Files Cleaned | Check | Whether local files were deleted after upload |
| Error | Long Text | Traceback on failure |

Naming: `BKUP-00001`, `BKUP-00002`, ...

Status colors: Queued=Blue, In Progress=Yellow, Success=Green, Failed=Red

## File Structure

```
aws_integration/
  s3/
    backup.py          # Backup logic: take_s3_backup, _run_backup, rotation, scheduler
    ...
  aws_integration/
    doctype/
      s3_backup_log/
        s3_backup_log.json   # DocType definition
        s3_backup_log.py     # Controller with clear_old_logs
```

## API Reference

| Endpoint | Auth | Description |
|----------|------|-------------|
| `aws_integration.s3.backup.take_s3_backup` | System Manager | Queue a backup job, returns `{log_name}` |

## Permissions

- **S3 Backup Log**: Administrator has read + delete. No other role has access.
- **take_s3_backup API**: Restricted to System Manager via `frappe.only_for`
- Scheduler uses an internal `_enqueue_backup()` that bypasses the role guard

## Requirements

- `boto3` (already included in app dependencies)
- AWS IAM credentials with S3 permissions: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:HeadBucket`, `s3:HeadObject`
- S3 bucket with **no public access** (all access via presigned URLs)
