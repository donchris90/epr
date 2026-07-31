"""
Module 15 — Survey & Engineering (Code: SVY)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.svy.models import GPS_PURPOSES, CALCULATION_METHODS


class SurveyControlPointSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(required=True)
    point_name = fields.Str(required=True)
    coordinate_system = fields.Str(allow_none=True)
    datum = fields.Str(allow_none=True)
    northing = fields.Decimal(allow_none=True, as_string=True)
    easting = fields.Decimal(allow_none=True, as_string=True)
    benchmark_elevation = fields.Decimal(allow_none=True, as_string=True)
    established_at = fields.Date(allow_none=True)
    established_by = fields.Str(allow_none=True)


class GPSCoordinateInputSchema(Schema):
    project_id = fields.UUID(required=True)
    control_point_id = fields.UUID(allow_none=True)
    photo_document_id = fields.UUID(allow_none=True)
    latitude = fields.Decimal(required=True, as_string=True)
    longitude = fields.Decimal(required=True, as_string=True)
    elevation = fields.Decimal(allow_none=True, as_string=True)
    purpose = fields.Str(load_default="setting_out", validate=validate.OneOf(GPS_PURPOSES))
    captured_at = fields.DateTime(allow_none=True)


class GPSCoordinateSchema(Schema):
    id = fields.UUID(dump_only=True)
    latitude = fields.Decimal(dump_only=True, as_string=True)
    longitude = fields.Decimal(dump_only=True, as_string=True)
    purpose = fields.Str(dump_only=True)


class LevelReadingInputSchema(Schema):
    project_id = fields.UUID(required=True)
    control_point_id = fields.UUID(allow_none=True)
    location_description = fields.Str(allow_none=True)
    design_level = fields.Decimal(required=True, as_string=True)
    measured_level = fields.Decimal(required=True, as_string=True)
    tolerance = fields.Decimal(load_default="0", as_string=True)
    measured_at = fields.DateTime(allow_none=True)
    measured_by = fields.Str(allow_none=True)


class LevelReadingSchema(Schema):
    id = fields.UUID(dump_only=True)
    design_level = fields.Decimal(dump_only=True, as_string=True)
    measured_level = fields.Decimal(dump_only=True, as_string=True)
    is_out_of_tolerance = fields.Bool(dump_only=True)


class DesignSurfaceInputSchema(Schema):
    project_id = fields.UUID(required=True)
    name = fields.Str(required=True)
    source_format = fields.Str(allow_none=True)
    imported_at = fields.DateTime(allow_none=True)


class DesignSurfaceSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(dump_only=True)
    is_approved = fields.Bool(dump_only=True)


class CrossSectionInputSchema(Schema):
    project_id = fields.UUID(required=True)
    design_surface_id = fields.UUID(allow_none=True)
    chainage = fields.Decimal(required=True, as_string=True)
    design_points = fields.List(fields.Dict(), allow_none=True)
    field_points = fields.List(fields.Dict(), allow_none=True)
    captured_at = fields.DateTime(allow_none=True)


class CrossSectionSchema(Schema):
    id = fields.UUID(dump_only=True)
    chainage = fields.Decimal(dump_only=True, as_string=True)


class EarthworksVolumeInputSchema(Schema):
    project_id = fields.UUID(required=True)
    cross_section_id = fields.UUID(allow_none=True)
    design_surface_id = fields.UUID(allow_none=True)
    calculation_method = fields.Str(load_default="cross_section", validate=validate.OneOf(CALCULATION_METHODS))
    cut_volume = fields.Decimal(allow_none=True, as_string=True)
    fill_volume = fields.Decimal(allow_none=True, as_string=True)


class EarthworksVolumeSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    cut_volume = fields.Decimal(dump_only=True, as_string=True)
    fill_volume = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)
    is_official = fields.Bool(dump_only=True)
    submitted_for_billing = fields.Bool(dump_only=True)


class RoadAlignmentInputSchema(Schema):
    project_id = fields.UUID(required=True)
    name = fields.Str(required=True)
    horizontal_alignment = fields.List(fields.Dict(), allow_none=True)
    vertical_alignment = fields.List(fields.Dict(), allow_none=True)
    chainage_start = fields.Decimal(allow_none=True, as_string=True)
    chainage_end = fields.Decimal(allow_none=True, as_string=True)


class RoadAlignmentSchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(dump_only=True)


class AsBuiltRecordInputSchema(Schema):
    project_id = fields.UUID(required=True)
    scope_reference = fields.Str(allow_none=True)
    design_position = fields.Dict(allow_none=True)
    constructed_position = fields.Dict(allow_none=True)
    design_level = fields.Decimal(allow_none=True, as_string=True)
    constructed_level = fields.Decimal(allow_none=True, as_string=True)


class AsBuiltRecordUpdateSchema(Schema):
    constructed_position = fields.Dict(allow_none=True)
    constructed_level = fields.Decimal(allow_none=True, as_string=True)


class AsBuiltRecordSchema(Schema):
    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    scope_reference = fields.Str(dump_only=True)
    constructed_level = fields.Decimal(dump_only=True, as_string=True)
    locked = fields.Bool(dump_only=True)
    locked_at = fields.DateTime(dump_only=True)
