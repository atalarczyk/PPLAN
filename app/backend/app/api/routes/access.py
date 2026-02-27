"""Access and session context endpoints."""

from fastapi import APIRouter, Depends

from app.core.auth import RequestUserContext, get_current_user_context

router = APIRouter(prefix="/access", tags=["access"])


@router.get("/context")
def get_access_context(context: RequestUserContext = Depends(get_current_user_context)) -> dict[str, object]:
    """Return authenticated session access context."""

    business_units = []
    for business_unit_id in context.business_unit_ids:
        business_units.append(str(business_unit_id))

    return {
        "user": {
            "id": str(context.user_id),
            "email": context.email,
            "display_name": context.display_name,
            "status": context.status,
            "microsoft_oid": context.microsoft_oid,
        },
        "roles": [role.value for role in context.role_names],
        "assignments": [
            {
                "role": assignment.role.value,
                "business_unit_id": str(assignment.business_unit_id)
                if assignment.business_unit_id is not None
                else None,
            }
            for assignment in context.roles
        ],
        "business_units": business_units,
        "has_access": bool(context.roles),
    }

