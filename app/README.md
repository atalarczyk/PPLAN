# PPLAN Cost Planning Platform

Current delivery status for V1 implementation against [`plans/v1-delivery-plan.md`](plans/v1-delivery-plan.md).

## Repository layout

- [`backend/`](backend/) — FastAPI API, domain/services, Alembic migrations, backend tests
- [`frontend/`](frontend/) — React + TypeScript SPA
- [`infra/`](infra/) — deployment-related templates (Apache)
- [`docker-compose.yml`](docker-compose.yml) — local PostgreSQL runtime

## Delivered architecture

- FastAPI app with API prefix and domain routers in [`backend/app/main.py`](backend/app/main.py) and [`backend/app/api/router.py`](backend/app/api/router.py)
- Domain routes implemented for access/admin/projects/matrix/finance/reports/exports/dashboards in [`backend/app/api/routes`](backend/app/api/routes)
- SQLAlchemy model + Alembic schema baseline in [`backend/app/models/entities.py`](backend/app/models/entities.py) and [`backend/alembic/versions/20260226_0001_initial_schema.py`](backend/alembic/versions/20260226_0001_initial_schema.py)
- React route shell and feature pages in [`frontend/src/app/router.tsx`](frontend/src/app/router.tsx) and [`frontend/src/features`](frontend/src/features)

## Feature coverage mapped to delivery plan

| Plan area | Status | Evidence |
| --- | --- | --- |
| Planning & actuals (plan §2 / §12) | Delivered | Matrix read/write + validations in [`backend/app/api/routes/matrix.py`](backend/app/api/routes/matrix.py), [`backend/app/services/planning_service.py`](backend/app/services/planning_service.py), UI in [`frontend/src/features/matrix/MatrixPage.tsx`](frontend/src/features/matrix/MatrixPage.tsx) |
| Finance (plan §2 / §8 / §13) | Delivered | Rates, registers, summary in [`backend/app/api/routes/finance.py`](backend/app/api/routes/finance.py), [`backend/app/services/finance_reporting_service.py`](backend/app/services/finance_reporting_service.py), UI in [`frontend/src/features/finance/FinancePage.tsx`](frontend/src/features/finance/FinancePage.tsx) |
| Reports + exports (plan §2 / §13) | Delivered | Report endpoints in [`backend/app/api/routes/reports.py`](backend/app/api/routes/reports.py), export endpoint in [`backend/app/api/routes/exports.py`](backend/app/api/routes/exports.py), UI in [`frontend/src/features/reports/ReportsPage.tsx`](frontend/src/features/reports/ReportsPage.tsx) |
| Dashboards (plan §2 / §14) | Delivered | Project/BU dashboards in [`backend/app/api/routes/dashboards.py`](backend/app/api/routes/dashboards.py), UI in [`frontend/src/features/dashboard/DashboardPage.tsx`](frontend/src/features/dashboard/DashboardPage.tsx) and [`frontend/src/features/dashboard/BusinessUnitDashboardPage.tsx`](frontend/src/features/dashboard/BusinessUnitDashboardPage.tsx) |
| Access & administration (plan §2 / §5 / §15) | Partially delivered | RBAC, scoped access, admin operations in [`backend/app/core/auth.py`](backend/app/core/auth.py), [`backend/app/api/routes/access.py`](backend/app/api/routes/access.py), [`backend/app/api/routes/admin.py`](backend/app/api/routes/admin.py), admin UI in [`frontend/src/features/admin/AdminPage.tsx`](frontend/src/features/admin/AdminPage.tsx); full Microsoft 365 interactive auth is deferred |
| Hardening/release (plan §16 / §18 / §19) | Partial | Automated backend/frontend unit/integration tests are present; some operational hardening items remain (see limitations below) |

## Backend ↔ frontend contract assumptions (validated)

The frontend API client base URL defaults to `/api/v1` in [`frontend/src/app/api/http.ts`](frontend/src/app/api/http.ts), matching backend API prefix in [`backend/app/core/config.py`](backend/app/core/config.py).

Key route/path assumptions verified in code and tests:

- session/access: `/access/context`, `/me` via [`frontend/src/app/auth/api.ts`](frontend/src/app/auth/api.ts) and [`backend/app/api/routes/access.py`](backend/app/api/routes/access.py), [`backend/app/api/routes/me.py`](backend/app/api/routes/me.py)
- projects/setup: `/business-units/{id}/projects`, `/projects/{id}/...` via [`frontend/src/features/projects/api.ts`](frontend/src/features/projects/api.ts) and [`backend/app/api/routes/projects.py`](backend/app/api/routes/projects.py)
- matrix bulk save: `/projects/{id}/matrix/entries/bulk` (backend also accepts `entries:bulk`) via [`frontend/src/features/matrix/api.ts`](frontend/src/features/matrix/api.ts) and [`backend/app/api/routes/matrix.py`](backend/app/api/routes/matrix.py)
- finance bulk rates + registers: `/projects/{id}/rates/entries/bulk`, `/financial-requests`, `/invoices`, `/revenues` via [`frontend/src/features/finance/api.ts`](frontend/src/features/finance/api.ts) and [`backend/app/api/routes/finance.py`](backend/app/api/routes/finance.py)
- reports/exports/dashboards: `/reports/projects/{id}/...`, `/exports/{report_key}`, `/dashboards/...` via [`frontend/src/features/reports/api.ts`](frontend/src/features/reports/api.ts), [`frontend/src/features/exports/api.ts`](frontend/src/features/exports/api.ts), [`frontend/src/features/dashboard/api.ts`](frontend/src/features/dashboard/api.ts) and matching backend routes

## Setup and run

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker + Docker Compose

### 1) Start PostgreSQL

From repository root:

```bash
docker compose up -d
```

### 2) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Backend config template: [`backend/.env.example`](backend/.env.example).

### 3) Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Frontend config template: [`frontend/.env.example`](frontend/.env.example).

### 4) Local URLs

- SPA: <http://localhost:5173>
- API health: <http://localhost:8000/api/v1/health>

## Test and quality commands

### Backend

```bash
cd backend
source .venv/bin/activate
python -m ruff check .
python -m pytest
```

### Frontend

```bash
cd frontend
npm test
npm run build
```

## Auth model and current limitations

Current auth model is intentionally transitional:

- backend currently supports trusted identity headers + optional development principal fallback in [`backend/app/core/auth.py`](backend/app/core/auth.py) and [`backend/app/core/config.py`](backend/app/core/config.py)
- frontend auth bridge is placeholder-only in [`frontend/src/app/auth/microsoft.ts`](frontend/src/app/auth/microsoft.ts)
- sign-in/callback pages are non-final placeholders in [`frontend/src/app/auth/views.tsx`](frontend/src/app/auth/views.tsx)

This means full Microsoft 365 token-based interactive flow from plan §15 is not yet implemented.

## Known limitations / next steps (mapped to plan)

1. **Microsoft 365 full login flow deferred** (plan §2 Access criterion 1, §15)
   - current state uses dev/header model; replace with real token acquisition/validation.
2. **Audit write coverage not wired end-to-end** (plan §10, §16, §19 Milestone 5)
   - audit table exists in schema/models, but mutation audit pipeline is still pending.
3. **Deprecation cleanup pending** (plan §19 hardening)
   - test runs currently report warnings for `datetime.utcnow()` usage and deprecated `HTTP_422_UNPROCESSABLE_ENTITY` constant.
4. **UI end-to-end browser automation and cross-browser verification not yet present in repo** (plan §18 points 3-4).
5. **Deployment automation / rollback readiness pending** (plan §19 final item).

