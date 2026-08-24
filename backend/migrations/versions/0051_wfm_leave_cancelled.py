"""wfm leave cancelled status

Revision ID: 0051_wfm_leave_cancelled
Revises: 0050_wfm_timesheet_statuses
Create Date: 2026-08-24

Real, small, additive extension: adds "cancelled" to LEAVE_STATUSES.
Confirmed genuinely missing before this -- LeaveRequest had no way to
represent a cancelled request, but this batch's own brief explicitly
requires Cancellation as a real leave action.
"""
from alembic import op

revision = "0051_wfm_leave_cancelled"
down_revision = "0050_wfm_timesheet_statuses"
branch_labels = None
depends_on = None

OLD_STATUSES = ("pending", "approved", "rejected")
NEW_STATUSES = ("pending", "approved", "rejected", "cancelled")


def upgrade():
    op.drop_constraint("ck_wfm_leave_requests_status", "wfm_leave_requests", type_="check")
    op.create_check_constraint("ck_wfm_leave_requests_status", "wfm_leave_requests", f"status IN {NEW_STATUSES}")


def downgrade():
    op.drop_constraint("ck_wfm_leave_requests_status", "wfm_leave_requests", type_="check")
    op.create_check_constraint("ck_wfm_leave_requests_status", "wfm_leave_requests", f"status IN {OLD_STATUSES}")
