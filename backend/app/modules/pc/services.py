"""
Module 19 — Project Controls (Code: PC)
Service layer — business logic other modules must call through rather
than querying pc_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.19):
  - EVM calculations always use the currently active baseline and
    current CBS budget; snapshots are immutable historical records, so
    a recalculation for a prior period_end never overwrites an earlier
    one -- there is no update path anywhere in this module.
  - A project whose CPI or SPI falls below a configurable threshold
    (default 0.9) surfaces on the at-risk list.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.pc.models import EVMSnapshot, ForecastAtCompletion, RiskRegisterEntry

DEFAULT_PERFORMANCE_THRESHOLD = Decimal("0.9")


# --- EVM snapshot (PC-01 through PC-05) -----------------------------------------

def create_evm_snapshot(
    tenant_id,
    *,
    project_id,
    period_end,
    planned_value,
    earned_value,
    actual_cost,
    budget_at_completion,
    baseline_id=None,
    calculated_by=None,
):
    """
    PV/EV/AC/BAC are caller-supplied (Modules 5/6/17/3 own those
    figures respectively). This function computes the derived metrics
    -- CV, SV, CPI, SPI -- which is the actual arithmetic this module
    is responsible for getting right.

    CPI/SPI are left NULL (not zero, not an error) when the denominator
    is zero, since "no actual cost yet" or "no planned value yet" is a
    real, meaningful state (e.g. a project that hasn't started spending
    or hasn't reached its baseline start date) -- forcing a number here
    would misrepresent that state as either a perfect or catastrophic
    performance index.
    """
    pv = Decimal(str(planned_value))
    ev = Decimal(str(earned_value))
    ac = Decimal(str(actual_cost))
    bac = Decimal(str(budget_at_completion))

    cost_variance = ev - ac
    schedule_variance = ev - pv
    cpi = (ev / ac) if ac != 0 else None
    spi = (ev / pv) if pv != 0 else None

    snapshot = EVMSnapshot(
        tenant_id=tenant_id,
        project_id=project_id,
        period_end=period_end,
        baseline_id=baseline_id,
        planned_value=pv,
        earned_value=ev,
        actual_cost=ac,
        budget_at_completion=bac,
        cost_variance=cost_variance,
        schedule_variance=schedule_variance,
        cpi=cpi,
        spi=spi,
        calculated_at=datetime.now(timezone.utc),
        calculated_by=calculated_by,
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


# --- Forecast at Completion (PC-06) ---------------------------------------------

def generate_forecast(snapshot: EVMSnapshot, *, method="cpi_based", manual_eac=None, manual_reason=None):
    """
    EAC (Estimate at Completion):
      - cpi_based: BAC / CPI -- assumes the REMAINING work continues at
        the CURRENT cost-efficiency rate (the standard default method).
      - atypical_variance: AC + (BAC - EV) -- assumes the current
        variance was a one-off and remaining work will proceed exactly
        at the ORIGINAL planned rate.
      - manual: caller-supplied re-estimate (requires a reason -- a
        manual override without a documented reason is not
        auditable).
    ETC (Estimate to Complete) = EAC - AC.
    VAC (Variance at Completion) = BAC - EAC.
    """
    bac = snapshot.budget_at_completion
    ac = snapshot.actual_cost
    ev = snapshot.earned_value

    if method == "cpi_based":
        if not snapshot.cpi:
            raise APIError("Cannot use the CPI-based method: CPI is undefined (actual cost is zero)", status=409)
        eac = bac / snapshot.cpi
    elif method == "atypical_variance":
        eac = ac + (bac - ev)
    elif method == "manual":
        if manual_eac is None:
            raise APIError("manual_eac is required for the manual re-estimate method", status=400)
        if not manual_reason:
            raise APIError("A reason is required for a manual re-estimate (audit trail)", status=400)
        eac = Decimal(str(manual_eac))
    else:
        raise APIError("Invalid forecast method", status=400)

    etc = eac - ac
    vac = bac - eac

    forecast = ForecastAtCompletion(
        tenant_id=snapshot.tenant_id,
        evm_snapshot_id=snapshot.id,
        method=method,
        estimate_at_completion=eac,
        estimate_to_complete=etc,
        variance_at_completion=vac,
        manual_reestimate_reason=manual_reason if method == "manual" else None,
    )
    db.session.add(forecast)
    db.session.commit()
    return forecast


# --- Performance threshold (business rule) --------------------------------------

def list_at_risk_projects(tenant_id, *, threshold=DEFAULT_PERFORMANCE_THRESHOLD):
    """
    Business rule: a project whose CPI or SPI falls below the
    configurable threshold surfaces on the at-risk list. Uses each
    project's MOST RECENT snapshot (by period_end) -- an old snapshot
    from a project that has since recovered should not keep it flagged.
    """
    threshold = Decimal(str(threshold))

    latest_per_project = (
        db.session.query(EVMSnapshot.project_id, db.func.max(EVMSnapshot.period_end).label("latest_period"))
        .filter(EVMSnapshot.tenant_id == tenant_id)
        .group_by(EVMSnapshot.project_id)
        .subquery()
    )

    latest_snapshots = EVMSnapshot.query.join(
        latest_per_project,
        db.and_(
            EVMSnapshot.project_id == latest_per_project.c.project_id,
            EVMSnapshot.period_end == latest_per_project.c.latest_period,
        ),
    ).filter(EVMSnapshot.tenant_id == tenant_id).all()

    at_risk = [
        s
        for s in latest_snapshots
        if (s.cpi is not None and s.cpi < threshold) or (s.spi is not None and s.spi < threshold)
    ]
    return at_risk


# --- Risk register (PC-08) --------------------------------------------------------

def add_risk_entry(tenant_id, *, project_id, description, probability, impact_value, mitigation_owner=None, identified_at=None):
    probability = Decimal(str(probability))
    impact_value = Decimal(str(impact_value))
    exposure_value = probability * impact_value

    entry = RiskRegisterEntry(
        tenant_id=tenant_id,
        project_id=project_id,
        description=description,
        probability=probability,
        impact_value=impact_value,
        exposure_value=exposure_value,
        mitigation_owner=mitigation_owner,
        identified_at=identified_at,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


# --- Delay analysis (PC-09) --------------------------------------------------------

def classify_delay(*, schedule_variance, cost_variance) -> str:
    """
    Distinguishes schedule-driven from cost-driven performance issues
    by the sign of SV and CV from the linked snapshot -- a project
    behind schedule (SV < 0) but on-or-under cost (CV >= 0) is purely
    schedule_driven; the reverse is cost_driven; both negative is
    genuinely both; neither negative is a healthy project.
    """
    behind_schedule = schedule_variance < 0
    over_cost = cost_variance < 0

    if behind_schedule and over_cost:
        return "both"
    if behind_schedule:
        return "schedule_driven"
    if over_cost:
        return "cost_driven"
    return "neither"


def summarize_delay_analysis(tenant_id, *, project_id, period_end, snapshot: EVMSnapshot, total_float_consumed_days=None, critical_path_delay_days=None):
    from app.modules.pc.models import DelayAnalysisSummary

    classification = classify_delay(schedule_variance=snapshot.schedule_variance, cost_variance=snapshot.cost_variance)

    summary = DelayAnalysisSummary(
        tenant_id=tenant_id,
        project_id=project_id,
        evm_snapshot_id=snapshot.id,
        period_end=period_end,
        total_float_consumed_days=total_float_consumed_days,
        critical_path_delay_days=critical_path_delay_days,
        classification=classification,
    )
    db.session.add(summary)
    db.session.commit()
    return summary


# --- Cash flow forecast (PC-07) -----------------------------------------------------

def generate_project_cash_flow_forecast(tenant_id, *, project_id, period_start, period_end, committed_costs, planned_billing):
    from app.modules.pc.models import ProjectCashFlowForecast

    committed_costs = Decimal(str(committed_costs))
    planned_billing = Decimal(str(planned_billing))

    forecast = ProjectCashFlowForecast(
        tenant_id=tenant_id,
        project_id=project_id,
        period_start=period_start,
        period_end=period_end,
        committed_costs=committed_costs,
        planned_billing=planned_billing,
        net_cash_flow=planned_billing - committed_costs,
        generated_at=datetime.now(timezone.utc),
    )
    db.session.add(forecast)
    db.session.commit()
    return forecast
