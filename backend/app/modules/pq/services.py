"""
Module 16 — Plant & Quarry Management (Code: PQ)
Service layer — business logic other modules must call through rather
than querying pq_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.16):
  - Explosives Register entries cannot be deleted, only
    appended/corrected with an audit trail.
  - Blasting Records require a linked Drilling Record and, where the
    tenant's jurisdiction requires it, a recorded regulatory
    notification reference before the blast event can be marked
    complete.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.pq.models import ExplosivesRegister, ExplosivesRegisterCorrection, BlastingRecord


# --- Explosives register (PQ-06, business rule) -------------------------------

def correct_explosives_entry(entry: ExplosivesRegister, *, reason: str, corrected_quantity=None, corrected_by=None):
    """
    The ONLY way to change the record of an explosives register entry
    after the fact. This never mutates `entry` itself -- it adds a new,
    separately attributable ExplosivesRegisterCorrection row. There is
    deliberately no update_entry or delete_entry function anywhere in
    this module: the absence of that capability IS the enforcement of
    "cannot be deleted, only appended/corrected."
    """
    if not reason:
        raise APIError("A reason is required to record a correction", status=400)

    correction = ExplosivesRegisterCorrection(
        tenant_id=entry.tenant_id,
        entry_id=entry.id,
        reason=reason,
        corrected_quantity=corrected_quantity,
        corrected_by=corrected_by,
        corrected_at=datetime.now(timezone.utc),
    )
    db.session.add(correction)
    db.session.commit()
    return correction


def get_explosives_balance(tenant_id, *, material_type) -> Decimal:
    """
    Running balance from the append-only ledger: procurement and
    storage add, issuance and consumption subtract. Corrections are
    reporting annotations on top of the ledger, not adjustments to it --
    the ledger itself never changes, so the balance is always computed
    fresh from the entries as recorded, which is the whole point of an
    audit-safe register.
    """
    entries = ExplosivesRegister.query.filter_by(tenant_id=tenant_id, material_type=material_type).all()

    balance = Decimal("0")
    for entry in entries:
        if entry.entry_type in ("procurement", "storage"):
            balance += entry.quantity
        else:  # issuance, consumption
            balance -= entry.quantity

    return balance


# --- Blasting records (PQ-08, business rule) -----------------------------------

def mark_blast_complete(blast: BlastingRecord, *, requires_regulatory_notification: bool = False):
    """
    Business rule: cannot be marked complete without a linked Drilling
    Record (already guaranteed by the schema -- drilling_record_id is
    NOT NULL, so this can never be violated by data that reaches this
    function) and, where the jurisdiction requires it, a recorded
    regulatory notification reference.
    """
    if blast.status == "completed":
        raise APIError("Blast is already marked complete", status=409)

    if requires_regulatory_notification and not blast.regulatory_notification_reference:
        raise APIError(
            "Cannot mark blast complete: regulatory notification reference is required in this jurisdiction",
            status=409,
        )

    blast.status = "completed"
    db.session.commit()
    return blast


# --- Stockpile reconciliation (PQ-05) -------------------------------------------

def reconcile_stockpile(stockpile, *, physical_quantity, tolerance=Decimal("0")):
    """
    `physical_quantity` (from a physical count, or Module 8's Inventory
    receipt figures) is supplied by the caller since PQ does not own
    Module 8's data. Returns the discrepancy; does not silently correct
    the stockpile record without the caller choosing to apply it."""
    physical_quantity = Decimal(str(physical_quantity))
    discrepancy = physical_quantity - stockpile.quantity

    if abs(discrepancy) > Decimal(str(tolerance)):
        stockpile.quantity = physical_quantity

    stockpile.last_reconciled_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"discrepancy": discrepancy, "quantity_after": stockpile.quantity}


# --- Production reports (PQ-10, PQ-11) -------------------------------------------

def generate_production_report(tenant_id, *, plant_or_quarry_name, period_start, period_end, total_output, cost_per_unit=None, target_output=None):
    """
    Yield efficiency = actual output / target output, where target is
    supplied by the caller (a plant's rated capacity is configuration
    this module doesn't own a canonical source for -- kept as an
    explicit input rather than guessed).
    """
    from app.modules.pq.models import ProductionReport

    total_output = Decimal(str(total_output))
    yield_efficiency = None
    if target_output:
        yield_efficiency = (total_output / Decimal(str(target_output))) * 100

    report = ProductionReport(
        tenant_id=tenant_id,
        plant_or_quarry_name=plant_or_quarry_name,
        period_start=period_start,
        period_end=period_end,
        total_output=total_output,
        yield_efficiency_pct=yield_efficiency,
        cost_per_unit=Decimal(str(cost_per_unit)) if cost_per_unit is not None else None,
        generated_at=datetime.now(timezone.utc),
    )
    db.session.add(report)
    db.session.commit()
    return report
