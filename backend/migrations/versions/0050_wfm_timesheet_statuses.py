"""wfm timesheet returned/locked statuses

Revision ID: 0050_wfm_timesheet_statuses
Revises: 0049_scp_vnp_auth
Create Date: 2026-08-24

Real, small, additive extension: adds "returned" and "locked" to
TIMESHEET_STATUSES. Confirmed genuinely missing before this --
Timesheet had no way to represent either state, but this batch's own
brief explicitly requires both "Return for correction" and "Lock" as
real timesheet actions. "locked" also closes a real, critical gap in
generate_payroll_run, which previously had no status filter at all
(see the accompanying services.py fix) -- payroll now only ever
consumes "approved" or "locked" timesheets, matching this batch's own
explicit, capitalized requirement.
"""
from alembic import op

revision = "0050_wfm_timesheet_statuses"
down_revision = "0049_scp_vnp_auth"
branch_labels = None
depends_on = None

OLD_STATUSES = ("pending_approval", "approved", "rejected")
NEW_STATUSES = ("pending_approval", "approved", "rejected", "returned", "locked")


def upgrade():
    op.drop_constraint("ck_wfm_timesheets_status", "wfm_timesheets", type_="check")
    op.create_check_constraint("ck_wfm_timesheets_status", "wfm_timesheets", f"status IN {NEW_STATUSES}")


def downgrade():
    op.drop_constraint("ck_wfm_timesheets_status", "wfm_timesheets", type_="check")
    op.create_check_constraint("ck_wfm_timesheets_status", "wfm_timesheets", f"status IN {OLD_STATUSES}")
