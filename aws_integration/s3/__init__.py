from urllib.parse import urlencode

S3_API_PREFIX = "/api/method/aws_integration.api.s3.generate_file"


def get_s3_file_url(s3_key, file_name):
    """Build the S3 API file URL from an S3 key and display file name."""
    return f"{S3_API_PREFIX}?{urlencode({'key': s3_key, 'file_name': file_name})}"
