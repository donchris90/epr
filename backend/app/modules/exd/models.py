"""
Module 21 — Executive Dashboard (Code: EXD)
SRS Section 4.21.

A single-screen, role-configured view for company leadership,
aggregating data that every other module produces. Per the SRS's own
framing, this module "introduces no new core business entities" beyond
`DashboardWidget` and `DashboardConfiguration` for personalization --
every actual metric is computed live from another module's data, never
stored here.

Design notes:
  - Business rule (SRS 4.21): dashboard figures are always traceable to
    source-module transactions via drill-down; the Executive Dashboard
    never stores an independently-editable number. This is enforced
    structurally, not just by convention: neither model below has ANY
    field that represents a business metric (no revenue, no CPI, no
    cash figure) -- only widget/layout configuration. Every metric
    lives in services.py as a function that queries another module's
    tables fresh on every call and returns a `drill_down` list of the
    specific source records the number came from.
  - This is the one module in the codebase where reading another
    module's tables directly (rather than calling its service
    functions) is the correct, intended design, not a bounded-context
    violation: EXD's entire purpose is read-only aggregation across
    modules for a dashboard, and it never writes to any of them. Where
    an earlier module already exposes a service function that does
    exactly the needed aggregation (e.g. Module 18's outstanding
    invoices report), this module calls that instead of re-querying
    the table itself.
  - EXD-13's natural-language querying depends on Module 25 (AI
    Construction Assistant), which does not exist yet -- not
    implemented here.
  - Not every widget named in SRS 4.21 (EXD-01 through EXD-11) is
    implemented with a real cross-module query in this pass: Company
    Revenue, Active Projects (CPI/SPI), Project Risks, AR/AP Aging, and
    Equipment Utilization are (see services.py, each backed by genuine
    queries against Modules 17/19/18/9's real data). Cash Position,
    Safety Score, Tender Pipeline, Profit Margin Trends, and Labor
    Productivity are left as documented TODOs rather than faked with
    placeholder numbers, since Module 17 has no running bank-balance
    concept yet, Module 14's composite safety score formula isn't
    specified precisely enough to implement responsibly, and the
    others would need aggregation logic this pass didn't have budget
    to build and test to the same standard as the rest of this
    codebase.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


WIDGET_TYPES = (
    "company_revenue",
    "project_profitability",
    "cash_position",
    "equipment_utilization",
    "safety_score",
    "active_projects",
    "tender_pipeline",
    "ar_ap_aging",
    "profit_margin_trend",
    "labor_productivity",
    "project_risks",
)


class DashboardWidget(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """A widget definition -- what KIND of live-computed data to show
    and how to configure it (filters, thresholds), never the data
    itself."""

    __tablename__ = "exd_dashboard_widgets"

    widget_type = db.Column(db.String(32), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    configuration = db.Column(JSONB, nullable=True)  # e.g. {"period_days": 30, "company_id": "..."}

    __table_args__ = (db.CheckConstraint(f"widget_type IN {WIDGET_TYPES}", name="ck_exd_widget_type"),)


class DashboardConfiguration(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """EXD-12: role-based dashboard configuration -- which widgets a
    role sees and what data scope (e.g. a region's project_ids) is
    applied to them. A Regional Director's configuration would carry a
    `region_project_ids` filter; a Group CEO's configuration would
    carry none (full consolidation)."""

    __tablename__ = "exd_dashboard_configurations"

    role_name = db.Column(db.String(128), nullable=False)  # e.g. "regional_director", "group_ceo"
    widget_ids = db.Column(JSONB, nullable=False, default=list)  # ordered list of DashboardWidget.id, as strings
    region_project_ids = db.Column(JSONB, nullable=True)  # list of project UUIDs this role is scoped to; null = all

    __table_args__ = (db.UniqueConstraint("tenant_id", "role_name", name="uq_exd_config_tenant_role"),)
