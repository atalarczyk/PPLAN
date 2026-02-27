"""initial schema

Revision ID: 20260226_0001
Revises:
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260226_0001"
down_revision = None
branch_labels = None
depends_on = None


role_type = postgresql.ENUM(
    "super_admin", "bu_admin", "editor", "viewer", name="role_type", create_type=False
)
project_status = postgresql.ENUM("draft", "active", "closed", name="project_status", create_type=False)
money_currency = postgresql.ENUM("PLN", "EUR", "USD", name="money_currency", create_type=False)
rate_unit = postgresql.ENUM("day", "fte_month", name="rate_unit", create_type=False)


def upgrade() -> None:
    role_type.create(op.get_bind(), checkfirst=True)
    project_status.create(op.get_bind(), checkfirst=True)
    money_currency.create(op.get_bind(), checkfirst=True)
    rate_unit.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "business_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("microsoft_oid", sa.String(length=128), nullable=False, unique=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "business_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_units.id"),
            nullable=True,
        ),
        sa.Column("role", role_type, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_role_assignments_user_id", "role_assignments", ["user_id"])
    op.create_index("ix_role_assignments_bu_id", "role_assignments", ["business_unit_id"])

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "business_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_units.id"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("start_month", sa.Date(), nullable=False),
        sa.Column("end_month", sa.Date(), nullable=False),
        sa.Column("status", project_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_business_unit_id", "projects", ["business_unit_id"])
    op.create_unique_constraint("uq_projects_business_unit_code", "projects", ["business_unit_id", "code"])

    op.create_table(
        "project_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("start_month", sa.Date(), nullable=False),
        sa.Column("end_month", sa.Date(), nullable=False),
        sa.Column("color_token", sa.String(length=32), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
    )
    op.create_index("ix_project_stages_project_id", "project_stages", ["project_id"])

    op.create_table(
        "performers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "business_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_units.id"),
            nullable=False,
        ),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_performers_business_unit_id", "performers", ["business_unit_id"])

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_stages.id"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_unique_constraint("uq_tasks_project_code", "tasks", ["project_id", "code"])

    op.create_table(
        "task_performer_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("performer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("performers.id"), nullable=False),
    )
    op.create_index("ix_task_performer_assignments_task_id", "task_performer_assignments", ["task_id"])
    op.create_index(
        "ix_task_performer_assignments_performer_id",
        "task_performer_assignments",
        ["performer_id"],
    )
    op.create_unique_constraint(
        "uq_task_performer_assignments", "task_performer_assignments", ["task_id", "performer_id"]
    )

    op.create_table(
        "effort_monthly_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("performer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("performers.id"), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("planned_person_days", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("actual_person_days", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.CheckConstraint("planned_person_days >= 0", name="ck_effort_planned_non_negative"),
        sa.CheckConstraint("actual_person_days >= 0", name="ck_effort_actual_non_negative"),
    )
    op.create_index("ix_effort_entries_project_month", "effort_monthly_entries", ["project_id", "month_start"])
    op.create_index(
        "ix_effort_entries_performer_month", "effort_monthly_entries", ["performer_id", "month_start"]
    )
    op.create_unique_constraint(
        "uq_effort_entries_project_task_performer_month",
        "effort_monthly_entries",
        ["project_id", "task_id", "performer_id", "month_start"],
    )

    op.create_table(
        "performer_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "business_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_units.id"),
            nullable=False,
        ),
        sa.Column("performer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("performers.id"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("rate_unit", rate_unit, nullable=False),
        sa.Column("rate_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("effective_from_month", sa.Date(), nullable=False),
        sa.Column("effective_to_month", sa.Date(), nullable=True),
    )
    op.create_index(
        "ix_performer_rates_performer_effective",
        "performer_rates",
        ["performer_id", "effective_from_month"],
    )

    op.create_table(
        "financial_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("request_no", sa.String(length=128), nullable=False),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", money_currency, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )
    op.create_index(
        "ix_financial_requests_project_month", "financial_requests", ["project_id", "month_start"]
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("invoice_no", sa.String(length=128), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", money_currency, nullable=False),
        sa.Column("payment_status", sa.String(length=32), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_invoices_project_month", "invoices", ["project_id", "month_start"])

    op.create_table(
        "revenues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("revenue_no", sa.String(length=128), nullable=False),
        sa.Column("recognition_date", sa.Date(), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", money_currency, nullable=False),
    )
    op.create_index("ix_revenues_project_month", "revenues", ["project_id", "month_start"])

    op.create_table(
        "project_monthly_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("planned_person_days", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("actual_person_days", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("planned_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("actual_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("revenue_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("invoice_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("cumulative_planned_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("cumulative_actual_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("cumulative_revenue", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
    )
    op.create_index(
        "ix_project_snapshots_project_month",
        "project_monthly_snapshots",
        ["project_id", "month_start"],
    )
    op.create_unique_constraint(
        "uq_project_snapshots_project_month", "project_monthly_snapshots", ["project_id", "month_start"]
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "business_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_units.id"),
            nullable=False,
        ),
        sa.Column("entity_name", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("before_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_business_unit_id", "audit_events", ["business_unit_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_business_unit_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_constraint("uq_project_snapshots_project_month", "project_monthly_snapshots", type_="unique")
    op.drop_index("ix_project_snapshots_project_month", table_name="project_monthly_snapshots")
    op.drop_table("project_monthly_snapshots")

    op.drop_index("ix_revenues_project_month", table_name="revenues")
    op.drop_table("revenues")

    op.drop_index("ix_invoices_project_month", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_financial_requests_project_month", table_name="financial_requests")
    op.drop_table("financial_requests")

    op.drop_index("ix_performer_rates_performer_effective", table_name="performer_rates")
    op.drop_table("performer_rates")

    op.drop_constraint(
        "uq_effort_entries_project_task_performer_month", "effort_monthly_entries", type_="unique"
    )
    op.drop_index("ix_effort_entries_performer_month", table_name="effort_monthly_entries")
    op.drop_index("ix_effort_entries_project_month", table_name="effort_monthly_entries")
    op.drop_table("effort_monthly_entries")

    op.drop_constraint("uq_task_performer_assignments", "task_performer_assignments", type_="unique")
    op.drop_index("ix_task_performer_assignments_performer_id", table_name="task_performer_assignments")
    op.drop_index("ix_task_performer_assignments_task_id", table_name="task_performer_assignments")
    op.drop_table("task_performer_assignments")

    op.drop_constraint("uq_tasks_project_code", "tasks", type_="unique")
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_performers_business_unit_id", table_name="performers")
    op.drop_table("performers")

    op.drop_index("ix_project_stages_project_id", table_name="project_stages")
    op.drop_table("project_stages")

    op.drop_constraint("uq_projects_business_unit_code", "projects", type_="unique")
    op.drop_index("ix_projects_business_unit_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_role_assignments_bu_id", table_name="role_assignments")
    op.drop_index("ix_role_assignments_user_id", table_name="role_assignments")
    op.drop_table("role_assignments")

    op.drop_table("users")
    op.drop_table("business_units")

    rate_unit.drop(op.get_bind(), checkfirst=True)
    money_currency.drop(op.get_bind(), checkfirst=True)
    project_status.drop(op.get_bind(), checkfirst=True)
    role_type.drop(op.get_bind(), checkfirst=True)

