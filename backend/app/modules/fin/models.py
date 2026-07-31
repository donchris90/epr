"""
Module 17 — Financial Management (Code: FIN)
SRS Section 4.17.

A complete accounting system for project-costed, multi-company,
multi-currency construction accounting -- the ERP core, expressed
through the platform's project lifecycle rather than as an isolated
department.

Key Data Entities (SRS 4.17): GeneralLedgerEntry, ChartOfAccounts,
AccountsPayableInvoice, AccountsReceivableInvoice, BudgetControl,
CashFlowRecord, FixedAsset, BankStatement, BankReconciliation,
TaxRecord, FinancialStatement, ProjectCostRecord, Company.

Design notes:
  - `GeneralLedgerEntry` is split into `JournalEntry` (header:
    company, date, source module/reference, description) and
    `GeneralLedgerLine` (the actual debit/credit lines) -- standard
    double-entry structure. A journal entry with unbalanced lines
    should be structurally impossible to create; services.py enforces
    sum(debits) == sum(credits) before anything is committed.
  - `BudgetControl` is implemented as `BudgetControlPolicy`
    (tenant-configurable enforcement mode per cost category) rather
    than a single global switch, per FIN-04's explicit requirement that
    the policy be configurable per tenant per cost category.
  - `ProjectCostRecord` is not a stored table -- it's a computed view
    over GeneralLedgerLine grouped by project/cost code
    (services.get_project_cost_summary), the same reasoning already
    used for WFM's labor cost allocation and EST's Engineer's Estimate:
    there is nothing here that needs to exist independently of the
    ledger lines themselves.
  - Business rule (SRS 4.17): no transaction may post directly to the
    General Ledger bypassing its originating module -- there is no
    generic "create arbitrary journal entry" route anywhere in this
    module. Every posting path (services.post_accounts_payable_invoice,
    post_accounts_receivable_invoice) is tied to a real originating
    module, and the one exception path (post_manual_exception) is
    gated behind a distinct `fin:manual_exception` permission at the
    route level -- the same field-level-gate pattern already used for
    WFM's medical records and HSE's incident closure.
  - FIN-13 (fixed-point decimal, never floating point) is satisfied by
    construction: every monetary column here is `Numeric`, and every
    calculation in services.py works in `Decimal`, continuing the
    discipline already followed in every prior module of this codebase.
  - FIN-14 (immutable GL audit trail): once a JournalEntry's status is
    "posted", nothing in this module provides a route to edit or delete
    it or its lines -- the same one-way-lock pattern used for SVY's
    As-Built records and EXE's signed diaries.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


ACCOUNT_TYPES = ("asset", "liability", "equity", "revenue", "expense")
BUDGET_ENFORCEMENT_MODES = ("hard_block", "warning")
JOURNAL_STATUSES = ("posted",)  # see module docstring -- creation IS posting; no draft/edit workflow
AP_INVOICE_STATUSES = ("unpaid", "paid")
AR_INVOICE_STATUSES = ("unpaid", "paid")
BANK_LINE_STATUSES = ("unmatched", "matched", "exception")
TAX_TYPES = ("vat", "withholding", "other")
STATEMENT_TYPES = ("income_statement", "balance_sheet", "cash_flow_statement")


class Company(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-12: multi-company support for tenants operating more than
    one legal entity."""

    __tablename__ = "fin_companies"

    name = db.Column(db.String(255), nullable=False)
    functional_currency = db.Column(db.String(3), nullable=False, default="NGN")
    is_default = db.Column(db.Boolean, nullable=False, default=False)


class ChartOfAccounts(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-01: configurable chart of accounts, defaulting to a
    construction-industry template (seeding that template is an
    application-layer/setup concern, not modeled here)."""

    __tablename__ = "fin_chart_of_accounts"

    code = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    account_type = db.Column(db.String(16), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.CheckConstraint(f"account_type IN {ACCOUNT_TYPES}", name="ck_fin_coa_account_type"),
        db.UniqueConstraint("tenant_id", "code", name="uq_fin_coa_tenant_code"),
    )


class BudgetControlPolicy(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-04: business rule -- hard block vs. warning, configurable
    per tenant per cost category. `cost_category` NULL means the
    tenant-wide default policy; a specific value overrides it for that
    category."""

    __tablename__ = "fin_budget_control_policies"

    cost_category = db.Column(db.String(64), nullable=True)  # NULL = tenant-wide default
    enforcement_mode = db.Column(db.String(16), nullable=False, default="warning")

    __table_args__ = (
        db.CheckConstraint(f"enforcement_mode IN {BUDGET_ENFORCEMENT_MODES}", name="ck_fin_budget_policy_mode"),
    )


class JournalEntry(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-01, FIN-14: the header of a double-entry posting. Business
    rule -- every entry must originate from a real module
    (`source_module`); creation is immediate posting, and posted
    entries are immutable (see module docstring)."""

    __tablename__ = "fin_journal_entries"

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_companies.id"), nullable=False, index=True)
    entry_date = db.Column(db.Date, nullable=False)
    source_module = db.Column(db.String(32), nullable=False)  # e.g. "PRC", "SUB", "manual_exception"
    source_reference = db.Column(UUID(as_uuid=True), nullable=True)  # loose reference to the originating record
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="posted")
    posted_by = db.Column(UUID(as_uuid=True), nullable=True)
    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    exchange_rate = db.Column(db.Numeric(12, 6), nullable=False, default=1)

    lines = relationship("GeneralLedgerLine", back_populates="journal_entry", cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint("status IN ('posted')", name="ck_fin_journal_status"),)


class GeneralLedgerLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Exactly one of debit_amount/credit_amount is non-zero per line,
    by convention enforced in services.py (not a DB constraint, since
    "exactly one of two Numeric columns is nonzero" is awkward to
    express portably -- the balance check across ALL lines in an entry
    is the real guarantee)."""

    __tablename__ = "fin_general_ledger_lines"

    journal_entry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_journal_entries.id"), nullable=False, index=True)
    account_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_chart_of_accounts.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # FIN-10 cost allocation
    cost_code = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # est_cbs_line_items.id, loose reference

    debit_amount = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    credit_amount = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("ChartOfAccounts")


class AccountsPayableInvoice(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-02: generated from matched procurement invoices (Module 7)
    or subcontract certificates (Module 12) -- never created directly."""

    __tablename__ = "fin_ap_invoices"

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_companies.id"), nullable=False, index=True)
    journal_entry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_journal_entries.id"), nullable=False)
    counterparty_reference = db.Column(UUID(as_uuid=True), nullable=True)  # prc_vendors.id or sub_subcontractors.id, loose
    source_reference = db.Column(UUID(as_uuid=True), nullable=True)  # PO or payment certificate id, loose
    invoice_number = db.Column(db.String(128), nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="unpaid")

    __table_args__ = (db.CheckConstraint(f"status IN {AP_INVOICE_STATUSES}", name="ck_fin_ap_status"),)


class AccountsReceivableInvoice(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-03: generated from client billing (Module 18, not yet
    built) -- client_reference stays a loose UUID until that module
    exists to link against properly."""

    __tablename__ = "fin_ar_invoices"

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_companies.id"), nullable=False, index=True)
    journal_entry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_journal_entries.id"), nullable=False)
    client_reference = db.Column(UUID(as_uuid=True), nullable=True)  # loose reference
    source_reference = db.Column(UUID(as_uuid=True), nullable=True)  # loose reference
    invoice_number = db.Column(db.String(128), nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="unpaid")

    __table_args__ = (db.CheckConstraint(f"status IN {AR_INVOICE_STATUSES}", name="ck_fin_ar_status"),)


class FixedAsset(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-06: depreciation schedule, integrated with Module 9's
    equipment register (loose reference) where an asset is also
    operational plant."""

    __tablename__ = "fin_fixed_assets"

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_companies.id"), nullable=False, index=True)
    equipment_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)  # eqp_equipment.id, loose reference

    asset_name = db.Column(db.String(255), nullable=False)
    acquisition_cost = db.Column(db.Numeric(18, 4), nullable=False)
    salvage_value = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    useful_life_years = db.Column(db.Integer, nullable=True)
    acquired_at = db.Column(db.Date, nullable=True)
    accumulated_depreciation = db.Column(db.Numeric(18, 4), nullable=False, default=0)


class BankStatementLine(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-07: imported bank statement line, matched (automatically
    where possible) against a journal entry, or flagged as an
    exception."""

    __tablename__ = "fin_bank_statement_lines"

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_companies.id"), nullable=False, index=True)
    bank_account_ref = db.Column(db.String(128), nullable=True)
    transaction_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Numeric(18, 4), nullable=False)  # positive = inflow, negative = outflow
    matched_journal_entry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_journal_entries.id"), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="unmatched")

    __table_args__ = (db.CheckConstraint(f"status IN {BANK_LINE_STATUSES}", name="ck_fin_bank_line_status"),)


class TaxRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-08: VAT/withholding/other, configurable per jurisdiction, on
    a sales or purchase transaction."""

    __tablename__ = "fin_tax_records"

    journal_entry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_journal_entries.id"), nullable=False, index=True)
    tax_type = db.Column(db.String(16), nullable=False)
    rate = db.Column(db.Numeric(6, 4), nullable=False)  # e.g. 0.075 for 7.5% VAT
    taxable_amount = db.Column(db.Numeric(18, 4), nullable=False)
    tax_amount = db.Column(db.Numeric(18, 4), nullable=False)

    __table_args__ = (db.CheckConstraint(f"tax_type IN {TAX_TYPES}", name="ck_fin_tax_type"),)


class CashFlowForecastEntry(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-05: actual and forecast, at company and project level.
    `forecast_*` figures are caller-supplied (a forecast is an
    estimation input, not derivable from the ledger); `actual_*` is
    computed from this module's own posted ledger."""

    __tablename__ = "fin_cash_flow_forecast_entries"

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_companies.id"), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)

    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    forecast_inflow = db.Column(db.Numeric(18, 4), nullable=True)
    forecast_outflow = db.Column(db.Numeric(18, 4), nullable=True)
    actual_inflow = db.Column(db.Numeric(18, 4), nullable=True)
    actual_outflow = db.Column(db.Numeric(18, 4), nullable=True)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)


class FinancialStatement(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """FIN-09: Income Statement / Balance Sheet / Cash Flow Statement,
    at company or consolidated-group level. Stored as a generated
    snapshot (JSONB breakdown) -- a statement is itself a reportable,
    referenceable record, the same reasoning as PQ's ProductionReport."""

    __tablename__ = "fin_financial_statements"

    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey("fin_companies.id"), nullable=True)  # NULL = consolidated
    statement_type = db.Column(db.String(24), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    data = db.Column(JSONB, nullable=True)  # {account_type: total, ...} or richer breakdown
    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"statement_type IN {STATEMENT_TYPES}", name="ck_fin_statement_type"),)
