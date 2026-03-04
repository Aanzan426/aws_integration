<div align="center">

# AWS Integration for Frappe

Offload file attachments to Amazon S3, automate site backups, and send emails via Amazon SES — all from your Frappe/ERPNext instance.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Frappe](https://img.shields.io/badge/Frappe-v15-blue.svg)](https://frappeframework.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org)

</div>

---

## Overview

**AWS Integration** is a Frappe app that connects your Frappe/ERPNext site to Amazon Web Services. It provides three core modules:

| Module | What it does |
|--------|-------------|
| **S3 File Storage** | Upload file attachments to S3, serve them via presigned URLs, and reclaim local disk space |
| **S3 Backups** | Schedule automated site backups to S3 with retention policies and email notifications |
| **SES Email** | Route outgoing emails through Amazon SES |

## Features

### S3 File Storage

- **Automatic upload** — Hourly scheduler uploads local files to S3 in configurable batches
- **Instant upload** — Optional immediate upload on file attachment (background job)
- **Presigned URL access** — Files served through time-limited S3 presigned URLs (configurable expiry)
- **Local file preservation** — `file_url` stays as the local path until the local copy is deleted, so files are served from disk when available
- **Folder mirroring** — S3 keys mirror Frappe's folder structure
- **DocType exemption** — Exclude specific DocTypes from S3 upload
- **Bulk migration** — One-click migration of all existing local files to S3 with parallel batch processing
- **Local cleanup** — Delete local copies of files already on S3 with tracking
- **Content-hash dedup** — Identical files reuse existing S3 objects instead of re-uploading
- **Orphan adoption** — Find files on disk with no File document, create records, and upload to S3
- **Concurrency safety** — Row-level locks prevent duplicate uploads across workers
- **Crash safety** — S3 metadata committed before local file deletion
- **Permission-gated** — Private files require authentication and document-level permissions
- **Multipart upload** — Files larger than 5 MB use S3 multipart upload
- **S3-compatible providers** — Works with Backblaze B2, Wasabi, MinIO, and any S3-compatible storage

### S3 Backups

- **Scheduled backups** — Daily, weekly, or monthly via Frappe scheduler
- **On-demand backups** — "Take Backup Now" button in AWS Settings
- **Complete backups** — Database dump, site config, public and private file archives
- **Retention policies** — Keep last N backups and/or delete backups older than N days
- **Realtime progress** — Status pipeline UI (Queued → Generating → Uploading → Done)
- **Email notifications** — Configurable alerts on success and/or failure
- **Auto-retry** — Failed backups retry up to 2 times automatically
- **Presigned downloads** — Download backup files directly from S3 via the backup log

### SES Email

- Amazon SES email sending integration
- Email queue flushing with rate limiting
- SES send logs

## Requirements

- **Frappe** v15+
- **Python** 3.10+
- **boto3** (installed automatically)
- AWS IAM credentials with appropriate permissions:
  - S3: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:HeadBucket`, `s3:HeadObject`
  - SES: `ses:SendEmail` (if using SES module)

## Installation

```bash
bench get-app https://github.com/UnityAppSuite/aws_integration.git --branch main
bench --site your-site.localhost install-app aws_integration
bench --site your-site.localhost migrate
bench build --app aws_integration
bench --site your-site.localhost clear-cache
```

## Quick Start

### 1. Configure AWS Credentials

Navigate to **AWS Settings** in your Frappe site:

1. Check **Enable AWS**
2. Enter your **AWS Access Key ID** and **Secret Access Key**
3. Set your **AWS Region**

### 2. Enable S3 File Storage

In the **S3 Storage** tab:

1. Check **Enable S3 File Storage**
2. Enter your **S3 Bucket Name**
3. Click **S3 Files > Test S3 Connection** to verify

### 3. Configure Upload Behavior

| Setting | Default | Description |
|---------|---------|-------------|
| Instant Upload to S3 | Off | Upload immediately when a file is attached |
| Delete Local File After S3 Upload | On | Remove local copy after confirmed upload |
| Delete S3 File on ERP Deletion | On | Delete S3 object when File doc is trashed |
| Batch Size | 50 | Files processed per scheduler run |
| Presigned URL Expiry | 900s | How long generated URLs remain valid |

### 4. (Optional) Enable S3 Backups

In the **S3 Backups** tab:

1. Check **Enable S3 Backups**
2. Set your preferred **Backup Frequency** (Daily / Weekly / Monthly)
3. Configure retention policies as needed
4. Enter a **Notify Email** for backup notifications

## Architecture

```
User uploads file
       │
       ▼
  ┌─────────┐     after_insert hook      ┌──────────────┐
  │  Frappe  │ ──────────────────────────▶│ Background   │
  │  (local) │                            │ Job (short)  │
  └─────────┘                             └──────┬───────┘
       │                                         │
       │  file_url stays local                   │ boto3 upload
       │  until local deleted                    ▼
       │                                  ┌──────────────┐
       │                                  │  Amazon S3   │
       │                                  └──────┬───────┘
       │                                         │
       ▼                                         │
  ┌─────────┐     presigned URL redirect         │
  │ Browser │ ◀──────────────────────────────────┘
  └─────────┘
```

## Documentation

- **[S3 File Storage & Backups](aws_integration/s3/README.md)** — Detailed setup, configuration, and architecture reference

## Project Structure

```
aws_integration/
├── api/
│   └── s3.py                  # Whitelisted APIs (file serving, migration, status)
├── aws_integration/
│   └── doctype/
│       ├── aws_settings/      # Main configuration DocType
│       ├── aws_ses_logs/      # SES email send logs
│       ├── s3_backup_log/     # Backup run history
│       └── s3_exempt_doctype/ # Child table for exempt DocTypes
├── s3/
│   ├── __init__.py            # S3_API_PREFIX, get_s3_file_url helper
│   ├── client.py              # S3Client — boto3 wrapper
│   ├── handlers.py            # File upload/delete hooks, dedup detection
│   ├── scheduler.py           # Hourly upload, bulk migration, cleanup, orphan adoption
│   ├── overrides.py           # S3File — File DocType override
│   ├── backup.py              # S3 backup logic, retention, scheduling
│   └── setup.py               # Custom fields on File DocType
├── utils/
│   └── email.py               # SES email integration
├── public/js/
│   └── file.js                # File form: S3 indicator, upload/delete buttons
└── hooks.py                   # Frappe hooks configuration
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up a development environment
- Code style and linting
- Submitting pull requests
- Reporting issues

## Security

If you discover a security vulnerability, please report it responsibly. See [SECURITY.md](SECURITY.md) for details.

## License

This project is licensed under the [Apache License 2.0](license.txt).

## Maintainers

Built and maintained by [@badal8381](https://github.com/badal8381) at [Hybrowlabs Technologies](https://hybrowlabs.com).
