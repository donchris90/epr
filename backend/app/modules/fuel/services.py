"""
Module 10 — Fuel Management (Code: FUEL)
Service layer — business logic other modules must call through rather
than querying fuel_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.10):
  - A Theft Flag does not auto-block operations; it generates a
    mandatory review task, escalating to Executive Dashboard visibility
    if unresolved beyond a configurable period.
  - Fuel Variance rolls into EQP-10's Cost per Hour as a DISTINCT line,
    never blended into a generic fuel cost figure -- see
    fuel_cost_breakdown, and app.modules.eqp.services.calculate_cost_per_hour's
    fuel_normal_cost / fuel_variance_cost parameters.
  - A manual fuel issue above a configurable quantity threshold requires
    a countersigned slip.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.fuel.models import (
    FuelTank,
    FuelPurchase,
    FuelIssue,
    FuelBurnRateProfile,
    FuelVarianceRecord,
    TheftFlag,
)

DEFAULT_COUNTERSIGNATURE_THRESHOLD_LITRES = Decimal("200")
DEFAULT_VARIANCE_THRESHOLD_PCT = Decimal("15")


# --- Purchases (FUEL-01) ------------------------------------------------------

def record_purchase(tenant_id, *, tank_id, vendor_id, quantity_litres, unit_price, delivered_at=None):
    quantity_litres = Decimal(str(quantity_litres))
    unit_price = Decimal(str(unit_price))

    tank = FuelTank.query.filter_by(id=tank_id, tenant_id=tenant_id).first()
    if not tank:
        raise APIError("Fuel tank not found", status=404)

    purchase = FuelPurchase(
        tenant_id=tenant_id,
        tank_id=tank_id,
        vendor_id=vendor_id,
        quantity_litres=quantity_litres,
        unit_price=unit_price,
        total_cost=quantity_litres * unit_price,
        delivered_at=delivered_at,
    )
    db.session.add(purchase)
    db.session.commit()
    return purchase


def confirm_delivery(purchase: FuelPurchase, *, confirmed_by):
    """Only confirmed deliveries update the tank balance (FUEL-01) --
    an unconfirmed purchase record is a paper trail, not yet stock."""
    if purchase.delivery_confirmed:
        raise APIError("Delivery is already confirmed", status=409)

    purchase.delivery_confirmed = True
    purchase.confirmed_by = confirmed_by
    purchase.tank.current_level_litres += purchase.quantity_litres

    db.session.commit()
    return purchase


# --- Tank reconciliation (FUEL-02, feeds FUEL-05) ----------------------------

def reconcile_tank(tank: FuelTank, *, dip_reading_litres, tolerance_litres=Decimal("20")):
    """
    Compares a physical dip/sensor reading against the system's
    recorded level. A discrepancy beyond tolerance is exactly the
    "tank-level drops do not match recorded issues" theft-detection
    trigger named in FUEL-05.
    """
    dip_reading_litres = Decimal(str(dip_reading_litres))
    tolerance_litres = Decimal(str(tolerance_litres))
    discrepancy = dip_reading_litres - tank.current_level_litres

    flag = None
    if abs(discrepancy) > tolerance_litres:
        flag = TheftFlag(
            tenant_id=tank.tenant_id,
            tank_id=tank.id,
            flag_reason="tank_level_mismatch",
            description=f"Dip reading {dip_reading_litres}L vs system level {tank.current_level_litres}L (discrepancy {discrepancy}L)",
            raised_at=datetime.now(timezone.utc),
        )
        db.session.add(flag)

    # The dip reading is physical ground truth -- reconcile the system
    # to match it regardless of whether a flag was raised, the same way
    # INV's stock-count adjustment corrects the books to the count.
    tank.current_level_litres = dip_reading_litres
    db.session.commit()

    return {"discrepancy_litres": discrepancy, "theft_flag": flag}


# --- Fuel issues (FUEL-03, FUEL-09 business rule) ----------------------------

def record_issue(
    tenant_id,
    *,
    tank_id,
    equipment_id,
    quantity_litres,
    issued_at,
    meter_reading=None,
    operator_id=None,
    issued_by=None,
    countersignature_threshold=DEFAULT_COUNTERSIGNATURE_THRESHOLD_LITRES,
):
    quantity_litres = Decimal(str(quantity_litres))

    tank = FuelTank.query.filter_by(id=tank_id, tenant_id=tenant_id).first()
    if not tank:
        raise APIError("Fuel tank not found", status=404)
    if quantity_litres > tank.current_level_litres:
        raise APIError("Insufficient fuel in tank", status=409, detail=f"Tank has {tank.current_level_litres}L, requested {quantity_litres}L.")

    issue = FuelIssue(
        tenant_id=tenant_id,
        tank_id=tank_id,
        equipment_id=equipment_id,
        operator_id=operator_id,
        quantity_litres=quantity_litres,
        meter_reading=meter_reading,
        issued_at=issued_at,
        issued_by=issued_by,
        requires_countersignature=quantity_litres > Decimal(str(countersignature_threshold)),
    )
    tank.current_level_litres -= quantity_litres

    db.session.add(issue)
    db.session.commit()
    return issue


def countersign_issue(issue: FuelIssue, *, countersigned_by):
    if not issue.requires_countersignature:
        raise APIError("This issue does not require a countersignature", status=409)
    if issue.countersigned:
        raise APIError("Issue is already countersigned", status=409)

    issue.countersigned = True
    issue.countersigned_by = countersigned_by
    issue.countersigned_at = datetime.now(timezone.utc)
    db.session.commit()
    return issue


def flag_issue_without_usage_log(issue: FuelIssue, *, has_usage_log: bool):
    """FUEL-05: a fuel issue with no corresponding equipment usage log.
    `has_usage_log` is supplied by the caller since usage logs belong
    to Module 6 (EXE) / Module 9 (EQP), not this module."""
    if has_usage_log:
        return None

    flag = TheftFlag(
        tenant_id=issue.tenant_id,
        equipment_id=issue.equipment_id,
        fuel_issue_id=issue.id,
        flag_reason="no_usage_log",
        description=f"Fuel issue of {issue.quantity_litres}L on {issue.issued_at} has no corresponding equipment usage log.",
        raised_at=datetime.now(timezone.utc),
    )
    db.session.add(flag)
    db.session.commit()
    return flag


# --- Fuel variance (FUEL-04, business rule) ----------------------------------

def calculate_fuel_variance(tenant_id, *, equipment_id, period_start, period_end, hours_operated):
    """
    `hours_operated` is supplied by the caller (Module 9 owns that
    data) -- same pattern used throughout for cross-module figures.
    Actual issued litres is computed from this module's own FuelIssue
    records, which it does own.
    """
    profile = FuelBurnRateProfile.query.filter_by(tenant_id=tenant_id, equipment_id=equipment_id).first()
    if not profile:
        raise APIError("No burn rate profile configured for this equipment", status=404)

    expected_litres = profile.expected_litres_per_hour * Decimal(str(hours_operated))

    # FuelIssue.issued_at is a DateTime column; comparing it against a
    # bare Date for period_end would implicitly compare against
    # midnight of that date, silently excluding every issue recorded
    # later that same day. Extend to the end of the day explicitly --
    # the same fix already applied in EQP's availability calculation.
    from datetime import datetime, time

    period_end_dt = datetime.combine(period_end, time.max)

    actual_litres = (
        db.session.query(db.func.coalesce(db.func.sum(FuelIssue.quantity_litres), 0))
        .filter(
            FuelIssue.tenant_id == tenant_id,
            FuelIssue.equipment_id == equipment_id,
            FuelIssue.issued_at >= period_start,
            FuelIssue.issued_at <= period_end_dt,
        )
        .scalar()
    )
    actual_litres = Decimal(actual_litres)

    variance_litres = actual_litres - expected_litres
    variance_pct = (variance_litres / expected_litres * 100) if expected_litres > 0 else None

    latest_purchase = (
        FuelPurchase.query.filter_by(tenant_id=tenant_id)
        .order_by(FuelPurchase.created_at.desc())
        .first()
    )
    unit_price = latest_purchase.unit_price if latest_purchase else None
    variance_cost = (variance_litres * unit_price) if unit_price is not None else None

    existing = FuelVarianceRecord.query.filter_by(
        tenant_id=tenant_id, equipment_id=equipment_id, period_start=period_start, period_end=period_end
    ).first()
    if existing:
        record = existing
    else:
        record = FuelVarianceRecord(tenant_id=tenant_id, equipment_id=equipment_id, period_start=period_start, period_end=period_end)
        db.session.add(record)

    record.expected_litres = expected_litres
    record.actual_litres = actual_litres
    record.variance_litres = variance_litres
    record.variance_pct = variance_pct
    record.unit_price_used = unit_price
    record.variance_cost = variance_cost
    db.session.commit()

    # Business rule: variance beyond threshold raises a theft flag,
    # but never blocks anything (see check_variance_theft_flag).
    return record


def check_variance_theft_flag(record: FuelVarianceRecord, *, threshold_pct=DEFAULT_VARIANCE_THRESHOLD_PCT):
    if record.variance_pct is None or abs(record.variance_pct) <= threshold_pct:
        return None

    flag = TheftFlag(
        tenant_id=record.tenant_id,
        equipment_id=record.equipment_id,
        flag_reason="variance_threshold_exceeded",
        description=f"Fuel variance {record.variance_pct}% exceeds {threshold_pct}% threshold for period {record.period_start} to {record.period_end}.",
        raised_at=datetime.now(timezone.utc),
    )
    db.session.add(flag)
    db.session.commit()
    return flag


def fuel_cost_breakdown(tenant_id, *, equipment_id, period_start, period_end, hours_operated) -> dict:
    """
    Business rule: variance rolls into Cost per Hour as a DISTINCT
    line. Returns normal_cost and variance_cost separately for exactly
    that purpose -- app.modules.eqp.services.calculate_cost_per_hour
    accepts both as separate parameters rather than one blended figure.
    """
    variance = calculate_fuel_variance(
        tenant_id, equipment_id=equipment_id, period_start=period_start, period_end=period_end, hours_operated=hours_operated
    )

    if variance.unit_price_used is None:
        return {"normal_cost": Decimal("0"), "variance_cost": Decimal("0")}

    normal_litres = min(variance.actual_litres, variance.expected_litres)
    normal_cost = normal_litres * variance.unit_price_used
    variance_cost = variance.variance_cost or Decimal("0")

    return {"normal_cost": normal_cost, "variance_cost": variance_cost}


# --- Theft flag escalation (business rule) -----------------------------------

def escalate_unresolved_theft_flags(tenant_id, *, threshold_days: int = 7, as_of=None):
    from datetime import date, timedelta

    as_of = as_of or date.today()
    horizon = as_of - timedelta(days=threshold_days)

    stale = TheftFlag.query.filter(
        TheftFlag.tenant_id == tenant_id,
        TheftFlag.status.in_(("open", "reviewing")),
        TheftFlag.raised_at.isnot(None),
        TheftFlag.raised_at < horizon,
    ).all()

    for flag in stale:
        flag.status = "escalated"
        flag.escalated_at = datetime.now(timezone.utc)

    db.session.commit()
    return stale
