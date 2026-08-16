"""
Module 17 — Financial Management (Code: FIN)
Request/response schemas.
"""
from marshmallow import Schema, fields, validate

from app.modules.fin.models import ACCOUNT_TYPES, BUDGET_ENFORCEMENT_MODES


class CompanySchema(Schema):
    id = fields.UUID(dump_only=True)
    name = fields.Str(required=True)
    functional_currency = fields.Str(load_default="NGN")
    is_default = fields.Bool(load_default=False)


class ChartOfAccountsSchema(Schema):
    id = fields.UUID(dump_only=True)
    code = fields.Str(required=True)
    name = fields.Str(required=True)
    account_type = fields.Str(required=True, validate=validate.OneOf(ACCOUNT_TYPES))
    is_active = fields.Bool(dump_only=True)


class BudgetControlPolicyInputSchema(Schema):
    cost_category = fields.Str(allow_none=True, load_default=None)
    enforcement_mode = fields.Str(required=True, validate=validate.OneOf(BUDGET_ENFORCEMENT_MODES))


class BudgetControlPolicySchema(Schema):
    id = fields.UUID(dump_only=True)
    cost_category = fields.Str(dump_only=True)
    enforcement_mode = fields.Str(dump_only=True)


class CheckBudgetControlSchema(Schema):
    cost_code = fields.UUID(required=True)
    cost_category = fields.Str(allow_none=True, load_default=None)
    posting_amount = fields.Decimal(required=True, as_string=True)
    cbs_budget_amount = fields.Decimal(required=True, as_string=True)


class PostAPInvoiceSchema(Schema):
    company_id = fields.UUID(required=True)
    source_module = fields.Str(required=True)
    source_reference = fields.UUID(allow_none=True, load_default=None)
    invoice_number = fields.Str(required=True)
    amount = fields.Decimal(required=True, as_string=True)
    expense_account_id = fields.UUID(required=True)
    payable_account_id = fields.UUID(required=True)
    counterparty_reference = fields.UUID(allow_none=True)
    currency = fields.Str(load_default="NGN")
    due_date = fields.Date(allow_none=True)
    project_id = fields.UUID(allow_none=True)
    cost_code = fields.UUID(allow_none=True)
    cost_category = fields.Str(allow_none=True)
    cbs_budget_amount = fields.Decimal(allow_none=True, as_string=True)


class PostARInvoiceSchema(Schema):
    company_id = fields.UUID(required=True)
    source_module = fields.Str(required=True)
    source_reference = fields.UUID(allow_none=True, load_default=None)
    invoice_number = fields.Str(required=True)
    amount = fields.Decimal(required=True, as_string=True)
    receivable_account_id = fields.UUID(required=True)
    revenue_account_id = fields.UUID(required=True)
    client_reference = fields.UUID(allow_none=True)
    currency = fields.Str(load_default="NGN")
    due_date = fields.Date(allow_none=True)
    project_id = fields.UUID(allow_none=True)


class InvoiceSchema(Schema):
    id = fields.UUID(dump_only=True)
    invoice_number = fields.Str(dump_only=True)
    amount = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)
    journal_entry_id = fields.UUID(dump_only=True)


class ManualExceptionLineSchema(Schema):
    account_id = fields.UUID(required=True)
    debit_amount = fields.Decimal(load_default="0", as_string=True)
    credit_amount = fields.Decimal(load_default="0", as_string=True)
    project_id = fields.UUID(allow_none=True)
    cost_code = fields.UUID(allow_none=True)


class PostManualExceptionSchema(Schema):
    company_id = fields.UUID(required=True)
    description = fields.Str(required=True)
    entry_date = fields.Date(allow_none=True)
    lines = fields.List(fields.Nested(ManualExceptionLineSchema), required=True)


class JournalEntrySchema(Schema):
    id = fields.UUID(dump_only=True)
    company_id = fields.UUID(dump_only=True)
    entry_date = fields.Date(dump_only=True)
    source_module = fields.Str(dump_only=True)
    description = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)


class BankStatementLineInputSchema(Schema):
    company_id = fields.UUID(required=True)
    bank_account_ref = fields.Str(allow_none=True)
    transaction_date = fields.Date(required=True)
    description = fields.Str(allow_none=True)
    amount = fields.Decimal(required=True, as_string=True)


class BankStatementLineSchema(Schema):
    id = fields.UUID(dump_only=True)
    amount = fields.Decimal(dump_only=True, as_string=True)
    status = fields.Str(dump_only=True)
    matched_journal_entry_id = fields.UUID(dump_only=True)


class CashFlowForecastInputSchema(Schema):
    company_id = fields.UUID(required=True)
    project_id = fields.UUID(allow_none=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    forecast_inflow = fields.Decimal(allow_none=True, as_string=True)
    forecast_outflow = fields.Decimal(allow_none=True, as_string=True)


class CashFlowForecastSchema(Schema):
    id = fields.UUID(dump_only=True)
    forecast_inflow = fields.Decimal(dump_only=True, as_string=True)
    forecast_outflow = fields.Decimal(dump_only=True, as_string=True)
    actual_inflow = fields.Decimal(dump_only=True, as_string=True)
    actual_outflow = fields.Decimal(dump_only=True, as_string=True)


class IncomeStatementInputSchema(Schema):
    company_id = fields.UUID(allow_none=True, load_default=None)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)


class FinancialStatementSchema(Schema):
    id = fields.UUID(dump_only=True)
    statement_type = fields.Str(dump_only=True)
    period_start = fields.Date(dump_only=True)
    period_end = fields.Date(dump_only=True)
    data = fields.Dict(dump_only=True)
