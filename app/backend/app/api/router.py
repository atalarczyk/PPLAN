"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes.access import router as access_router
from app.api.routes.admin import legacy_router as admin_legacy_router
from app.api.routes.admin import router as admin_router
from app.api.routes.dashboards import router as dashboards_router
from app.api.routes.exports import router as exports_router
from app.api.routes.finance import router as finance_router
from app.api.routes.health import router as health_router
from app.api.routes.me import router as me_router
from app.api.routes.matrix import router as matrix_router
from app.api.routes.projects import router as projects_router
from app.api.routes.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(me_router)
api_router.include_router(access_router)
api_router.include_router(admin_router)
api_router.include_router(admin_legacy_router)
api_router.include_router(projects_router)
api_router.include_router(matrix_router)
api_router.include_router(finance_router)
api_router.include_router(reports_router)
api_router.include_router(exports_router)
api_router.include_router(dashboards_router)

