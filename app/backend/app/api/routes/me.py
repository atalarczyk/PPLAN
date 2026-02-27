"""Current user endpoint."""

from fastapi import APIRouter, Depends

from app.core.auth import RequestUserContext, get_current_user_context

router = APIRouter(prefix="/me", tags=["me"])


def _serialize_assignment(role_name: str, business_unit_id: object) -> dict[str, object]:
    return {
        "role": role_name,
        "business_unit_id": str(business_unit_id) if business_unit_id is not None else None,
    }


@router.get("")
def get_me(context: RequestUserContext = Depends(get_current_user_context)) -> dict[str, object]:
    """Return current authenticated user profile and roles."""

    return {
        "id": str(context.user_id),
        "microsoft_oid": context.microsoft_oid,
        "email": context.email,
        "display_name": context.display_name,
        "status": context.status,
        "roles": [
            _serialize_assignment(assignment.role.value, assignment.business_unit_id)
            for assignment in context.roles
        ],
    }

