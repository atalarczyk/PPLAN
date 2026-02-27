from __future__ import annotations

import uuid

from app.core.auth import AppRole, EffectiveRoleAssignment, RequestUserContext, has_business_unit_access, has_role


def test_has_role_matches_expected_roles() -> None:
    context = RequestUserContext(
        user_id=uuid.uuid4(),
        microsoft_oid="oid-1",
        email="user@test.local",
        display_name="User",
        status="active",
        roles=(
            EffectiveRoleAssignment(
                role=AppRole.EDITOR,
                business_unit_id=uuid.uuid4(),
                assignment_id=uuid.uuid4(),
            ),
        ),
    )

    assert has_role(context, {AppRole.EDITOR}) is True
    assert has_role(context, {AppRole.VIEWER, AppRole.BUSINESS_UNIT_ADMIN}) is False


def test_has_business_unit_access_for_scoped_role() -> None:
    bu_id = uuid.uuid4()
    context = RequestUserContext(
        user_id=uuid.uuid4(),
        microsoft_oid="oid-2",
        email="scoped@test.local",
        display_name="Scoped",
        status="active",
        roles=(
            EffectiveRoleAssignment(
                role=AppRole.BUSINESS_UNIT_ADMIN,
                business_unit_id=bu_id,
                assignment_id=uuid.uuid4(),
            ),
        ),
    )

    assert has_business_unit_access(context, business_unit_id=bu_id) is True
    assert (
        has_business_unit_access(
            context,
            business_unit_id=bu_id,
            allowed_roles={AppRole.BUSINESS_UNIT_ADMIN},
        )
        is True
    )
    assert (
        has_business_unit_access(
            context,
            business_unit_id=bu_id,
            allowed_roles={AppRole.EDITOR},
        )
        is False
    )


def test_has_business_unit_access_for_super_admin_depends_on_allowed_roles() -> None:
    bu_id = uuid.uuid4()
    context = RequestUserContext(
        user_id=uuid.uuid4(),
        microsoft_oid="oid-3",
        email="super@test.local",
        display_name="Super",
        status="active",
        roles=(
            EffectiveRoleAssignment(
                role=AppRole.SUPER_ADMIN,
                business_unit_id=None,
                assignment_id=uuid.uuid4(),
            ),
        ),
    )

    assert has_business_unit_access(context, business_unit_id=bu_id) is True
    assert (
        has_business_unit_access(
            context,
            business_unit_id=bu_id,
            allowed_roles={AppRole.SUPER_ADMIN},
        )
        is True
    )
    assert (
        has_business_unit_access(
            context,
            business_unit_id=bu_id,
            allowed_roles={AppRole.BUSINESS_UNIT_ADMIN},
        )
        is False
    )

