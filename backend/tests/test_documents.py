"""
Tests for app/documents/ -- the real S3-backed upload/confirm/download
lifecycle.

Uses moto's mock_aws, which intercepts boto3 at the HTTP layer (it
implements the actual S3 REST API in-process), not a hand-rolled stub
of app/documents/services.py's functions -- so these tests exercise
the real presigned-URL generation, the real HEAD-based confirmation
check, and the real GET/DELETE calls, the same code paths that ran
against a live moto server process during manual verification of this
module (see README's "Production readiness" notes for that session).

Tenant-context discipline: outside a real HTTP request, nothing
re-applies `SET LOCAL app.tenant_id` automatically (the middleware's
after_begin listener only fires within a request context -- see
app/middleware/tenant_context.py). Every services.* call below that
commits internally is followed IMMEDIATELY by a fresh _as_tenant()
call before the returned object's attributes are touched at all --
Flask-SQLAlchemy's default expire_on_commit=True means even a plain
attribute read after a commit triggers an implicit re-SELECT, and that
SELECT is just as subject to FORCE ROW LEVEL SECURITY as any other
query.
"""
import pytest
import requests
from moto import mock_aws
from sqlalchemy import text

from app.documents import services
from app.utils.errors import APIError


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


@pytest.fixture()
def s3_bucket(app):
    """
    moto's mock_aws() intercepts requests to AWS's own endpoint
    pattern, not to an arbitrary custom `endpoint_url` -- production
    and local dev deliberately set S3_ENDPOINT_URL (to point at a real
    S3-compatible server, e.g. MinIO), but that same override would
    make boto3 try to talk to a real, non-existent server during tests
    instead of moto's in-process mock. Clearing it here just for the
    duration of the test is what lets moto actually intercept the
    calls; get_s3_client() still runs its normal code path either way.
    """
    with mock_aws():
        import boto3

        with app.app_context():
            original_endpoint = app.config["S3_ENDPOINT_URL"]
            app.config["S3_ENDPOINT_URL"] = None

            bucket = app.config["S3_BUCKET"]
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket=bucket)
            import app.extensions as extensions

            extensions._s3_client = None
            yield bucket
            extensions._s3_client = None

            app.config["S3_ENDPOINT_URL"] = original_endpoint


class TestUploadConfirmDownloadLifecycle:
    def test_full_lifecycle_with_a_real_upload(self, app, db, seed_tenants, s3_bucket):
        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            document, upload_url = services.create_upload_request(
                seed_tenants["a"],
                original_filename="license.pdf",
                content_type="application/pdf",
                doc_type="trade_license",
            )
            _as_tenant(db, seed_tenants["a"])
            assert document.status == "pending"
            assert upload_url.startswith("http")

            file_bytes = b"a real trade license document, for real this time"
            put_response = requests.put(upload_url, data=file_bytes, headers={"Content-Type": "application/pdf"})
            assert put_response.status_code == 200

            _as_tenant(db, seed_tenants["a"])
            confirmed = services.confirm_upload(document)
            _as_tenant(db, seed_tenants["a"])
            assert confirmed.status == "uploaded"
            assert confirmed.size_bytes == len(file_bytes)

            download_url = services.get_download_url(confirmed)
            downloaded = requests.get(download_url)
            assert downloaded.status_code == 200
            assert downloaded.content == file_bytes

    def test_confirming_an_upload_that_never_happened_fails(self, app, db, seed_tenants, s3_bucket):
        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            document, _ = services.create_upload_request(
                seed_tenants["a"], original_filename="never-uploaded.pdf", content_type="application/pdf"
            )
            _as_tenant(db, seed_tenants["a"])
            with pytest.raises(APIError):
                services.confirm_upload(document)
            _as_tenant(db, seed_tenants["a"])
            assert document.status == "failed"

    def test_cannot_confirm_the_same_document_twice(self, app, db, seed_tenants, s3_bucket):
        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            document, upload_url = services.create_upload_request(
                seed_tenants["a"], original_filename="file.pdf", content_type="application/pdf"
            )
            requests.put(upload_url, data=b"content")

            _as_tenant(db, seed_tenants["a"])
            services.confirm_upload(document)

            _as_tenant(db, seed_tenants["a"])
            with pytest.raises(APIError):
                services.confirm_upload(document)

    def test_cannot_download_a_document_that_was_never_uploaded(self, app, db, seed_tenants, s3_bucket):
        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            document, _ = services.create_upload_request(
                seed_tenants["a"], original_filename="pending.pdf", content_type="application/pdf"
            )
            _as_tenant(db, seed_tenants["a"])
            with pytest.raises(APIError):
                services.get_download_url(document)

    def test_delete_removes_both_the_s3_object_and_the_row(self, app, db, seed_tenants, s3_bucket):
        import boto3
        from botocore.exceptions import ClientError

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            document, upload_url = services.create_upload_request(
                seed_tenants["a"], original_filename="to-delete.pdf", content_type="application/pdf"
            )
            requests.put(upload_url, data=b"content")

            _as_tenant(db, seed_tenants["a"])
            services.confirm_upload(document)
            _as_tenant(db, seed_tenants["a"])
            file_key = document.file_key
            document_id = document.id

            _as_tenant(db, seed_tenants["a"])
            services.delete_document(document)

            s3 = boto3.client("s3", region_name="us-east-1")
            with pytest.raises(ClientError):
                s3.head_object(Bucket=s3_bucket, Key=file_key)

            _as_tenant(db, seed_tenants["a"])
            from app.models.core import Document

            assert Document.query.filter_by(id=document_id).first() is None


class TestDocumentTenantIsolation:
    """The documents table's RLS policy is exactly the same mechanism
    proven in test_tenant_isolation.py for every other module -- this
    class exists because document storage is cross-cutting
    infrastructure rather than one of the 25 numbered modules, so it
    doesn't live in that file, but the guarantee matters exactly as
    much here as anywhere else in the platform."""

    def test_cannot_view_other_tenants_document(self, client, db, app, seed_tenants, auth_headers, s3_bucket):
        with app.app_context():
            _as_tenant(db, seed_tenants["b"])
            document, _ = services.create_upload_request(
                seed_tenants["b"], original_filename="tenant-b-file.pdf", content_type="application/pdf"
            )
            _as_tenant(db, seed_tenants["b"])
            doc_id = document.id

        r = client.get(f"/v1/documents/{doc_id}", headers=auth_headers("a"))
        assert r.status_code == 404

    def test_cannot_confirm_other_tenants_document(self, client, db, app, seed_tenants, auth_headers, s3_bucket):
        with app.app_context():
            _as_tenant(db, seed_tenants["b"])
            document, upload_url = services.create_upload_request(
                seed_tenants["b"], original_filename="tenant-b-file.pdf", content_type="application/pdf"
            )
            requests.put(upload_url, data=b"content")
            _as_tenant(db, seed_tenants["b"])
            doc_id = document.id

        r = client.post(f"/v1/documents/{doc_id}/confirm", headers=auth_headers("a"))
        assert r.status_code == 404

        with app.app_context():
            _as_tenant(db, seed_tenants["b"])
            from app.models.core import Document

            untouched = Document.query.filter_by(id=doc_id).first()
            assert untouched.status == "pending"

    def test_document_list_excludes_other_tenant(self, client, db, app, seed_tenants, auth_headers, s3_bucket):
        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            services.create_upload_request(seed_tenants["a"], original_filename="a-file.pdf", content_type="application/pdf")

            _as_tenant(db, seed_tenants["b"])
            services.create_upload_request(seed_tenants["b"], original_filename="b-file.pdf", content_type="application/pdf")

        r = client.get("/v1/documents", headers=auth_headers("a"))
        filenames = [d["original_filename"] for d in r.get_json()["data"]]
        assert "a-file.pdf" in filenames
        assert "b-file.pdf" not in filenames
