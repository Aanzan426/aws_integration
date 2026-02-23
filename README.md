### AWS Integration

AWS Integration for Frappe/ERPNext — S3 file storage, S3 backups, and SES email.

### Features

**S3 File Storage**
- Automatic upload of file attachments to Amazon S3 (instant or scheduled)
- Presigned URL file access with permission checks
- Folder-mirrored S3 key structure
- DocType exemption (exclude specific DocTypes from upload)
- Bulk migration of existing files
- Local file cleanup with tracking (`local_deleted` field)
- Per-file "Delete Local File" button (when on S3 and local copy exists)
- Confirmation dialogs on all destructive actions
- S3-compatible provider support (Backblaze B2, Wasabi, MinIO)

**S3 Backups**
- On-demand and scheduled (Daily/Weekly/Monthly) site backups to S3
- Database dump, site config, and file archives
- Realtime progress tracking with status pipeline UI
- Retention policies (count-based and age-based)
- Email notifications on success/failure
- Local backup cleanup after upload with per-log "Delete Local Files" button
- S3 objects auto-deleted when backup log is trashed
- Configurable job timeout for large sites
- Confirmation dialogs on all destructive actions
- Presigned download URLs for backup files

**SES Email**
- Amazon SES email sending integration

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app aws_integration
```

After installation:

```bash
bench --site <site> migrate
bench build --app aws_integration
bench --site <site> clear-cache
```

### Documentation

- [S3 File Storage & Backups](aws_integration/s3/README.md) — Setup, configuration, and architecture
- [PRD](PRD_S3_File_Storage.md) — Full product requirements document

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/aws_integration
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

apache-2.0
