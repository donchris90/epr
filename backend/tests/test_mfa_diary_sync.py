"""
Tests for MFA's exe_daily_site_diary sync dispatch target
(app/modules/mfa/services.py:_create_exe_daily_site_diary).

Added specifically to unblock the mobile app's intended primary
screen (SRS 7.2.2, Daily Site Diary Flow) -- the mobile scaffold's own
local schema and screen naming assumed this worked already, but
nothing in the sync dispatcher supported it until this pass. Follows
the exact established pattern of hse_near_miss/ast_asset_inspection.
"""
import uuid

from sqlalchemy import text


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


class TestDailySiteDiarySyncDispatch:
    def test_creates_a_real_diary_from_a_synced_entry(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["mfa:write"])
        project_id = str(uuid.uuid4())

        r = client.post("/v1/mfa/sync-batch", headers=headers, json={
            "device_id": "test-device-001",
            "entries": [{
                "client_record_id": str(uuid.uuid4()),
                "target_module": "EXE",
                "target_entity_type": "exe_daily_site_diary",
                "operation": "create",
                "payload": {
                    "project_id": project_id, "diary_date": "2026-08-16",
                    "workforce_present_count": 24, "narrative": "Foundation pour completed.",
                },
            }],
        })
        assert r.status_code == 201
        entry = r.get_json()["data"][0]
        assert entry["status"] == "synced"
        assert entry["server_record_id"] is not None

        _as_tenant(db, seed_tenants["a"])
        from app.modules.exe.models import DailySiteDiary
        diary = DailySiteDiary.query.filter_by(tenant_id=seed_tenants["a"], project_id=project_id).first()
        assert diary is not None
        assert diary.status == "draft"
        assert diary.workforce_present_count == 24
        assert diary.narrative == "Foundation pour completed."

    def test_duplicate_project_and_date_becomes_a_real_conflict_not_a_duplicate(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["mfa:write", "mfa:read"])
        project_id = str(uuid.uuid4())

        def submit(narrative):
            return client.post("/v1/mfa/sync-batch", headers=headers, json={
                "device_id": "test-device",
                "entries": [{
                    "client_record_id": str(uuid.uuid4()),
                    "target_module": "EXE", "target_entity_type": "exe_daily_site_diary", "operation": "create",
                    "payload": {"project_id": project_id, "diary_date": "2026-08-16", "narrative": narrative},
                }],
            })

        r1 = submit("First diary")
        assert r1.get_json()["data"][0]["status"] == "synced"

        r2 = submit("A conflicting second diary for the same day")
        entry2 = r2.get_json()["data"][0]
        assert entry2["status"] == "conflict"

        _as_tenant(db, seed_tenants["a"])
        from app.modules.exe.models import DailySiteDiary
        diaries = DailySiteDiary.query.filter_by(tenant_id=seed_tenants["a"], project_id=project_id).all()
        assert len(diaries) == 1  # the conflicting one was never created

        r3 = client.get("/v1/mfa/conflicts", headers=headers)
        conflicts = r3.get_json()["data"]
        assert len(conflicts) == 1
        assert conflicts[0]["server_current_state"]["narrative"] == "First diary"

    def test_resubmitting_the_same_client_record_id_is_idempotent(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["mfa:write"])
        project_id = str(uuid.uuid4())
        client_record_id = str(uuid.uuid4())

        payload = {
            "device_id": "test-device",
            "entries": [{
                "client_record_id": client_record_id,
                "target_module": "EXE", "target_entity_type": "exe_daily_site_diary", "operation": "create",
                "payload": {"project_id": project_id, "diary_date": "2026-08-16", "narrative": "Diary"},
            }],
        }

        r1 = client.post("/v1/mfa/sync-batch", headers=headers, json=payload)
        r2 = client.post("/v1/mfa/sync-batch", headers=headers, json=payload)  # simulates a dropped-connection retry

        assert r1.get_json()["data"][0]["id"] == r2.get_json()["data"][0]["id"]

        _as_tenant(db, seed_tenants["a"])
        from app.modules.exe.models import DailySiteDiary
        diaries = DailySiteDiary.query.filter_by(tenant_id=seed_tenants["a"], project_id=project_id).all()
        assert len(diaries) == 1  # no duplicate from the retry

    def test_missing_required_fields_becomes_a_conflict_not_a_crash(self, app, db, client, seed_tenants, auth_headers):
        headers = auth_headers("a", permissions=["mfa:write"])

        r = client.post("/v1/mfa/sync-batch", headers=headers, json={
            "device_id": "test-device",
            "entries": [{
                "client_record_id": str(uuid.uuid4()),
                "target_module": "EXE", "target_entity_type": "exe_daily_site_diary", "operation": "create",
                "payload": {"narrative": "No project_id or diary_date"},
            }],
        })
        assert r.status_code == 201  # the batch endpoint itself succeeds
        assert r.get_json()["data"][0]["status"] == "conflict"  # but this entry didn't apply cleanly
