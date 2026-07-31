"""
Module 6 — Project Execution (Code: EXE)
SRS Section 4.6 — Flask Blueprint. Base path: /v1/exe
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.exe import services
from app.modules.exe.models import (
    DailySiteDiary,
    SiteMedia,
    WeatherRecord,
    ProgressEntry,
    WorkCompletedRecord,
    SiteIssue,
    VisitorLog,
    EquipmentUsageRecord,
    LaborUsageRecord,
    ConcretePourRecord,
    InspectionLog,
)
from app.modules.exe.schemas import (
    DailySiteDiarySchema,
    UpdateDiarySchema,
    DiaryAmendmentSchema,
    SiteMediaSchema,
    WeatherRecordSchema,
    ProgressEntrySchema,
    WorkCompletedRecordSchema,
    SiteIssueSchema,
    VisitorLogSchema,
    EquipmentUsageRecordSchema,
    LaborUsageRecordSchema,
    ConcretePourRecordSchema,
    InspectionLogSchema,
)

bp = Blueprint("exe", __name__, url_prefix="/v1/exe")

diary_schema = DailySiteDiarySchema()
amendment_schema = DiaryAmendmentSchema()
media_schema = SiteMediaSchema()
weather_schema = WeatherRecordSchema()
progress_schema = ProgressEntrySchema()
work_completed_schema = WorkCompletedRecordSchema()
issue_schema = SiteIssueSchema()
visitor_schema = VisitorLogSchema()
equipment_usage_schema = EquipmentUsageRecordSchema()
labor_usage_schema = LaborUsageRecordSchema()
pour_schema = ConcretePourRecordSchema()
inspection_schema = InspectionLogSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_diary_or_404(diary_id) -> DailySiteDiary:
    diary = DailySiteDiary.query.filter_by(id=diary_id, tenant_id=g.tenant_id).first()
    if not diary:
        raise APIError("Diary not found", status=404)
    return diary


@bp.get("/health")
def health():
    return jsonify({"module": "exe", "name": "Project Execution", "status": "ok"})


# --- Daily Site Diary (EXE-01, EXE-12, business rule) -----------------------

@bp.post("/diaries")
@require_permission("exe:write")
def create_diary():
    data = _load(diary_schema)
    diary = DailySiteDiary(tenant_id=g.tenant_id, **data)
    db.session.add(diary)
    db.session.commit()
    return jsonify(diary_schema.dump(diary)), 201


@bp.get("/diaries")
@require_permission("exe:read")
def list_diaries():
    query = DailySiteDiary.query.filter_by(tenant_id=g.tenant_id)
    project_id = request.args.get("project_id")
    if project_id:
        query = query.filter_by(project_id=project_id)
    diaries = query.order_by(DailySiteDiary.diary_date.desc()).all()
    return jsonify(envelope(diary_schema.dump(diaries, many=True)))


@bp.get("/diaries/<uuid:diary_id>")
@require_permission("exe:read")
def get_diary(diary_id):
    return jsonify(diary_schema.dump(_get_diary_or_404(diary_id)))


@bp.put("/diaries/<uuid:diary_id>")
@require_permission("exe:write")
def update_diary(diary_id):
    diary = _get_diary_or_404(diary_id)
    data = _load(UpdateDiarySchema())
    diary = services.update_diary(diary, **data)
    return jsonify(diary_schema.dump(diary))


@bp.post("/diaries/<uuid:diary_id>/sign")
@require_permission("exe:sign")
def sign_diary(diary_id):
    diary = _get_diary_or_404(diary_id)
    diary = services.sign_diary(diary, signed_by=g.user_id)
    return jsonify(diary_schema.dump(diary))


@bp.post("/diaries/<uuid:diary_id>/countersign")
@require_permission("exe:sign")
def countersign_diary(diary_id):
    diary = _get_diary_or_404(diary_id)
    diary = services.countersign_diary(diary, countersigned_by=g.user_id)
    return jsonify(diary_schema.dump(diary))


@bp.post("/diaries/<uuid:diary_id>/amendments")
@require_permission("exe:write")
def add_amendment(diary_id):
    diary = _get_diary_or_404(diary_id)
    data = _load(amendment_schema)
    amendment = services.amend_diary(diary, description=data["description"], amended_by=g.user_id)
    return jsonify(amendment_schema.dump(amendment)), 201


@bp.get("/diaries/<uuid:diary_id>/amendments")
@require_permission("exe:read")
def list_amendments(diary_id):
    _get_diary_or_404(diary_id)
    from app.modules.exe.models import DiaryAmendment

    amendments = (
        DiaryAmendment.query.filter_by(diary_id=diary_id, tenant_id=g.tenant_id)
        .order_by(DiaryAmendment.created_at.asc())
        .all()
    )
    return jsonify(envelope(amendment_schema.dump(amendments, many=True)))


# --- Media (EXE-03) -----------------------------------------------------------

@bp.post("/site-media")
@require_permission("exe:write")
def add_site_media():
    data = _load(media_schema)
    media = SiteMedia(tenant_id=g.tenant_id, **data)
    db.session.add(media)
    db.session.commit()
    return jsonify(media_schema.dump(media)), 201


# --- Weather (EXE-04) ----------------------------------------------------------

@bp.post("/diaries/<uuid:diary_id>/weather")
@require_permission("exe:write")
def add_weather_record(diary_id):
    diary = _get_diary_or_404(diary_id)
    data = _load(weather_schema)
    record = WeatherRecord(tenant_id=g.tenant_id, diary_id=diary.id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(weather_schema.dump(record)), 201


@bp.get("/diaries/<uuid:diary_id>/weather")
@require_permission("exe:read")
def list_weather_records(diary_id):
    _get_diary_or_404(diary_id)
    records = WeatherRecord.query.filter_by(diary_id=diary_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(weather_schema.dump(records, many=True)))


# --- Progress (EXE-05) ---------------------------------------------------------

@bp.post("/progress-entries")
@require_permission("exe:write")
def add_progress_entry():
    data = _load(progress_schema)
    entry = ProgressEntry(tenant_id=g.tenant_id, **data)
    db.session.add(entry)
    db.session.commit()
    return jsonify(progress_schema.dump(entry)), 201


@bp.get("/progress-entries")
@require_permission("exe:read")
def list_progress_entries():
    activity_id = request.args.get("activity_id")
    query = ProgressEntry.query.filter_by(tenant_id=g.tenant_id)
    if activity_id:
        query = query.filter_by(activity_id=activity_id)
    entries = query.order_by(ProgressEntry.recorded_at.desc()).all()
    return jsonify(envelope(progress_schema.dump(entries, many=True)))


# --- Work completed (EXE-06, business rule) ------------------------------------

@bp.post("/work-completed")
@require_permission("exe:write")
def add_work_completed():
    data = _load(work_completed_schema)
    record = services.record_work_completed(g.tenant_id, **data)
    body = work_completed_schema.dump(record)
    response = {**body}
    if record.exceeds_contracted_quantity:
        response["warning"] = "Cumulative completed quantity exceeds the contracted BOQ quantity."
    return jsonify(response), 201


# --- Site issues (EXE-07) -------------------------------------------------------

@bp.post("/site-issues")
@require_permission("exe:write")
def create_site_issue():
    data = _load(issue_schema)
    issue = SiteIssue(tenant_id=g.tenant_id, **data)
    db.session.add(issue)
    db.session.commit()
    return jsonify(issue_schema.dump(issue)), 201


@bp.get("/site-issues")
@require_permission("exe:read")
def list_site_issues():
    query = SiteIssue.query.filter_by(tenant_id=g.tenant_id)
    project_id = request.args.get("project_id")
    status = request.args.get("status")
    if project_id:
        query = query.filter_by(project_id=project_id)
    if status:
        query = query.filter_by(status=status)
    issues = query.all()
    return jsonify(envelope(issue_schema.dump(issues, many=True)))


@bp.post("/site-issues/escalate-overdue")
@require_permission("exe:write")
def escalate_overdue_issues():
    escalated = services.escalate_overdue_issues(g.tenant_id)
    return jsonify(envelope(issue_schema.dump(escalated, many=True)))


# --- Visitor log (EXE-08) -------------------------------------------------------

@bp.post("/visitor-logs")
@require_permission("exe:write")
def add_visitor_log():
    data = _load(visitor_schema)
    log = VisitorLog(tenant_id=g.tenant_id, **data)
    db.session.add(log)
    db.session.commit()
    return jsonify(visitor_schema.dump(log)), 201


# --- Equipment & labor usage (EXE-09) -------------------------------------------

@bp.post("/diaries/<uuid:diary_id>/equipment-usage")
@require_permission("exe:write")
def add_equipment_usage(diary_id):
    diary = _get_diary_or_404(diary_id)
    data = _load(equipment_usage_schema)
    record = EquipmentUsageRecord(tenant_id=g.tenant_id, diary_id=diary.id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(equipment_usage_schema.dump(record)), 201


@bp.get("/diaries/<uuid:diary_id>/equipment-usage")
@require_permission("exe:read")
def list_equipment_usage(diary_id):
    _get_diary_or_404(diary_id)
    records = EquipmentUsageRecord.query.filter_by(diary_id=diary_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(equipment_usage_schema.dump(records, many=True)))


@bp.post("/diaries/<uuid:diary_id>/labor-usage")
@require_permission("exe:write")
def add_labor_usage(diary_id):
    diary = _get_diary_or_404(diary_id)
    data = _load(labor_usage_schema)
    record = LaborUsageRecord(tenant_id=g.tenant_id, diary_id=diary.id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(labor_usage_schema.dump(record)), 201


@bp.get("/diaries/<uuid:diary_id>/labor-usage")
@require_permission("exe:read")
def list_labor_usage(diary_id):
    _get_diary_or_404(diary_id)
    records = LaborUsageRecord.query.filter_by(diary_id=diary_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(labor_usage_schema.dump(records, many=True)))


# --- Concrete pour records (EXE-10) ---------------------------------------------

@bp.post("/concrete-pours")
@require_permission("exe:write")
def add_concrete_pour():
    data = _load(pour_schema)
    record = ConcretePourRecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(pour_schema.dump(record)), 201


# --- Inspection logs (EXE-11) ----------------------------------------------------

@bp.post("/inspection-logs")
@require_permission("exe:write")
def add_inspection_log():
    data = _load(inspection_schema)
    log = InspectionLog(tenant_id=g.tenant_id, **data)
    db.session.add(log)
    db.session.commit()
    return jsonify(inspection_schema.dump(log)), 201


@bp.get("/inspection-logs")
@require_permission("exe:read")
def list_inspection_logs():
    outcome = request.args.get("outcome")
    query = InspectionLog.query.filter_by(tenant_id=g.tenant_id)
    if outcome:
        query = query.filter_by(outcome=outcome)
    logs = query.all()
    return jsonify(envelope(inspection_schema.dump(logs, many=True)))
