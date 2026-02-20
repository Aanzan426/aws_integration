from frappe.core.doctype.file.file import File


S3_API_PREFIX = "/api/method/aws_integration.api.s3.generate_file"


class S3File(File):
    """Override File DocType to handle S3-stored files.

    Frappe's dedup logic copies file_url from an existing File doc onto the
    new one when content_hash matches. When that file_url is our S3 API route,
    Frappe's validation methods reject it because it's not a local disk path.

    This override skips disk-based validation for S3 API URLs.
    """

    def exists_on_disk(self):
        if self.is_on_s3 and self.s3_key:
            return True
        if self.file_url and self.file_url.startswith(S3_API_PREFIX):
            return True
        return super().exists_on_disk()

    def validate_file_path(self):
        if self.file_url and self.file_url.startswith(S3_API_PREFIX):
            return
        super().validate_file_path()

    def validate_file_url(self):
        if self.file_url and self.file_url.startswith(S3_API_PREFIX):
            return
        super().validate_file_url()

    def validate_file_on_disk(self):
        if self.file_url and self.file_url.startswith(S3_API_PREFIX):
            return
        super().validate_file_on_disk()
