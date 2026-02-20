import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
    """Create custom fields on File DocType for S3 integration."""
    custom_fields = {
        "File": [
            {
                "fieldname": "s3_info_section",
                "fieldtype": "Section Break",
                "label": "S3 Info",
                "insert_after": "preview",
                "collapsible": 1,
            },
            {
                "fieldname": "s3_key",
                "fieldtype": "Small Text",
                "label": "S3 Key",
                "insert_after": "s3_info_section",
                "read_only": 1,
                "no_copy": 1,
            },
            {
                "fieldname": "is_on_s3",
                "fieldtype": "Check",
                "label": "Uploaded to S3",
                "insert_after": "s3_key",
                "read_only": 1,
                "default": "0",
                "no_copy": 1,
            },
            {
                "fieldname": "s3_uploaded_at",
                "fieldtype": "Datetime",
                "label": "S3 Upload Date",
                "insert_after": "is_on_s3",
                "read_only": 1,
                "no_copy": 1,
            },
        ]
    }
    create_custom_fields(custom_fields, update=True)
