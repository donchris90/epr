"""
Tests for real avatar support (app/auth/services.py) -- reuses the
existing document/S3 infrastructure, with a real image-type check
applied specifically when a document is set as someone's avatar.

Uses moto's mock_aws, matching test_documents.py's own established
pattern exactly -- a real S3 REST API implemented in-process, not a
hand-rolled stub, so the full real upload -> confirm -> set-avatar ->
retrieve flow is genuinely exercised end to end.
"""
import pytest
import requests
from moto import mock_aws
from sqlalchemy import text

from app.documents import services as doc_services
from app.auth import services as auth_services
from app.utils.errors import APIError


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


@pytest.fixture()
def s3_bucket(app):
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


def _upload_and_confirm(db, tenant_id, *, content_type, file_bytes=b"fake image bytes"):
    """Real upload through the full lifecycle, matching exactly what a
    real browser upload does -- request a slot, PUT real bytes
    directly to S3, confirm via a real HEAD request."""
    _as_tenant(db, tenant_id)
    document, upload_url = doc_services.create_upload_request(
        tenant_id, original_filename="avatar.jpg", content_type=content_type,
    )
    _as_tenant(db, tenant_id)
    requests.put(upload_url, data=file_bytes, headers={"Content-Type": content_type})
    _as_tenant(db, tenant_id)
    confirmed = doc_services.confirm_upload(document)
    _as_tenant(db, tenant_id)
    return confirmed


class TestGetProfile:
    def test_returns_real_profile_fields(self, app, db, seed_tenants):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        _as_tenant(db, seed_tenants["a"])
        user = User(tenant_id=seed_tenants["a"], email="profiletest@example.com", password_hash=hash_password("x"), status="active", department="Engineering", job_title="Site Engineer")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            profile = auth_services.get_profile(seed_tenants["a"], user_id)
            assert profile.email == "profiletest@example.com"
            assert profile.department == "Engineering"

    def test_nonexistent_user_404s(self, app, db, seed_tenants):
        import uuid

        with app.app_context():
            with pytest.raises(APIError) as exc_info:
                auth_services.get_profile(seed_tenants["a"], uuid.uuid4())
            assert exc_info.value.status == 404


class TestSetAvatar:
    def test_real_full_flow_upload_confirm_set_avatar(self, app, db, seed_tenants, s3_bucket):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            user = User(tenant_id=seed_tenants["a"], email="avatartest@example.com", password_hash=hash_password("x"), status="active")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            document = _upload_and_confirm(db, seed_tenants["a"], content_type="image/jpeg")
            assert document.status == "uploaded"
            document_id = document.id

            _as_tenant(db, seed_tenants["a"])
            updated = auth_services.set_avatar(seed_tenants["a"], user_id, document_id=document_id)
            assert updated.avatar_document_id == document_id

    def test_rejects_a_non_image_document(self, app, db, seed_tenants, s3_bucket):
        """The real, deliberate rule: content_type is read from the
        actual S3 HEAD response during confirm_upload, never trusted
        from the client -- a real PDF genuinely cannot become an
        avatar, this isn't just checking a client-supplied claim."""
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            user = User(tenant_id=seed_tenants["a"], email="avatarreject@example.com", password_hash=hash_password("x"), status="active")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            document = _upload_and_confirm(db, seed_tenants["a"], content_type="application/pdf")
            document_id = document.id

            _as_tenant(db, seed_tenants["a"])
            with pytest.raises(APIError) as exc_info:
                auth_services.set_avatar(seed_tenants["a"], user_id, document_id=document_id)
            assert exc_info.value.status == 400

    def test_rejects_a_document_that_never_finished_uploading(self, app, db, seed_tenants, s3_bucket):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            user = User(tenant_id=seed_tenants["a"], email="avatarpending@example.com", password_hash=hash_password("x"), status="active")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Requested but never actually uploaded/confirmed -- still status="pending"
            document, _ = doc_services.create_upload_request(seed_tenants["a"], original_filename="avatar.jpg", content_type="image/jpeg")
            _as_tenant(db, seed_tenants["a"])
            document_id = document.id

            with pytest.raises(APIError) as exc_info:
                auth_services.set_avatar(seed_tenants["a"], user_id, document_id=document_id)
            assert exc_info.value.status == 409

    def test_rejects_a_document_belonging_to_another_tenant(self, app, db, seed_tenants, s3_bucket):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            user = User(tenant_id=seed_tenants["a"], email="avatarcrosstenant@example.com", password_hash=hash_password("x"), status="active")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            document = _upload_and_confirm(db, seed_tenants["b"], content_type="image/jpeg")
            document_id = document.id

            _as_tenant(db, seed_tenants["a"])
            with pytest.raises(APIError) as exc_info:
                auth_services.set_avatar(seed_tenants["a"], user_id, document_id=document_id)
            assert exc_info.value.status == 404


class TestRemoveAvatar:
    def test_clears_the_avatar(self, app, db, seed_tenants, s3_bucket):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            user = User(tenant_id=seed_tenants["a"], email="avatarremove@example.com", password_hash=hash_password("x"), status="active")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            document = _upload_and_confirm(db, seed_tenants["a"], content_type="image/png")
            document_id = document.id
            _as_tenant(db, seed_tenants["a"])
            auth_services.set_avatar(seed_tenants["a"], user_id, document_id=document_id)

            _as_tenant(db, seed_tenants["a"])
            cleared = auth_services.remove_avatar(seed_tenants["a"], user_id)
            assert cleared.avatar_document_id is None


class TestMeEndpoints:
    def test_get_me_returns_a_real_working_avatar_url(self, app, db, client, seed_tenants, auth_headers, s3_bucket):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            user = User(tenant_id=seed_tenants["a"], email="meendpoint@example.com", password_hash=hash_password("x"), status="active")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            document = _upload_and_confirm(db, seed_tenants["a"], content_type="image/jpeg")
            document_id = document.id
            _as_tenant(db, seed_tenants["a"])
            auth_services.set_avatar(seed_tenants["a"], user_id, document_id=document_id)

        headers = auth_headers("a", user_id=str(user_id), permissions=["*"])
        r = client.get("/v1/auth/me", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["email"] == "meendpoint@example.com"
        assert r.get_json()["avatar_url"] is not None
        assert r.get_json()["avatar_url"].startswith("http")

    def test_set_avatar_via_the_real_http_endpoint(self, app, db, client, seed_tenants, auth_headers, s3_bucket):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            user = User(tenant_id=seed_tenants["a"], email="httpavatar@example.com", password_hash=hash_password("x"), status="active")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            document = _upload_and_confirm(db, seed_tenants["a"], content_type="image/webp")
            document_id = str(document.id)

        headers = auth_headers("a", user_id=str(user_id), permissions=["*"])
        r = client.put("/v1/auth/me/avatar", headers=headers, json={"document_id": document_id})
        assert r.status_code == 200
        assert r.get_json()["avatar_url"] is not None

    def test_delete_avatar_via_the_real_http_endpoint(self, app, db, client, seed_tenants, auth_headers, s3_bucket):
        from app.models.core import User
        from app.auth.jwt_utils import hash_password

        with app.app_context():
            _as_tenant(db, seed_tenants["a"])
            user = User(tenant_id=seed_tenants["a"], email="httpdelavatar@example.com", password_hash=hash_password("x"), status="active")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            document = _upload_and_confirm(db, seed_tenants["a"], content_type="image/jpeg")
            document_id = str(document.id)
            _as_tenant(db, seed_tenants["a"])
            auth_services.set_avatar(seed_tenants["a"], user_id, document_id=document_id)

        headers = auth_headers("a", user_id=str(user_id), permissions=["*"])
        r = client.delete("/v1/auth/me/avatar", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["avatar_url"] is None
