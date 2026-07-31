"""
Uploads a local backup dump (produced by backup.sh) to the dedicated
backup bucket, then verifies it landed with a real HEAD request --
the same "never trust that a write succeeded just because the call
didn't raise" discipline used for document uploads
(app/documents/services.py:confirm_upload).

Usage:
    python scripts/upload_backup_to_s3.py path/to/siteforge-TIMESTAMP.dump

Reads the same S3_ENDPOINT_URL / S3_ACCESS_KEY / S3_SECRET_KEY /
S3_BACKUP_BUCKET config as the rest of the app (app/config.py), via
the same get_s3_client() used for document storage -- one S3 client
construction path for the whole codebase, not two.
"""
import os
import sys

from botocore.exceptions import ClientError

from app import create_app
from app.extensions import get_s3_client


def upload(dump_path: str) -> str:
    if not os.path.isfile(dump_path):
        raise FileNotFoundError(dump_path)

    app = create_app()
    with app.app_context():
        s3 = get_s3_client()
        bucket = app.config["S3_BACKUP_BUCKET"]
        key = f"postgres/{os.path.basename(dump_path)}"

        s3.upload_file(dump_path, bucket, key)

        # Verify for real, not just "upload_file() didn't raise" --
        # confirm the object actually exists at the expected size.
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            raise RuntimeError(f"Upload appeared to succeed but HEAD check failed: {exc}") from exc

        local_size = os.path.getsize(dump_path)
        remote_size = head["ContentLength"]
        if remote_size != local_size:
            raise RuntimeError(
                f"Uploaded object size mismatch: local {local_size} bytes, remote {remote_size} bytes"
            )

        return f"s3://{bucket}/{key}"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/upload_backup_to_s3.py path/to/dump", file=sys.stderr)
        sys.exit(1)

    location = upload(sys.argv[1])
    print(f"Verified in S3: {location}")
