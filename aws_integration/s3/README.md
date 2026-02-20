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

## Requirements

- `boto3` (already included in app dependencies)
- AWS IAM credentials with S3 permissions: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:HeadBucket`, `s3:HeadObject`
- S3 bucket with **no public access** (all access via presigned URLs)
