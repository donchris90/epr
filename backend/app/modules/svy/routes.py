"""
Module 15 — Survey & Engineering (Code: SVY)
SRS Section 4.15 — Flask Blueprint. Base path: /v1/svy
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.svy import services
from app.modules.svy.models import (
    SurveyControlPoint,
    GPSCoordinate,
    DesignSurface,
    CrossSection,
    EarthworksVolumeCalculation,
    RoadAlignment,
    AsBuiltRecord,
)
from app.modules.svy.schemas import (
    SurveyControlPointSchema,
    GPSCoordinateInputSchema,
    GPSCoordinateSchema,
    LevelReadingInputSchema,
    LevelReadingSchema,
    DesignSurfaceInputSchema,
    DesignSurfaceSchema,
    CrossSectionInputSchema,
    CrossSectionSchema,
    EarthworksVolumeInputSchema,
    EarthworksVolumeSchema,
    RoadAlignmentInputSchema,
    RoadAlignmentSchema,
    AsBuiltRecordInputSchema,
    AsBuiltRecordUpdateSchema,
    AsBuiltRecordSchema,
)

bp = Blueprint("svy", __name__, url_prefix="/v1/svy")

control_point_schema = SurveyControlPointSchema()
gps_schema = GPSCoordinateSchema()
level_schema = LevelReadingSchema()
surface_schema = DesignSurfaceSchema()
cross_section_schema = CrossSectionSchema()
volume_schema = EarthworksVolumeSchema()
alignment_schema = RoadAlignmentSchema()
as_built_schema = AsBuiltRecordSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_surface_or_404(surface_id) -> DesignSurface:
    s = DesignSurface.query.filter_by(id=surface_id, tenant_id=g.tenant_id).first()
    if not s:
        raise APIError("Design surface not found", status=404)
    return s


def _get_volume_calc_or_404(calc_id) -> EarthworksVolumeCalculation:
    c = EarthworksVolumeCalculation.query.filter_by(id=calc_id, tenant_id=g.tenant_id).first()
    if not c:
        raise APIError("Earthworks volume calculation not found", status=404)
    return c


def _get_as_built_or_404(record_id) -> AsBuiltRecord:
    r = AsBuiltRecord.query.filter_by(id=record_id, tenant_id=g.tenant_id).first()
    if not r:
        raise APIError("As-built record not found", status=404)
    return r


@bp.get("/health")
def health():
    return jsonify({"module": "svy", "name": "Survey & Engineering", "status": "ok"})


# --- Control points (SVY-01) -----------------------------------------------------

@bp.post("/control-points")
@require_permission("svy:write")
def create_control_point():
    data = _load(control_point_schema)
    point = SurveyControlPoint(tenant_id=g.tenant_id, **data)
    db.session.add(point)
    db.session.commit()
    return jsonify(control_point_schema.dump(point)), 201


@bp.get("/control-points")
@require_permission("svy:read")
def list_control_points():
    points = SurveyControlPoint.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(control_point_schema.dump(points, many=True)))


# --- GPS coordinates (SVY-02, SVY-09) --------------------------------------------

@bp.post("/gps-coordinates")
@require_permission("svy:write")
def create_gps_coordinate():
    data = _load(GPSCoordinateInputSchema())
    coord = GPSCoordinate(tenant_id=g.tenant_id, **data)
    db.session.add(coord)
    db.session.commit()
    return jsonify(gps_schema.dump(coord)), 201


# --- Level readings (SVY-03) ------------------------------------------------------

@bp.post("/level-readings")
@require_permission("svy:write")
def create_level_reading():
    data = _load(LevelReadingInputSchema())
    reading = services.record_level_reading(g.tenant_id, **data)
    return jsonify(level_schema.dump(reading)), 201


@bp.get("/level-readings/out-of-tolerance")
@require_permission("svy:read")
def list_out_of_tolerance_readings():
    from app.modules.svy.models import LevelReading

    project_id = request.args.get("project_id")
    query = LevelReading.query.filter_by(tenant_id=g.tenant_id, is_out_of_tolerance=True)
    if project_id:
        query = query.filter_by(project_id=project_id)
    readings = query.all()
    return jsonify(envelope(level_schema.dump(readings, many=True)))


# --- Design surfaces (SVY-08) -----------------------------------------------------

@bp.post("/design-surfaces")
@require_permission("svy:write")
def create_design_surface():
    data = _load(DesignSurfaceInputSchema())
    surface = DesignSurface(tenant_id=g.tenant_id, **data)
    db.session.add(surface)
    db.session.commit()
    return jsonify(surface_schema.dump(surface)), 201


@bp.post("/design-surfaces/<uuid:surface_id>/approve")
@require_permission("svy:approve")
def approve_design_surface(surface_id):
    surface = _get_surface_or_404(surface_id)
    surface = services.approve_design_surface(surface, approved_by=g.user_id)
    return jsonify(surface_schema.dump(surface))


# --- Cross sections (SVY-04) -------------------------------------------------------

@bp.post("/cross-sections")
@require_permission("svy:write")
def create_cross_section():
    data = _load(CrossSectionInputSchema())
    section = CrossSection(tenant_id=g.tenant_id, **data)
    db.session.add(section)
    db.session.commit()
    return jsonify(cross_section_schema.dump(section)), 201


# --- Earthworks volumes (SVY-05, business rule) ------------------------------------

@bp.post("/earthworks-volumes")
@require_permission("svy:write")
def create_earthworks_volume():
    data = _load(EarthworksVolumeInputSchema())
    calc = services.calculate_earthworks_volume(g.tenant_id, calculated_by=g.user_id, **data)
    return jsonify(volume_schema.dump(calc)), 201


@bp.post("/earthworks-volumes/<uuid:calc_id>/submit-for-billing")
@require_permission("svy:approve")
def submit_for_billing(calc_id):
    calc = _get_volume_calc_or_404(calc_id)
    calc = services.submit_for_billing(calc)
    return jsonify(volume_schema.dump(calc))


# --- Road alignments (SVY-06) --------------------------------------------------------

@bp.post("/road-alignments")
@require_permission("svy:write")
def create_road_alignment():
    data = _load(RoadAlignmentInputSchema())
    alignment = RoadAlignment(tenant_id=g.tenant_id, **data)
    db.session.add(alignment)
    db.session.commit()
    return jsonify(alignment_schema.dump(alignment)), 201


# --- As-built records (SVY-07, business rule) -----------------------------------------

@bp.post("/as-built-records")
@require_permission("svy:write")
def create_as_built_record():
    data = _load(AsBuiltRecordInputSchema())
    record = AsBuiltRecord(tenant_id=g.tenant_id, **data)
    db.session.add(record)
    db.session.commit()
    return jsonify(as_built_schema.dump(record)), 201


@bp.put("/as-built-records/<uuid:record_id>")
@require_permission("svy:write")
def update_as_built_record(record_id):
    record = _get_as_built_or_404(record_id)
    data = _load(AsBuiltRecordUpdateSchema())
    record = services.update_as_built_record(record, **data)
    return jsonify(as_built_schema.dump(record))


@bp.post("/as-built-records/<uuid:record_id>/lock")
@require_permission("svy:approve")
def lock_as_built_record(record_id):
    record = _get_as_built_or_404(record_id)
    record = services.lock_as_built_record(record)
    return jsonify(as_built_schema.dump(record))
