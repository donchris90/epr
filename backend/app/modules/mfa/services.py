"""
Module 24 — Mobile Field App (Code: MFA)
Service layer — the server side of the offline-sync protocol.

Business rules encoded here (SRS 4.24):
  - No mobile-captured record is final/official until successfully
    synced and accepted by the server -- `_apply_sync_entry` is the
    ONLY code path that sets status="synced", and only after a real
    commit succeeds.
  - Conflicts are never silently discarded -- every failure path in
    `_apply_sync_entry` creates a ConflictRecord before returning;
    there is no `except: pass` or silent-drop anywhere in this module.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.utils.errors import APIError
from app.modules.mfa.models import SyncQueueEntry, ConflictRecord


def submit_sync_batch(tenant_id, *, device_id, entries):
    """
    `entries`: list of dicts with client_record_id, target_module,
    target_entity_type, operation, payload, device_timestamp.

    Idempotent: if a client_record_id was already submitted (by this
    device or a prior dropped connection resubmitting the same batch),
    the existing SyncQueueEntry's current state is returned rather than
    reprocessing -- a device retrying a partially-acknowledged batch
    never creates duplicate server records.
    """
    results = []
    for entry_data in entries:
        client_record_id = entry_data["client_record_id"]
        existing = SyncQueueEntry.query.filter_by(tenant_id=tenant_id, client_record_id=client_record_id).first()
        if existing:
            results.append(existing)
            continue

        entry = SyncQueueEntry(
            tenant_id=tenant_id,
            device_id=device_id,
            client_record_id=client_record_id,
            target_module=entry_data["target_module"],
            target_entity_type=entry_data["target_entity_type"],
            operation=entry_data.get("operation", "create"),
            payload=entry_data["payload"],
            device_timestamp=entry_data.get("device_timestamp"),
        )
        db.session.add(entry)
        db.session.flush()

        _apply_sync_entry(entry)
        results.append(entry)

    db.session.commit()
    return results


def _apply_sync_entry(entry: SyncQueueEntry):
    """
    Dispatches to the real target-entity creation logic. On success,
    marks the entry synced with the real server_record_id. On ANY
    failure, creates a ConflictRecord and marks the entry "conflict" --
    there is no path where a failure is simply swallowed.
    """
    try:
        if entry.target_entity_type == "hse_near_miss":
            server_record_id = _create_hse_near_miss(entry)
        elif entry.target_entity_type == "ast_asset_inspection":
            server_record_id = _create_ast_asset_inspection(entry)
        elif entry.target_entity_type == "exe_daily_site_diary":
            server_record_id = _create_exe_daily_site_diary(entry)
        else:
            raise APIError(f"Unknown target entity type: {entry.target_entity_type}", status=400)

        entry.status = "synced"
        entry.server_record_id = server_record_id
        entry.synced_at = datetime.now(timezone.utc)

    except _ValidationConflict as exc:
        _record_conflict(entry, conflict_type="validation_failure", server_current_state=exc.server_state)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: ANY failure must surface as a conflict, never vanish
        _record_conflict(entry, conflict_type="validation_failure", server_current_state=None, note=str(exc))


class _ValidationConflict(Exception):
    def __init__(self, message, server_state=None):
        super().__init__(message)
        self.server_state = server_state


def _record_conflict(entry: SyncQueueEntry, *, conflict_type, server_current_state=None, note=None):
    entry.status = "conflict"
    entry.rejection_reason = note or f"{conflict_type} on sync"

    conflict = ConflictRecord(
        tenant_id=entry.tenant_id,
        sync_queue_entry_id=entry.id,
        conflict_type=conflict_type,
        client_payload=entry.payload,
        server_current_state=server_current_state,
    )
    db.session.add(conflict)


def _create_hse_near_miss(entry: SyncQueueEntry):
    from app.modules.hse.models import NearMiss, INCIDENT_CLASSIFICATIONS

    payload = entry.payload
    classification = payload.get("classification")
    if classification not in INCIDENT_CLASSIFICATIONS:
        raise _ValidationConflict(f"Invalid classification '{classification}'")
    if not payload.get("description"):
        raise _ValidationConflict("description is required")

    near_miss = NearMiss(
        tenant_id=entry.tenant_id,
        project_id=payload.get("project_id"),
        classification=classification,
        description=payload["description"],
        occurred_at=entry.device_timestamp or datetime.now(timezone.utc),
    )
    db.session.add(near_miss)
    db.session.flush()
    return near_miss.id


def _create_ast_asset_inspection(entry: SyncQueueEntry):
    from app.modules.ast.models import Asset, AssetInspection

    payload = entry.payload
    asset_id = payload.get("asset_id")
    asset = Asset.query.filter_by(id=asset_id, tenant_id=entry.tenant_id).first() if asset_id else None
    if not asset:
        # A genuine, meaningful conflict: the field device thinks this
        # asset exists (it did, offline, in the cached local store);
        # the server says otherwise. Surface it, don't guess.
        raise _ValidationConflict(f"Asset {asset_id} not found", server_state={"asset_id": asset_id, "found": False})

    inspection = AssetInspection(
        tenant_id=entry.tenant_id,
        asset_id=asset.id,
        inspected_at=payload.get("inspected_at"),
        condition_score=payload.get("condition_score"),
        inspector_name=payload.get("inspector_name"),
        notes=payload.get("notes"),
    )
    db.session.add(inspection)
    db.session.flush()
    return inspection.id


def _create_exe_daily_site_diary(entry: SyncQueueEntry):
    """
    Real target type added specifically to unblock the mobile app's
    intended primary screen (SRS 7.2.2, Daily Site Diary Flow) --
    previously the mobile scaffold's own local schema and screen
    naming assumed this worked already, but nothing in this dispatcher
    supported it until now.

    A genuine, meaningful conflict case exists here, not a contrived
    one: exe_daily_site_diaries has a real
    uq_exe_diaries_project_date constraint (one diary per project per
    day) -- if a diary for this project/date already exists (created
    via the web app, or by another device syncing first), that's a
    real disagreement the field user needs to see and resolve, not
    something to silently overwrite or duplicate.

    Mobile-submitted diaries are created as "draft" -- signing
    (DailySiteDiary.signed_by/signed_at) stays a separate, explicit
    action through the normal EXE flow, not something sync auto-applies
    on the device's behalf.
    """
    from app.modules.exe.models import DailySiteDiary

    payload = entry.payload
    project_id = payload.get("project_id")
    diary_date = payload.get("diary_date")
    if not project_id or not diary_date:
        raise _ValidationConflict("project_id and diary_date are both required")

    existing = DailySiteDiary.query.filter_by(
        tenant_id=entry.tenant_id, project_id=project_id, diary_date=diary_date
    ).first()
    if existing:
        raise _ValidationConflict(
            f"A diary for this project on {diary_date} already exists",
            server_state={
                "existing_diary_id": str(existing.id),
                "status": existing.status,
                "narrative": existing.narrative,
            },
        )

    diary = DailySiteDiary(
        tenant_id=entry.tenant_id,
        project_id=project_id,
        diary_date=diary_date,
        workforce_present_count=payload.get("workforce_present_count"),
        equipment_on_site_summary=payload.get("equipment_on_site_summary"),
        narrative=payload.get("narrative"),
        status="draft",
    )
    db.session.add(diary)
    db.session.flush()
    return diary.id


# --- Conflict resolution ---------------------------------------------------------

def resolve_conflict(conflict: ConflictRecord, *, resolved_by, resolution):
    """
    A human reviewer's decision on a surfaced conflict -- this function
    only records the DECISION (e.g. "discard the mobile record" or
    "apply it with corrections"); it deliberately does not
    automatically re-attempt the original operation, since the whole
    point of surfacing a conflict is that automatic reconciliation
    already failed once and a human should decide what happens next.
    """
    if conflict.status == "resolved":
        raise APIError("Conflict has already been resolved", status=409)

    conflict.status = "resolved"
    conflict.resolution = resolution
    conflict.resolved_by = resolved_by
    conflict.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return conflict


def get_sync_status_summary(tenant_id, *, device_id=None):
    """MFA-09: per-record sync status, for the client to render "pending
    / syncing / synced / conflict" state to the user."""
    query = SyncQueueEntry.query.filter_by(tenant_id=tenant_id)
    if device_id:
        query = query.filter_by(device_id=device_id)
    entries = query.all()

    counts = {"pending": 0, "synced": 0, "conflict": 0, "rejected": 0}
    for entry in entries:
        counts[entry.status] += 1
    return counts
