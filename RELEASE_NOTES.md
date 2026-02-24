# Release Notes

## v1.0.0 — AWS Integration for Frappe

**Release Date:** February 24, 2026

This is the first stable release of **AWS Integration**, a comprehensive Frappe app that brings Amazon S3 file storage, S3-based site backups, and SES email sending to your Frappe/ERPNext instance.

---

### 🚀 Highlights

- **Unified AWS Settings** — A single DocType to configure S3 storage, S3 backups, and SES email with a clean tabbed interface
- **Zero-downtime migration** — Migrate existing files and backups to S3 without any downtime; files remain accessible throughout
- **S3-compatible providers** — Not locked into AWS; works with Backblaze B2, Wasabi, MinIO, DigitalOcean Spaces, and any S3-compatible service

---

### ✨ New Features

#### S3 File Storage
- **Instant & scheduled uploads** — Choose between immediate background upload on file attachment or hourly batch processing
- **Presigned URL serving** — Files are served via time-limited presigned URLs with Frappe's native permission model enforced for private files
- **Bulk migration** — One-click "Migrate All Files to S3" with real-time progress bar showing upload count and failures
- **S3 status dashboard** — View files on S3, pending uploads, exempt files, storage sizes, migration progress, and recent errors at a glance
- **DocType exemptions** — Configure a list of DocTypes whose attachments should remain local (e.g., Print Formats, temporary files)
- **Per-file actions** — "Upload to S3" button on local files; "Delete Local File" button on S3-uploaded files (with confirmation dialog)
- **Local file cleanup** — Bulk clean up local copies of S3 uploaded files to free disk space, with path traversal protection
- **Dedup compatibility** — Frappe's content-hash deduplication works seamlessly; duplicated File docs are automatically marked as S3-stored
- **File DocType override** — Custom `S3File` class bypasses Frappe's disk-based validation for S3 API URLs
- **Custom fields on File** — `s3_key`, `is_on_s3`, `s3_uploaded_at`, `local_deleted` fields created automatically via `after_migrate`
- **Collision-safe naming** — Content-hash prefix added to S3 keys when different files with the same name exist
- **Multipart upload** — Files >5 MB use S3 multipart upload for reliability
- **S3-compatible endpoint** — Custom endpoint URL support for non-AWS providers

#### S3 Site Backups
- **On-demand backups** — "Take Backup Now" button with live status pipeline (Queued → Generating → Uploading → Done)
- **Scheduled backups** — Automatic Daily, Weekly, or Monthly backups via Frappe scheduler events
- **Full site backup** — Database dump, site config, public files archive, and private files archive
- **Separate backup bucket** — Optionally store backups in a different bucket from file storage
- **Backup log tracking** — `S3 Backup Log` DocType tracks every backup with status, timestamps, file sizes, S3 keys, and error details
- **Retention management** — Auto-delete old backups by count ("keep last N") and/or by age ("delete older than N days")
- **Upload local backups** — Scan the local backup directory and upload previously generated backups to S3
- **Presigned download URLs** — Download any backup file (DB, config, files, private) from S3 via time-limited URLs
- **Email notifications** — Configure notifications for backup success and/or failure
- **Auto-retry** — Failed backups retry up to 2 times before final failure
- **Local cleanup** — Automatic or manual deletion of local backup files after successful upload
- **Configurable timeout** — Adjustable background job timeout for large sites (default: 6000 seconds / 100 minutes)

#### SES Email
- **SES v2 API integration** — Send transactional emails via Amazon SES with HTML and plain text support
- **Email queue override** — Automatically replaces Frappe's default email queue flusher when AWS is enabled
- **Batch email sending** — Configurable batch size with built-in rate limiting
- **SES logging** — All sent emails tracked in `AWS SES Logs` with message ID, recipients (To/CC/BCC), subject, and status
- **Automatic handler toggle** — Enabling/disabling AWS toggles the `Scheduled Job Type` for email queue flushing

---

### 🏗️ Architecture & Security

- **Row-level database locking** — `SELECT ... FOR UPDATE` prevents race conditions between instant and scheduled upload workers
- **Commit-before-delete pattern** — S3 metadata is committed to the database before local file deletion, preventing data loss on commit failure
- **Path traversal protection** — All local file operations validate resolved paths against expected base directories
- **Permission enforcement** — Private file access requires authentication and document-level read permission
- **Graceful disable warning** — Disabling S3 when files exist on S3 shows a warning with file count (does not block save)
- **Safe backup paths** — Backup file operations validate paths are within the site's backup directory

---

### 📋 Configuration Reference

#### AWS Settings Tabs

| Tab | Key Settings |
|---|---|
| **General** | Enable AWS, Access Key ID, Secret Key, Region |
| **SES Settings** | Source Email, Sender Name, Email Batch Size |
| **S3 Storage** | Enable S3, Bucket, Region, Endpoint URL, Upload Settings, Exempt DocTypes |
| **S3 Backups** | Enable Backups, Frequency, Backup Bucket, Retention, Notifications, Timeout |

---

### 📦 Dependencies

- **Frappe** `>=15.0.0, <16.0.0`
- **boto3** (AWS SDK for Python)

---

### 🔄 Upgrade Notes

This is the initial release. For fresh installations:

1. Install the app: `bench get-app <repo-url> --branch develop`
2. Install on site: `bench --site <site> install-app aws_integration`
3. Run migration: `bench --site <site> migrate` (creates custom fields on File DocType)
4. Build assets: `bench build --app aws_integration`
5. Clear cache: `bench --site <site> clear-cache`
6. Configure at `/app/aws-settings`

---

### 🐛 Known Limitations

- **No streaming** — Large file downloads redirect to S3 presigned URLs rather than streaming through Frappe
- **Single region** — All S3 operations use the configured region; cross-region replication is not managed by the app
- **SES sandbox** — New AWS accounts are in SES sandbox mode and can only send to verified email addresses

---

### 👥 Contributors

- Hybrowlabs Technologies

---

### 📄 License

Apache-2.0
