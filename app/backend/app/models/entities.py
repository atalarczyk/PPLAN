"""ORM entities for PPLAN baseline schema."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RoleType(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    BU_ADMIN = "bu_admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class MoneyCurrency(str, enum.Enum):
    PLN = "PLN"
    EUR = "EUR"
    USD = "USD"


class RateUnit(str, enum.Enum):
    DAY = "day"
    FTE_MONTH = "fte_month"


class BusinessUnit(Base):
    __tablename__ = "business_units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    microsoft_oid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        CheckConstraint(
            "((role = 'super_admin' AND business_unit_id IS NULL) "
            "OR (role <> 'super_admin' AND business_unit_id IS NOT NULL))",
            name="ck_role_assignments_scope_matches_role",
        ),
        UniqueConstraint("user_id", "role", "business_unit_id", name="uq_role_assignments_user_role_bu"),
        Index(
            "uq_role_assignments_user_role_global",
            "user_id",
            "role",
            unique=True,
            postgresql_where=text("business_unit_id IS NULL"),
            sqlite_where=text("business_unit_id IS NULL"),
        ),
        Index("ix_role_assignments_user_id", "user_id"),
        Index("ix_role_assignments_bu_id", "business_unit_id"),
        Index("ix_role_assignments_bu_active", "business_unit_id", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_units.id"), nullable=True
    )
    role: Mapped[RoleType] = mapped_column(
        SQLEnum(
            RoleType,
            name="role_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_business_unit_id", "business_unit_id"),
        UniqueConstraint("business_unit_id", "code", name="uq_projects_business_unit_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_units.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    start_month: Mapped[date] = mapped_column(Date, nullable=False)
    end_month: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(
            ProjectStatus,
            name="project_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ProjectStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ProjectStage(Base):
    __tablename__ = "project_stages"
    __table_args__ = (Index("ix_project_stages_project_id", "project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_month: Mapped[date] = mapped_column(Date, nullable=False)
    end_month: Mapped[date] = mapped_column(Date, nullable=False)
    color_token: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence_no: Mapped[int] = mapped_column(nullable=False)


class Performer(Base):
    __tablename__ = "performers"
    __table_args__ = (Index("ix_performers_business_unit_id", "business_unit_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_units.id"), nullable=False
    )
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_project_id", "project_id"),
        UniqueConstraint("project_id", "code", name="uq_tasks_project_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_stages.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TaskPerformerAssignment(Base):
    __tablename__ = "task_performer_assignments"
    __table_args__ = (
        Index("ix_task_performer_assignments_task_id", "task_id"),
        Index("ix_task_performer_assignments_performer_id", "performer_id"),
        UniqueConstraint("task_id", "performer_id", name="uq_task_performer_assignments"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    performer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("performers.id"), nullable=False
    )


class EffortMonthlyEntry(Base):
    __tablename__ = "effort_monthly_entries"
    __table_args__ = (
        CheckConstraint("planned_person_days >= 0", name="ck_effort_planned_non_negative"),
        CheckConstraint("actual_person_days >= 0", name="ck_effort_actual_non_negative"),
        Index("ix_effort_entries_project_month", "project_id", "month_start"),
        Index("ix_effort_entries_performer_month", "performer_id", "month_start"),
        UniqueConstraint(
            "project_id",
            "task_id",
            "performer_id",
            "month_start",
            name="uq_effort_entries_project_task_performer_month",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    performer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("performers.id"), nullable=False
    )
    month_start: Mapped[date] = mapped_column(Date, nullable=False)
    planned_person_days: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    actual_person_days: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))


class PerformerRate(Base):
    __tablename__ = "performer_rates"
    __table_args__ = (
        CheckConstraint("rate_value >= 0", name="ck_performer_rates_rate_value_non_negative"),
        Index("ix_performer_rates_performer_effective", "performer_id", "effective_from_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_units.id"), nullable=False
    )
    performer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("performers.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    rate_unit: Mapped[RateUnit] = mapped_column(
        SQLEnum(
            RateUnit,
            name="rate_unit",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    rate_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_from_month: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to_month: Mapped[date | None] = mapped_column(Date, nullable=True)


class FinancialRequest(Base):
    __tablename__ = "financial_requests"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_financial_requests_amount_non_negative"),
        Index("ix_financial_requests_project_month", "project_id", "month_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    request_no: Mapped[str] = mapped_column(String(128), nullable=False)
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    month_start: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[MoneyCurrency] = mapped_column(
        SQLEnum(
            MoneyCurrency,
            name="money_currency",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=MoneyCurrency.PLN,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_invoices_amount_non_negative"),
        Index("ix_invoices_project_month", "project_id", "month_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    invoice_no: Mapped[str] = mapped_column(String(128), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    month_start: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[MoneyCurrency] = mapped_column(
        SQLEnum(
            MoneyCurrency,
            name="money_currency",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=MoneyCurrency.PLN,
    )
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unpaid")
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Revenue(Base):
    __tablename__ = "revenues"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_revenues_amount_non_negative"),
        Index("ix_revenues_project_month", "project_id", "month_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    revenue_no: Mapped[str] = mapped_column(String(128), nullable=False)
    recognition_date: Mapped[date] = mapped_column(Date, nullable=False)
    month_start: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[MoneyCurrency] = mapped_column(
        SQLEnum(
            MoneyCurrency,
            name="money_currency",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=MoneyCurrency.PLN,
    )


class ProjectMonthlySnapshot(Base):
    __tablename__ = "project_monthly_snapshots"
    __table_args__ = (
        CheckConstraint("planned_person_days >= 0", name="ck_snapshots_planned_person_days_non_negative"),
        CheckConstraint("actual_person_days >= 0", name="ck_snapshots_actual_person_days_non_negative"),
        CheckConstraint("planned_cost >= 0", name="ck_snapshots_planned_cost_non_negative"),
        CheckConstraint("actual_cost >= 0", name="ck_snapshots_actual_cost_non_negative"),
        CheckConstraint("revenue_amount >= 0", name="ck_snapshots_revenue_amount_non_negative"),
        CheckConstraint("invoice_amount >= 0", name="ck_snapshots_invoice_amount_non_negative"),
        CheckConstraint("cumulative_planned_cost >= 0", name="ck_snapshots_cumulative_planned_cost_non_negative"),
        CheckConstraint("cumulative_actual_cost >= 0", name="ck_snapshots_cumulative_actual_cost_non_negative"),
        CheckConstraint("cumulative_revenue >= 0", name="ck_snapshots_cumulative_revenue_non_negative"),
        Index("ix_project_snapshots_project_month", "project_id", "month_start"),
        UniqueConstraint("project_id", "month_start", name="uq_project_snapshots_project_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    month_start: Mapped[date] = mapped_column(Date, nullable=False)
    planned_person_days: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    actual_person_days: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    planned_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    revenue_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    invoice_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cumulative_planned_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    cumulative_actual_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    cumulative_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_business_unit_id", "business_unit_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_units.id"), nullable=False
    )
    entity_name: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    before_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

