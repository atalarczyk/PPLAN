"""phase1 access constraints and non-negative checks

Revision ID: 20260226_0002
Revises: 20260226_0001
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260226_0002"
down_revision = "20260226_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_role_assignments_scope_matches_role",
        "role_assignments",
        "((role = 'super_admin' AND business_unit_id IS NULL) "
        "OR (role <> 'super_admin' AND business_unit_id IS NOT NULL))",
    )
    op.create_unique_constraint(
        "uq_role_assignments_user_role_bu",
        "role_assignments",
        ["user_id", "role", "business_unit_id"],
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_role_assignments_user_role_global
        ON role_assignments (user_id, role)
        WHERE business_unit_id IS NULL
        """
    )
    op.create_index("ix_role_assignments_bu_active", "role_assignments", ["business_unit_id", "active"])

    op.create_check_constraint(
        "ck_performer_rates_rate_value_non_negative",
        "performer_rates",
        "rate_value >= 0",
    )
    op.create_check_constraint(
        "ck_financial_requests_amount_non_negative",
        "financial_requests",
        "amount >= 0",
    )
    op.create_check_constraint(
        "ck_invoices_amount_non_negative",
        "invoices",
        "amount >= 0",
    )
    op.create_check_constraint(
        "ck_revenues_amount_non_negative",
        "revenues",
        "amount >= 0",
    )

    op.create_check_constraint(
        "ck_snapshots_planned_person_days_non_negative",
        "project_monthly_snapshots",
        "planned_person_days >= 0",
    )
    op.create_check_constraint(
        "ck_snapshots_actual_person_days_non_negative",
        "project_monthly_snapshots",
        "actual_person_days >= 0",
    )
    op.create_check_constraint(
        "ck_snapshots_planned_cost_non_negative",
        "project_monthly_snapshots",
        "planned_cost >= 0",
    )
    op.create_check_constraint(
        "ck_snapshots_actual_cost_non_negative",
        "project_monthly_snapshots",
        "actual_cost >= 0",
    )
    op.create_check_constraint(
        "ck_snapshots_revenue_amount_non_negative",
        "project_monthly_snapshots",
        "revenue_amount >= 0",
    )
    op.create_check_constraint(
        "ck_snapshots_invoice_amount_non_negative",
        "project_monthly_snapshots",
        "invoice_amount >= 0",
    )
    op.create_check_constraint(
        "ck_snapshots_cumulative_planned_cost_non_negative",
        "project_monthly_snapshots",
        "cumulative_planned_cost >= 0",
    )
    op.create_check_constraint(
        "ck_snapshots_cumulative_actual_cost_non_negative",
        "project_monthly_snapshots",
        "cumulative_actual_cost >= 0",
    )
    op.create_check_constraint(
        "ck_snapshots_cumulative_revenue_non_negative",
        "project_monthly_snapshots",
        "cumulative_revenue >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_snapshots_cumulative_revenue_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_snapshots_cumulative_actual_cost_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_snapshots_cumulative_planned_cost_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_snapshots_invoice_amount_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_snapshots_revenue_amount_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_snapshots_actual_cost_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_snapshots_planned_cost_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_snapshots_actual_person_days_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_snapshots_planned_person_days_non_negative",
        "project_monthly_snapshots",
        type_="check",
    )

    op.drop_constraint("ck_revenues_amount_non_negative", "revenues", type_="check")
    op.drop_constraint("ck_invoices_amount_non_negative", "invoices", type_="check")
    op.drop_constraint(
        "ck_financial_requests_amount_non_negative",
        "financial_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_performer_rates_rate_value_non_negative",
        "performer_rates",
        type_="check",
    )

    op.drop_index("ix_role_assignments_bu_active", table_name="role_assignments")
    op.execute("DROP INDEX IF EXISTS uq_role_assignments_user_role_global")
    op.drop_constraint("uq_role_assignments_user_role_bu", "role_assignments", type_="unique")
    op.drop_constraint("ck_role_assignments_scope_matches_role", "role_assignments", type_="check")

