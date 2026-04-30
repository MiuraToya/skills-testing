# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication

Communicate with the user in **Japanese** (日本語). Code, identifiers, and this file remain in English.

## Purpose of this repo

This is an experimental codebase used to measure the effect of Agent Skills on testing strategy (UT vs. IT comparison). The application itself — a meeting-room reservation API — is a vehicle for that experiment, not the product. There are two parallel test trees that deliberately mirror each other:

- `no-skills-tests/` — tests written without Agent Skills assistance
- `with-sklls-tests/` — tests written with Agent Skills assistance (note the typo `sklls` in the directory name; keep it as-is)

`pytest.ini` declares `testpaths = tests`, which **does not match** either directory. To actually run tests, point pytest at one of the two trees explicitly (see below).

## Tooling

- Python **3.14**, dependencies and execution managed by **uv**.
- `uv sync` installs runtime deps; `uv sync --group test` adds pytest/httpx; `uv sync --group dev` adds ruff.
- Lint: `uv run ruff check` / `uv run ruff format`.

## Common commands

### Run the API locally

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Run with Docker Compose (full stack)

```bash
docker compose up --build      # api + db on :8000 / :3306
```

### Run tests

The test fixture in `no-skills-tests/conftest.py` automatically:
1. Boots the `db-test` MySQL container (compose profile `test`, port **3307**, project name `reservation-api-test`).
2. Waits for readiness, then runs `alembic upgrade head` against the test DB.
3. Truncates all tables (preserving `alembic_version`) after each test.
4. Tears the container down at session end.

So just running pytest is enough — Docker must be available:

```bash
uv sync --group test
uv run pytest no-skills-tests          # or with-sklls-tests
uv run pytest no-skills-tests/path/to/test_x.py::TestClass::test_case
```

`TEST_DATABASE_URL` overrides the default `mysql+pymysql://app:app@127.0.0.1:3307/reservation_db_test`. The conftest sets `DATABASE_URL` to the test DB before importing app modules, so app code that reads settings at import time also points at the test DB.

### Alembic

```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
uv run alembic downgrade -1
```

`alembic/env.py` reads `DATABASE_URL` from the environment first, falling back to `app.config.settings`.

## Architecture

DDD-leaning layered structure. Dependencies flow inward only: `presentation` → `application` → `domain`, and `infrastructure` implements `application` ports against `domain` types. Do not call SQLAlchemy from `application` or `domain`.

```
app/
  domain/           # Entities + invariants only. No I/O, no framework.
  application/      # Use-case services + ports (UnitOfWork, repositories).
  infrastructure/   # SQLAlchemy repositories, UoW, ORM models, session.
  presentation/     # FastAPI routes, request/response schemas, error mapping.
```

### Entity construction pattern

Domain entities (`Reservation`, `Room`) **cannot be instantiated directly** — the constructor requires a private `_internal=True` keyword and raises `ReservationRuleError` otherwise. Always go through:

- `Entity.create(...)` — for new entities (generates IDs/timestamps, sets initial state).
- `Entity.reconstruct(...)` — for rehydrating from persistence (preserves stored state).

Infrastructure repositories must use `reconstruct`. Application services must use `create`. `_validate_invariants()` runs in `__init__`, so both paths are validated.

### Unit of Work

`app.application.ports.UnitOfWork` is the abstract boundary; `SqlAlchemyUnitOfWork` is the impl. Services always do `with self._uow as uow:` and call `uow.commit()` / `uow.rollback()` explicitly. The UoW context manager auto-rollbacks on exception and closes the session, but does **not** auto-commit on success — services must commit deliberately.

`get_uow` (in `presentation/api/dependencies.py`) is the FastAPI dependency. Tests override it via `app.dependency_overrides[get_uow]` in the autouse fixture, swapping in a UoW bound to the test session factory.

### Exception mapping

- `domain.exceptions.ReservationRuleError` — invariant violation in the domain.
- `application.exceptions` — `ValidationError`, `ConflictError`, `NotFoundError`. Services catch `ReservationRuleError` and translate to `ValidationError`; they translate `IntegrityError` into `ConflictError`.
- `presentation/error_handlers.py` maps application exceptions to HTTP responses. Domain exceptions should not leak past the application layer.

### Reservation invariants (enforced in `Reservation._validate_invariants`)

- All datetimes must be timezone-aware.
- `start_at` / `end_at` align to 30-minute slots, seconds/microseconds zero.
- Times fall within business hours **09:00–18:00** in `self.timezone` (default `Asia/Tokyo`).
- Start and end on the same local date.
- `attendee_count` ≤ room capacity (checked via `Room.ensure_capacity_for`).
- Active reservation must not have `canceled_at`; canceled must have it.
- Cancellation only allowed up to **60 minutes** before `start_at`.
- Overlap detection lives on the entity: `reservation.overlaps(start, end)`. The service queries candidates via `reservations.list_by_room_and_range` and filters with `overlaps`.

Datetimes are normalized to UTC inside `Reservation.create`; the original timezone is stored as the `timezone` string for business-hour checks.

## Configuration

`app/config.py` (`pydantic_settings.BaseSettings`) reads `.env`. Recognized vars: `DATABASE_URL`, `TIMEZONE`, `APP_NAME`. `.env.example` documents the defaults.
