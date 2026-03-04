# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main branch | Yes |

## Reporting a Security Issue

If you discover a security issue in this project, please report it responsibly by emailing **badal@unityedu.ai** with the subject line **"AWS Integration Security Report"**.

Please include:

- A description of the issue
- Steps to reproduce
- The potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and work with you to understand and address the issue before any public disclosure.

**Please do not open a public GitHub issue for security-related reports.**

## Scope

This policy covers the `aws_integration` Frappe app, including:

- S3 file upload and access control
- Presigned URL generation
- S3 backup operations
- SES email integration
- Permission checks on private files

## Best Practices for Deployers

- Use IAM credentials with the **minimum required permissions** (least privilege)
- Never commit AWS credentials to version control
- Set a short **presigned URL expiry** (default: 15 minutes)
- Enable **Delete S3 File on ERP Deletion** to avoid orphaned S3 objects
- Keep your Frappe and AWS Integration app up to date
