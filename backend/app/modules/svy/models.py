"""
Module 15 — Survey & Engineering (Code: SVY)
SRS Section 4.15.

The geospatial and earthworks data unique to civil construction,
bridging field survey work and downstream billing/QMS.

Key Data Entities (SRS 4.15): SurveyControlPoint, GPSCoordinate,
LevelReading, CrossSection, EarthworksVolumeCalculation, RoadAlignment,
AsBuiltRecord.

Design notes:
  - `DesignSurface` is not in the SRS's named entity list but is what
    the first business rule actually needs: "Earthworks Volume
    calculations used for billing must reference an APPROVED design
    surface" requires somewhere for "approved design surface" to be a
    real, checkable fact, not just a string. SVY-08's design-surface
    import requirement needs the same table.
  - Business rule (SRS 4.15): an EarthworksVolumeCalculation is
    "official" (billable) only if it references an approved
    DesignSurface; without one it is `is_official=False` and
    `status='preliminary'` by construction, and
    services.submit_for_billing refuses anything not official.
  - Business rule (SRS 4.15): an AsBuiltRecord is locked once the
    associated scope is marked complete, becoming part of the immutable
    handover package -- `locked` is a one-way flag; nothing in this
    module provides a route back to `locked=False`.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


GPS_PURPOSES = ("setting_out", "as_built_verification")
CALCULATION_METHODS = ("cross_section", "surface_model")
VOLUME_STATUSES = ("preliminary", "official")


class SurveyControlPoint(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SVY-01: coordinate system, datum, and benchmark elevation."""

    __tablename__ = "svy_control_points"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    point_name = db.Column(db.String(128), nullable=False)
    coordinate_system = db.Column(db.String(64), nullable=True)  # e.g. "UTM Zone 32N"
    datum = db.Column(db.String(64), nullable=True)  # e.g. "WGS84"
    northing = db.Column(db.Numeric(14, 4), nullable=True)
    easting = db.Column(db.Numeric(14, 4), nullable=True)
    benchmark_elevation = db.Column(db.Numeric(10, 4), nullable=True)
    established_at = db.Column(db.Date, nullable=True)
    established_by = db.Column(db.String(255), nullable=True)


class GPSCoordinate(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SVY-02, SVY-09: setting-out and as-built verification points,
    optionally correlated to a control point and a GPS-tagged photo."""

    __tablename__ = "svy_gps_coordinates"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    control_point_id = db.Column(UUID(as_uuid=True), db.ForeignKey("svy_control_points.id"), nullable=True)
    photo_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)

    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    elevation = db.Column(db.Numeric(10, 4), nullable=True)
    purpose = db.Column(db.String(24), nullable=False, default="setting_out")
    captured_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"purpose IN {GPS_PURPOSES}", name="ck_svy_gps_purpose"),)


class LevelReading(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SVY-03: grading/formation-level verification against design
    levels, flagging out-of-tolerance readings."""

    __tablename__ = "svy_level_readings"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    control_point_id = db.Column(UUID(as_uuid=True), db.ForeignKey("svy_control_points.id"), nullable=True)

    location_description = db.Column(db.String(255), nullable=True)
    design_level = db.Column(db.Numeric(10, 4), nullable=False)
    measured_level = db.Column(db.Numeric(10, 4), nullable=False)
    tolerance = db.Column(db.Numeric(8, 4), nullable=False, default=0)
    is_out_of_tolerance = db.Column(db.Boolean, nullable=False, default=False)

    measured_at = db.Column(db.DateTime(timezone=True), nullable=True)
    measured_by = db.Column(db.String(255), nullable=True)


class DesignSurface(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SVY-08: imported design surface/alignment for comparison against
    field survey data. Approval status is what the earthworks billing
    business rule checks."""

    __tablename__ = "svy_design_surfaces"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    source_format = db.Column(db.String(32), nullable=True)  # e.g. "LandXML"
    imported_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    approved_by = db.Column(UUID(as_uuid=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    cross_sections = relationship("CrossSection", back_populates="design_surface")
    volume_calculations = relationship("EarthworksVolumeCalculation", back_populates="design_surface")


class CrossSection(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SVY-04: field cross-section captured against a design
    cross-section, for earthworks measurement."""

    __tablename__ = "svy_cross_sections"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    design_surface_id = db.Column(UUID(as_uuid=True), db.ForeignKey("svy_design_surfaces.id"), nullable=True)

    chainage = db.Column(db.Numeric(10, 3), nullable=False)
    design_points = db.Column(JSONB, nullable=True)  # [{offset, elevation}, ...]
    field_points = db.Column(JSONB, nullable=True)  # [{offset, elevation}, ...]
    captured_at = db.Column(db.DateTime(timezone=True), nullable=True)

    design_surface = relationship("DesignSurface", back_populates="cross_sections")


class EarthworksVolumeCalculation(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SVY-05: business rule -- billable ("official") only if it
    references an approved DesignSurface; otherwise preliminary and
    unbillable (see services.py)."""

    __tablename__ = "svy_earthworks_volume_calculations"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    cross_section_id = db.Column(UUID(as_uuid=True), db.ForeignKey("svy_cross_sections.id"), nullable=True)
    design_surface_id = db.Column(UUID(as_uuid=True), db.ForeignKey("svy_design_surfaces.id"), nullable=True)

    calculation_method = db.Column(db.String(16), nullable=False, default="cross_section")
    cut_volume = db.Column(db.Numeric(14, 4), nullable=True)
    fill_volume = db.Column(db.Numeric(14, 4), nullable=True)

    status = db.Column(db.String(16), nullable=False, default="preliminary")
    is_official = db.Column(db.Boolean, nullable=False, default=False)
    submitted_for_billing = db.Column(db.Boolean, nullable=False, default=False)

    calculated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    calculated_by = db.Column(UUID(as_uuid=True), nullable=True)

    design_surface = relationship("DesignSurface", back_populates="volume_calculations")

    __table_args__ = (
        db.CheckConstraint(f"calculation_method IN {CALCULATION_METHODS}", name="ck_svy_volume_method"),
        db.CheckConstraint(f"status IN {VOLUME_STATUSES}", name="ck_svy_volume_status"),
    )


class RoadAlignment(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SVY-06: horizontal and vertical alignment with chainage, for
    linear infrastructure projects."""

    __tablename__ = "svy_road_alignments"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    horizontal_alignment = db.Column(JSONB, nullable=True)  # [{chainage, northing, easting}, ...]
    vertical_alignment = db.Column(JSONB, nullable=True)  # [{chainage, elevation}, ...]
    chainage_start = db.Column(db.Numeric(10, 3), nullable=True)
    chainage_end = db.Column(db.Numeric(10, 3), nullable=True)


class AsBuiltRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """SVY-07: business rule -- locked once the associated scope is
    marked complete, becoming part of the immutable handover package
    (feeds Module 20 Asset Management)."""

    __tablename__ = "svy_as_built_records"

    project_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    scope_reference = db.Column(db.String(255), nullable=True)

    design_position = db.Column(JSONB, nullable=True)  # {northing, easting, elevation}
    constructed_position = db.Column(JSONB, nullable=True)
    design_level = db.Column(db.Numeric(10, 4), nullable=True)
    constructed_level = db.Column(db.Numeric(10, 4), nullable=True)

    captured_at = db.Column(db.DateTime(timezone=True), nullable=True)
    captured_by = db.Column(UUID(as_uuid=True), nullable=True)

    locked = db.Column(db.Boolean, nullable=False, default=False)
    locked_at = db.Column(db.DateTime(timezone=True), nullable=True)
