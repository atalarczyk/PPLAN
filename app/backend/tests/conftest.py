from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.dependencies import get_db_session
import app.models.entities  # noqa: F401
from app.main import create_app
from app.models.entities import (
    BusinessUnit,
    EffortMonthlyEntry,
    FinancialRequest,
    Invoice,
    Performer,
    PerformerRate,
    Project,
    ProjectMonthlySnapshot,
    ProjectStage,
    Revenue,
    RoleAssignment,
    Task,
    TaskPerformerAssignment,
    User,
)

TEST_TABLES = [
    BusinessUnit.__table__,
    User.__table__,
    RoleAssignment.__table__,
    Project.__table__,
    ProjectStage.__table__,
    Performer.__table__,
    Task.__table__,
    TaskPerformerAssignment.__table__,
    EffortMonthlyEntry.__table__,
    PerformerRate.__table__,
    FinancialRequest.__table__,
    Invoice.__table__,
    Revenue.__table__,
    ProjectMonthlySnapshot.__table__,
]


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine, tables=TEST_TABLES)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=TEST_TABLES)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(
    *,
    oid: str = "oid-super-admin",
    email: str = "super.admin@test.local",
    display_name: str = "Super Admin",
) -> dict[str, str]:
    return {
        "X-MS-OID": oid,
        "X-MS-EMAIL": email,
        "X-MS-DISPLAY-NAME": display_name,
    }
