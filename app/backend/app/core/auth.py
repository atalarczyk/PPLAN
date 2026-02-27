"""Authentication context extraction and RBAC guard utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.dependencies import get_db_session
from app.models.entities import BusinessUnit, RoleAssignment, RoleType, User


class AppRole(str, Enum):
    """Application role names aligned with delivery plan contract."""

    SUPER_ADMIN = "super_admin"
    BUSINESS_UNIT_ADMIN = "business_unit_admin"
    EDITOR = "editor"
    VIEWER = "viewer"


ROLE_TYPE_TO_APP_ROLE: dict[RoleType, AppRole] = {
    RoleType.SUPER_ADMIN: AppRole.SUPER_ADMIN,
    RoleType.BU_ADMIN: AppRole.BUSINESS_UNIT_ADMIN,
    RoleType.EDITOR: AppRole.EDITOR,
    RoleType.VIEWER: AppRole.VIEWER,
}


APP_ROLE_TO_DB_ROLE: dict[AppRole, RoleType] = {
    AppRole.SUPER_ADMIN: RoleType.SUPER_ADMIN,
    AppRole.BUSINESS_UNIT_ADMIN: RoleType.BU_ADMIN,
    AppRole.EDITOR: RoleType.EDITOR,
    AppRole.VIEWER: RoleType.VIEWER,
}


@dataclass(frozen=True)
class EffectiveRoleAssignment:
    """Effective role assignment resolved for request context."""

    role: AppRole
    business_unit_id: UUID | None
    assignment_id: UUID


@dataclass(frozen=True)
class RequestUserContext:
    """Authenticated request actor resolved from headers and DB state."""

    user_id: UUID
    microsoft_oid: str
    email: str
    display_name: str
    status: str
    roles: tuple[EffectiveRoleAssignment, ...]

    @property
    def role_names(self) -> tuple[AppRole, ...]:
        """Unique role names assigned to this user."""

        return tuple(dict.fromkeys(assignment.role for assignment in self.roles))

    @property
    def business_unit_ids(self) -> tuple[UUID, ...]:
        """Business unit scope IDs where the user has explicit assignment."""

        scoped: list[UUID] = []
        for assignment in self.roles:
            if assignment.business_unit_id is not None and assignment.business_unit_id not in scoped:
                scoped.append(assignment.business_unit_id)
        return tuple(scoped)

    @property
    def is_super_admin(self) -> bool:
        """Whether current user has super admin role."""

        return AppRole.SUPER_ADMIN in self.role_names


def _require_identity_headers(
    x_ms_oid: str | None,
    x_ms_email: str | None,
    x_ms_display_name: str | None,
) -> tuple[str, str, str]:
    if not x_ms_oid or not x_ms_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing identity headers. Expected X-MS-OID and X-MS-EMAIL or enable development principal fallback."
            ),
        )

    display_name = x_ms_display_name or x_ms_email
    return x_ms_oid.strip(), x_ms_email.strip().lower(), display_name.strip()


def _resolve_identity(
    x_ms_oid: str | None,
    x_ms_email: str | None,
    x_ms_display_name: str | None,
) -> tuple[str, str, str]:
    settings = get_settings()
    if x_ms_oid and x_ms_email:
        return _require_identity_headers(x_ms_oid, x_ms_email, x_ms_display_name)

    if settings.auth_allow_dev_principal:
        return (
            settings.auth_dev_microsoft_oid.strip(),
            settings.auth_dev_email.strip().lower(),
            settings.auth_dev_display_name.strip(),
        )

    return _require_identity_headers(x_ms_oid, x_ms_email, x_ms_display_name)


def _upsert_user(db: Session, *, microsoft_oid: str, email: str, display_name: str) -> User:
    user = db.scalar(select(User).where(User.microsoft_oid == microsoft_oid))
    now = datetime.utcnow()

    if user is None:
        user = User(
            microsoft_oid=microsoft_oid,
            email=email,
            display_name=display_name,
            status="active",
            last_login_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()
        return user

    changed = False
    if user.email != email:
        user.email = email
        changed = True
    if user.display_name != display_name:
        user.display_name = display_name
        changed = True

    user.last_login_at = now
    if changed:
        user.updated_at = now
    db.flush()
    return user


def ensure_user_principal(
    db: Session,
    *,
    microsoft_oid: str,
    email: str,
    display_name: str,
) -> User:
    """Ensure user exists and return persisted row.

    Utility exported for tests and seed helpers.
    """

    normalized_oid = microsoft_oid.strip()
    normalized_email = email.strip().lower()
    normalized_display_name = display_name.strip() or normalized_email

    user = _upsert_user(
        db,
        microsoft_oid=normalized_oid,
        email=normalized_email,
        display_name=normalized_display_name,
    )
    db.commit()
    db.refresh(user)
    return user


def _load_effective_roles(db: Session, *, user_id: UUID) -> tuple[EffectiveRoleAssignment, ...]:
    assignments = db.scalars(
        select(RoleAssignment).where(
            and_(RoleAssignment.user_id == user_id, RoleAssignment.active.is_(True))
        )
    ).all()

    return tuple(
        EffectiveRoleAssignment(
            role=ROLE_TYPE_TO_APP_ROLE[assignment.role],
            business_unit_id=assignment.business_unit_id,
            assignment_id=assignment.id,
        )
        for assignment in assignments
    )


def get_current_user_context(
    x_ms_oid: str | None = Header(default=None, alias="X-MS-OID"),
    x_ms_email: str | None = Header(default=None, alias="X-MS-EMAIL"),
    x_ms_display_name: str | None = Header(default=None, alias="X-MS-DISPLAY-NAME"),
    db: Session = Depends(get_db_session),
) -> RequestUserContext:
    """Resolve current request user and effective role assignments.

    Header strategy:
    - Current phase: trusted headers from proxy / test clients.
    - Future M365 phase: replace with token validation and claim extraction.
    """

    microsoft_oid, email, display_name = _resolve_identity(x_ms_oid, x_ms_email, x_ms_display_name)
    user = _upsert_user(db, microsoft_oid=microsoft_oid, email=email, display_name=display_name)
    roles = _load_effective_roles(db, user_id=user.id)
    db.commit()

    return RequestUserContext(
        user_id=user.id,
        microsoft_oid=user.microsoft_oid,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        roles=roles,
    )


def has_role(context: RequestUserContext, allowed_roles: set[AppRole]) -> bool:
    """Check whether user has any of the allowed roles."""

    return any(role in allowed_roles for role in context.role_names)


def has_business_unit_access(
    context: RequestUserContext,
    *,
    business_unit_id: UUID,
    allowed_roles: set[AppRole] | None = None,
) -> bool:
    """Check scoped BU access optionally constrained by allowed roles."""

    if context.is_super_admin:
        if allowed_roles is None:
            return True
        return AppRole.SUPER_ADMIN in allowed_roles

    for assignment in context.roles:
        if assignment.business_unit_id != business_unit_id:
            continue
        if allowed_roles is None or assignment.role in allowed_roles:
            return True
    return False


def require_roles(*roles: AppRole):
    """Dependency factory requiring at least one provided role."""

    allowed = set(roles)

    def dependency(context: RequestUserContext = Depends(get_current_user_context)) -> RequestUserContext:
        if not has_role(context, allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions for this operation.",
            )
        return context

    return dependency


def require_business_unit_roles(*roles: AppRole):
    """Dependency factory requiring role within selected business unit scope.

    Business unit id is accepted from either path or query parameter as
    ``business_unit_id``.
    """

    allowed = set(roles)

    def dependency(
        business_unit_id: UUID,
        context: RequestUserContext = Depends(get_current_user_context),
    ) -> RequestUserContext:
        if not has_business_unit_access(
            context,
            business_unit_id=business_unit_id,
            allowed_roles=allowed,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient business unit scope permissions for this operation.",
            )
        return context

    return dependency


def ensure_business_unit_exists(db: Session, business_unit_id: UUID) -> BusinessUnit:
    """Resolve business unit or raise 404."""

    business_unit = db.scalar(select(BusinessUnit).where(BusinessUnit.id == business_unit_id))
    if business_unit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business unit not found.",
        )
    return business_unit
