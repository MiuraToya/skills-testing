import os
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "mysql+pymysql://app:app@127.0.0.1:3307/reservation_db_test",
)

# Ensure app settings resolve to test DB when modules are imported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app
from app.presentation.api.dependencies import get_uow

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PROJECT_NAME = "reservation-api-test"
TEST_PROFILE = "test"


def _run_command(command: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(
        command,
        check=True,
        cwd=PROJECT_ROOT,
        env=env if env is not None else os.environ.copy(),
    )


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> None:
    """Start test MySQL container and run migrations once per test session."""
    _run_command(
        [
            "docker",
            "compose",
            "-p",
            COMPOSE_PROJECT_NAME,
            "--profile",
            TEST_PROFILE,
            "up",
            "-d",
            "db-test",
        ]
    )

    max_attempts = 30
    wait_seconds = 1
    for _ in range(max_attempts):
        try:
            engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            break
        except Exception:
            time.sleep(wait_seconds)
    else:
        raise RuntimeError("Test DB did not become ready in 30 seconds.")

    _run_command(
        ["uv", "run", "alembic", "upgrade", "head"],
        env={**os.environ.copy(), "DATABASE_URL": TEST_DATABASE_URL},
    )

    yield

    _run_command(
        [
            "docker",
            "compose",
            "-p",
            COMPOSE_PROJECT_NAME,
            "--profile",
            TEST_PROFILE,
            "down",
            "-v",
        ]
    )


@pytest.fixture(scope="session")
def test_engine(setup_test_db: None) -> Engine:
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def test_session_factory(test_engine: Engine) -> sessionmaker:
    return sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@pytest.fixture(autouse=True)
def override_uow_dependency(test_session_factory: sessionmaker) -> None:
    def _get_test_uow():
        yield SqlAlchemyUnitOfWork(test_session_factory)

    app.dependency_overrides[get_uow] = _get_test_uow
    yield
    app.dependency_overrides.pop(get_uow, None)


@pytest.fixture(scope="function", autouse=True)
def cleanup_db(test_engine: Engine) -> None:
    """Cleanup table data after each test while keeping schema/migration history."""
    yield
    with test_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        tables = [row[0] for row in conn.execute(text("SHOW TABLES"))]
        for table in tables:
            if table != "alembic_version":
                conn.execute(text(f"TRUNCATE TABLE `{table}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def test_session(test_session_factory: sessionmaker):
    session = test_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(override_uow_dependency: None):
    with TestClient(app) as test_client:
        yield test_client
