"""
Module 15 — Survey & Engineering (Code: SVY)
Service layer — business logic other modules must call through rather
than querying svy_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.15):
  - Earthworks Volume calculations used for billing must reference an
    approved design surface; ad hoc volume estimates are clearly
    flagged "preliminary" and cannot be submitted as a billing
    quantity.
  - As-Built Records are locked once the associated scope is marked
    complete and become part of the immutable handover package.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.svy.models import DesignSurface, EarthworksVolumeCalculation, AsBuiltRecord


# --- Level readings (SVY-03) ---------------------------------------------------

def record_level_reading(tenant_id, *, project_id, design_level, measured_level, tolerance=Decimal("0"), **kwargs):
    design_level = Decimal(str(design_level))
    measured_level = Decimal(str(measured_level))
    tolerance = Decimal(str(tolerance))

    out_of_tolerance = abs(measured_level - design_level) > tolerance

    from app.modules.svy.models import LevelReading

    reading = LevelReading(
        tenant_id=tenant_id,
        project_id=project_id,
        design_level=design_level,
        measured_level=measured_level,
        tolerance=tolerance,
        is_out_of_tolerance=out_of_tolerance,
        **kwargs,
    )
    db.session.add(reading)
    db.session.commit()
    return reading


# --- Design surfaces (SVY-08) --------------------------------------------------

def approve_design_surface(surface: DesignSurface, *, approved_by):
    if surface.is_approved:
        raise APIError("Design surface is already approved", status=409)
    surface.is_approved = True
    surface.approved_by = approved_by
    surface.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return surface


# --- Earthworks volumes (SVY-05, business rule) --------------------------------

def calculate_earthworks_volume(
    tenant_id, *, project_id, cut_volume, fill_volume, calculation_method="cross_section", design_surface_id=None, cross_section_id=None, calculated_by=None
):
    """
    Business rule: a calculation is "official" (billable) only if it
    references an APPROVED design surface. Without one -- or with one
    that isn't yet approved -- it is created as preliminary, and
    submit_for_billing will refuse it regardless of what the caller
    later tries to claim.
    """
    is_official = False
    if design_surface_id:
        surface = DesignSurface.query.filter_by(id=design_surface_id, tenant_id=tenant_id).first()
        if not surface:
            raise APIError("Design surface not found", status=404)
        is_official = surface.is_approved

    calc = EarthworksVolumeCalculation(
        tenant_id=tenant_id,
        project_id=project_id,
        cross_section_id=cross_section_id,
        design_surface_id=design_surface_id,
        calculation_method=calculation_method,
        cut_volume=cut_volume,
        fill_volume=fill_volume,
        status="official" if is_official else "preliminary",
        is_official=is_official,
        calculated_at=datetime.now(timezone.utc),
        calculated_by=calculated_by,
    )
    db.session.add(calc)
    db.session.commit()
    return calc


def submit_for_billing(calc: EarthworksVolumeCalculation):
    """
    The actual enforcement point: a preliminary (unofficial) volume
    calculation can be viewed, reported on, and used for internal
    progress tracking -- it simply cannot be submitted as a Module 18
    billing quantity. This is the gate a Module 18 caller must pass
    through, never a raw read of cut_volume/fill_volume.
    """
    if not calc.is_official:
        raise APIError(
            "Cannot submit a preliminary earthworks volume calculation for billing",
            status=409,
            detail="This calculation does not reference an approved design surface. "
            "It is flagged unofficial/preliminary and cannot be used as a billing quantity.",
        )
    if calc.submitted_for_billing:
        raise APIError("This calculation has already been submitted for billing", status=409)

    calc.submitted_for_billing = True
    db.session.commit()
    return calc


# --- As-built records (SVY-07, business rule) -----------------------------------

def lock_as_built_record(record: AsBuiltRecord):
    """
    Business rule: once locked, this is one-way -- nothing in this
    module provides a route back to `locked=False`. The record becomes
    part of the immutable handover package from this point on.
    """
    if record.locked:
        raise APIError("As-built record is already locked", status=409)

    record.locked = True
    record.locked_at = datetime.now(timezone.utc)
    db.session.commit()
    return record


def update_as_built_record(record: AsBuiltRecord, **fields):
    """The only path for editing an as-built record's captured data --
    refuses once locked, mirroring the pattern used for EXE's signed
    diaries and TBM's locked estimates."""
    if record.locked:
        raise APIError("As-built record is locked and cannot be edited", status=409)

    for key, value in fields.items():
        setattr(record, key, value)
    db.session.commit()
    return record
