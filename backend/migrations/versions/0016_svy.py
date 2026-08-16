"""svy module tables

Revision ID: 0016_svy
Revises: 0015_hse
Create Date: 2026-07-30

Creates the tables defined in app/modules/svy/models.py (SRS Section
4.15) and enables Row-Level Security + FORCE + the tenant_isolation
policy on every one of them, per SRS Section 5.5.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_svy"
down_revision = "0015_hse"
branch_labels = None
depends_on = None


SVY_TABLES = [
    "svy_control_points",
    "svy_gps_coordinates",
    "svy_level_readings",
    "svy_design_surfaces",
    "svy_cross_sections",
    "svy_earthworks_volume_calculations",
    "svy_road_alignments",
    "svy_as_built_records",
]


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def _enable_rls(table_name: str):
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table_name}
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def upgrade():
    op.create_table(
        "svy_control_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("point_name", sa.String(128), nullable=False),
        sa.Column("coordinate_system", sa.String(64), nullable=True),
        sa.Column("datum", sa.String(64), nullable=True),
        sa.Column("northing", sa.Numeric(14, 4), nullable=True),
        sa.Column("easting", sa.Numeric(14, 4), nullable=True),
        sa.Column("benchmark_elevation", sa.Numeric(10, 4), nullable=True),
        sa.Column("established_at", sa.Date, nullable=True),
        sa.Column("established_by", sa.String(255), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "svy_gps_coordinates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("control_point_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("svy_control_points.id"), nullable=True),
        sa.Column("photo_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("elevation", sa.Numeric(10, 4), nullable=True),
        sa.Column("purpose", sa.String(24), nullable=False, server_default="setting_out"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("purpose IN ('setting_out','as_built_verification')", name="ck_svy_gps_purpose"),
    )

    op.create_table(
        "svy_level_readings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("control_point_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("svy_control_points.id"), nullable=True),
        sa.Column("location_description", sa.String(255), nullable=True),
        sa.Column("design_level", sa.Numeric(10, 4), nullable=False),
        sa.Column("measured_level", sa.Numeric(10, 4), nullable=False),
        sa.Column("tolerance", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("is_out_of_tolerance", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("measured_by", sa.String(255), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "svy_design_surfaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_format", sa.String(32), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "svy_cross_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("design_surface_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("svy_design_surfaces.id"), nullable=True),
        sa.Column("chainage", sa.Numeric(10, 3), nullable=False),
        sa.Column("design_points", postgresql.JSONB, nullable=True),
        sa.Column("field_points", postgresql.JSONB, nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "svy_earthworks_volume_calculations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("cross_section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("svy_cross_sections.id"), nullable=True),
        sa.Column("design_surface_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("svy_design_surfaces.id"), nullable=True),
        sa.Column("calculation_method", sa.String(16), nullable=False, server_default="cross_section"),
        sa.Column("cut_volume", sa.Numeric(14, 4), nullable=True),
        sa.Column("fill_volume", sa.Numeric(14, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="preliminary"),
        sa.Column("is_official", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("submitted_for_billing", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculated_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("calculation_method IN ('cross_section','surface_model')", name="ck_svy_volume_method"),
        sa.CheckConstraint("status IN ('preliminary','official')", name="ck_svy_volume_status"),
    )

    op.create_table(
        "svy_road_alignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("horizontal_alignment", postgresql.JSONB, nullable=True),
        sa.Column("vertical_alignment", postgresql.JSONB, nullable=True),
        sa.Column("chainage_start", sa.Numeric(10, 3), nullable=True),
        sa.Column("chainage_end", sa.Numeric(10, 3), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "svy_as_built_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("scope_reference", sa.String(255), nullable=True),
        sa.Column("design_position", postgresql.JSONB, nullable=True),
        sa.Column("constructed_position", postgresql.JSONB, nullable=True),
        sa.Column("design_level", sa.Numeric(10, 4), nullable=True),
        sa.Column("constructed_level", sa.Numeric(10, 4), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("locked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )

    for table in SVY_TABLES:
        _enable_rls(table)


def downgrade():
    for table in reversed(SVY_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("svy_as_built_records")
    op.drop_table("svy_road_alignments")
    op.drop_table("svy_earthworks_volume_calculations")
    op.drop_table("svy_cross_sections")
    op.drop_table("svy_design_surfaces")
    op.drop_table("svy_level_readings")
    op.drop_table("svy_gps_coordinates")
    op.drop_table("svy_control_points")
