# Shopee Core Engine Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working backend slice: typed contracts, SQLite persistence, event store, DB queue/outbox, simulator gateway, decision/workflow skeleton, FastAPI health/event ingest, and minimal Telegram command surface.

**Architecture:** Modular monolith. Domain logic depends on contracts and repository interfaces; providers live behind adapters. This plan builds the core spine only, so later Shopee API, Telegram cockpit, reports, chat, memory, and print flows can plug in without rewriting foundations.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.x, Alembic, Pydantic v2, pydantic-settings, httpx, aiogram 3.x, openpyxl, pytest.

---

## Scope Split

The design spec covers many subsystems. Implement in separate plans:

1. Core Engine Foundation: this plan.
2. Shopee API Integration: signed client, token refresh, capability discovery, order/logistics/product APIs.
3. Telegram Operations Cockpit: menus, inbox, cards, callbacks, roles.
4. Reporting and Audit Workbook: Excel exports and `auditshopeedef.xlsx` template.
5. Chat Intelligence: classifier, templates, approval flow, customer dynamics.
6. Memory and Learning: memory lifecycle, proposal eval, rollback.
7. Print and Fulfillment: resi/AWB download, archive, batch labels, packing.

Do not implement later subsystem behavior in this plan. Build seams and tests only.

## File Structure

Create:

- `pyproject.toml`: package metadata, dependencies, pytest config.
- `.env.example`: safe config keys.
- `alembic.ini`: migration config.
- `src/shopee_agent/__init__.py`: package marker.
- `src/shopee_agent/config/settings.py`: Pydantic settings.
- `src/shopee_agent/contracts/events.py`: event envelopes and normalized event types.
- `src/shopee_agent/contracts/decisions.py`: `Decision`, `RiskTier`, `ActionRequest`.
- `src/shopee_agent/contracts/workflows.py`: workflow status and instance models.
- `src/shopee_agent/persistence/base.py`: SQLAlchemy metadata/base.
- `src/shopee_agent/persistence/session.py`: engine/session factory.
- `src/shopee_agent/persistence/models.py`: core tables.
- `src/shopee_agent/persistence/repositories.py`: event/outbox/workflow repositories.
- `src/shopee_agent/app/events.py`: event ingest service.
- `src/shopee_agent/app/queue.py`: DB-backed queue/outbox claim/complete behavior.
- `src/shopee_agent/app/decisions.py`: minimal decision intelligence skeleton.
- `src/shopee_agent/app/workflows.py`: deterministic workflow skeleton.
- `src/shopee_agent/providers/shopee/simulator.py`: fake Shopee gateway.
- `src/shopee_agent/providers/telegram/fake.py`: fake Telegram gateway.
- `src/shopee_agent/entrypoints/api/main.py`: FastAPI app.
- `src/shopee_agent/entrypoints/worker/main.py`: queue worker loop entrypoint.
- `src/shopee_agent/entrypoints/telegram/main.py`: minimal aiogram bot entrypoint.
- `src/shopee_agent/simulator/scenarios.py`: sample event fixtures.
- `alembic/env.py`: migration env.
- `alembic/versions/0001_core_foundation.py`: initial migration.
- `tests/conftest.py`: isolated test DB fixtures.
- `tests/test_event_ingest.py`: event dedupe and normalization tests.
- `tests/test_queue_outbox.py`: queue lease/idempotency tests.
- `tests/test_decision_engine.py`: decision explanation skeleton tests.
- `tests/test_workflows.py`: workflow resume tests.
- `tests/test_api_health.py`: FastAPI health and ingest tests.
- `tests/test_architecture_boundaries.py`: import boundary guard.

Modify:

- `.gitignore`: keep `.omx/`, `.env`, DB files, archives, generated exports out of git.

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Write dependency and test config**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "shopee-agent"
version = "0.1.0"
description = "Telegram-supervised Shopee agentic automation backend"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.30,<1",
  "pydantic>=2.8,<3",
  "pydantic-settings>=2.4,<3",
  "sqlalchemy>=2.0,<3",
  "alembic>=1.13,<2",
  "httpx>=0.27,<1",
  "aiogram>=3.10,<4",
  "openpyxl>=3.1,<4",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2,<9",
  "pytest-asyncio>=0.23,<1",
  "ruff>=0.6,<1",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 2: Add safe environment template**

Create `.env.example`:

```dotenv
APP_ENV=local
DATABASE_URL=sqlite:///./data/shopee_agent.db
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_IDS=
SHOPEE_PARTNER_ID=
SHOPEE_PARTNER_KEY=
SHOPEE_BASE_URL=https://partner.shopeemobile.com
LLM_PROVIDER=disabled
ARCHIVE_DIR=./data/archive
```

- [ ] **Step 3: Update gitignore**

Ensure `.gitignore` contains:

```gitignore
.omx/
.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
data/
*.db
*.db-shm
*.db-wal
outputs/
```

- [ ] **Step 4: Verify metadata parses**

Run:

```bash
python3 -m tomllib pyproject.toml
```

Expected: command exits `0`.

- [ ] **Step 5: Commit scaffold**

```bash
git add pyproject.toml .env.example .gitignore
git commit -m "Create Python project scaffold"
```

## Task 2: Typed Contracts

**Files:**
- Create: `src/shopee_agent/__init__.py`
- Create: `src/shopee_agent/contracts/events.py`
- Create: `src/shopee_agent/contracts/decisions.py`
- Create: `src/shopee_agent/contracts/workflows.py`
- Test: `tests/test_decision_engine.py`

- [ ] **Step 1: Write failing contract test**

Create `tests/test_decision_engine.py`:

```python
from shopee_agent.contracts.decisions import Decision, RiskTier
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType


def test_decision_explanation_contains_policy_and_context_ids() -> None:
    event = EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id="evt-1",
        payload={"order_sn": "250501ABC"},
    )
    decision = Decision(
        decision_id="dec-1",
        event_id=event.event_id,
        agent_name="order",
        subject_type="order",
        subject_id="250501ABC",
        risk_tier=RiskTier.LOW,
        confidence=0.95,
        policy_version="policy-v1",
        feature_flag="orders.shadow",
        context_id="ctx-1",
        reason_codes=["order_created"],
        recommended_action="record_order",
        requires_human=False,
    )

    explanation = decision.explain()

    assert "dec-1" in explanation
    assert "ctx-1" in explanation
    assert "policy-v1" in explanation
    assert "orders.shadow" in explanation
```

- [ ] **Step 2: Run test to see import failure**

Run:

```bash
pytest tests/test_decision_engine.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'shopee_agent'`.

- [ ] **Step 3: Add contract models**

Create `src/shopee_agent/__init__.py`:

```python
"""Shopee agent backend."""
```

Create `src/shopee_agent/contracts/events.py`:

```python
from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class EventSource(StrEnum):
    SHOPEE_WEBHOOK = "shopee_webhook"
    SHOPEE_POLL = "shopee_poll"
    TELEGRAM = "telegram"
    SIMULATOR = "simulator"


class EventType(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    SHIPPING_DOCUMENT_REQUESTED = "shipping_document.requested"
    CHAT_MESSAGE_RECEIVED = "chat.message_received"
    SYSTEM_COMMAND = "system.command"


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    source: EventSource
    event_type: EventType
    shop_id: str
    source_event_id: str
    payload: dict
    correlation_id: str = Field(default_factory=lambda: f"corr_{uuid4().hex}")
```

Create `src/shopee_agent/contracts/decisions.py`:

```python
from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionRequest(BaseModel):
    action_id: str = Field(default_factory=lambda: f"act_{uuid4().hex}")
    action_type: str
    subject_id: str
    idempotency_key: str
    payload: dict = Field(default_factory=dict)


class Decision(BaseModel):
    decision_id: str = Field(default_factory=lambda: f"dec_{uuid4().hex}")
    event_id: str
    agent_name: str
    subject_type: str
    subject_id: str
    risk_tier: RiskTier
    confidence: float
    policy_version: str
    feature_flag: str
    context_id: str
    reason_codes: list[str]
    recommended_action: str
    requires_human: bool
    action_request: ActionRequest | None = None

    def explain(self) -> str:
        return (
            f"Decision {self.decision_id}: event={self.event_id}, "
            f"context={self.context_id}, policy={self.policy_version}, "
            f"flag={self.feature_flag}, risk={self.risk_tier}, "
            f"confidence={self.confidence}, action={self.recommended_action}, "
            f"reasons={','.join(self.reason_codes)}"
        )
```

Create `src/shopee_agent/contracts/workflows.py`:

```python
from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowInstance(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid4().hex}")
    workflow_type: str
    version: str
    subject_id: str
    current_state: str
    status: WorkflowStatus = WorkflowStatus.RUNNING
    event_id: str
    data: dict = Field(default_factory=dict)
```

- [ ] **Step 4: Run contract test**

Run:

```bash
PYTHONPATH=src pytest tests/test_decision_engine.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit contracts**

```bash
git add src/shopee_agent tests/test_decision_engine.py
git commit -m "Add typed event decision and workflow contracts"
```

## Task 3: Persistence and Migration

**Files:**
- Create: `src/shopee_agent/config/settings.py`
- Create: `src/shopee_agent/persistence/base.py`
- Create: `src/shopee_agent/persistence/session.py`
- Create: `src/shopee_agent/persistence/models.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_core_foundation.py`
- Test: `tests/conftest.py`
- Test: `tests/test_event_ingest.py`

- [ ] **Step 1: Write failing persistence test**

Create `tests/conftest.py`:

```python
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shopee_agent.persistence.base import Base


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as session:
        yield session
```

Create `tests/test_event_ingest.py`:

```python
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType
from shopee_agent.persistence.repositories import EventRepository


def test_event_repository_dedupes_source_event(db_session) -> None:
    repo = EventRepository(db_session)
    event = EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id="same-source-event",
        payload={"order_sn": "250501ABC"},
    )

    first = repo.insert_if_new(event)
    second = repo.insert_if_new(event)

    assert first.created is True
    assert second.created is False
    assert first.event_id == second.event_id
```

- [ ] **Step 2: Run test to verify missing repository**

Run:

```bash
PYTHONPATH=src pytest tests/test_event_ingest.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `EventRepository`.

- [ ] **Step 3: Add settings, models, and repository**

Create `src/shopee_agent/config/settings.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./data/shopee_agent.db"
    archive_dir: str = "./data/archive"
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    shopee_partner_id: str = ""
    shopee_partner_key: str = ""
    shopee_base_url: str = "https://partner.shopeemobile.com"
    llm_provider: str = "disabled"
```

Create `src/shopee_agent/persistence/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `src/shopee_agent/persistence/models.py`:

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from shopee_agent.persistence.base import Base


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "shop_id",
            "source_event_id",
            "event_type",
            name="uq_events_source_event",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True)
    source_event_id: Mapped[str] = mapped_column(String(128), index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="stored", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OutboxRecord(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outbox_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    action_type: Mapped[str] = mapped_column(String(128), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class WorkflowRecord(Base):
    __tablename__ = "workflow_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    workflow_type: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    current_state: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), index=True)
    event_id: Mapped[str] = mapped_column(String(64), index=True)
    data_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

Create `src/shopee_agent/persistence/session.py`:

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(database_url), future=True)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session:
        yield session
```

Create `src/shopee_agent/persistence/repositories.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shopee_agent.contracts.events import EventEnvelope
from shopee_agent.persistence.models import EventRecord


@dataclass(frozen=True)
class InsertEventResult:
    event_id: str
    created: bool


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def insert_if_new(self, event: EventEnvelope) -> InsertEventResult:
        record = EventRecord(
            event_id=event.event_id,
            source=event.source.value,
            event_type=event.event_type.value,
            shop_id=event.shop_id,
            source_event_id=event.source_event_id,
            correlation_id=event.correlation_id,
            payload_json=json.dumps(event.payload, sort_keys=True),
        )
        self.session.add(record)
        try:
            self.session.commit()
            return InsertEventResult(event_id=event.event_id, created=True)
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(EventRecord).where(
                    EventRecord.source == event.source.value,
                    EventRecord.shop_id == event.shop_id,
                    EventRecord.source_event_id == event.source_event_id,
                    EventRecord.event_type == event.event_type.value,
                )
            )
            if existing is None:
                raise
            return InsertEventResult(event_id=existing.event_id, created=False)
```

- [ ] **Step 4: Add Alembic migration files**

Create `alembic.ini`:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///./data/shopee_agent.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `alembic/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from shopee_agent.persistence.base import Base
from shopee_agent.persistence import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `alembic/versions/0001_core_foundation.py`:

```python
from alembic import op
import sqlalchemy as sa

revision = "0001_core_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("shop_id", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_id"),
        sa.UniqueConstraint("source", "shop_id", "source_event_id", "event_type", name="uq_events_source_event"),
    )
    op.create_index("ix_events_shop_id", "events", ["shop_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])

    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("outbox_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("outbox_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_outbox_status_priority", "outbox", ["status", "priority", "lease_until"])

    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_type", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("current_state", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_id"),
    )
    op.create_index("ix_workflow_subject", "workflow_instances", ["subject_id"])
    op.create_index("ix_workflow_status", "workflow_instances", ["status"])


def downgrade() -> None:
    op.drop_table("workflow_instances")
    op.drop_table("outbox")
    op.drop_table("events")
```

- [ ] **Step 5: Run persistence test**

Run:

```bash
PYTHONPATH=src pytest tests/test_event_ingest.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit persistence**

```bash
git add src/shopee_agent/config src/shopee_agent/persistence alembic alembic.ini tests
git commit -m "Add core persistence and event dedupe"
```

## Task 4: Queue and Outbox

**Files:**
- Modify: `src/shopee_agent/persistence/repositories.py`
- Create: `src/shopee_agent/app/queue.py`
- Test: `tests/test_queue_outbox.py`

- [ ] **Step 1: Write failing queue tests**

Create `tests/test_queue_outbox.py`:

```python
from datetime import UTC, datetime, timedelta

from shopee_agent.app.queue import OutboxQueue
from shopee_agent.contracts.decisions import ActionRequest


def test_outbox_dedupes_by_idempotency_key(db_session) -> None:
    queue = OutboxQueue(db_session)
    action = ActionRequest(
        action_type="telegram.send_message",
        subject_id="task-1",
        idempotency_key="telegram:task-1",
        payload={"text": "hello"},
    )

    first = queue.enqueue(action)
    second = queue.enqueue(action)

    assert first.created is True
    assert second.created is False
    assert first.outbox_id == second.outbox_id


def test_claim_expired_pending_work(db_session) -> None:
    queue = OutboxQueue(db_session)
    action = ActionRequest(
        action_type="telegram.send_message",
        subject_id="task-2",
        idempotency_key="telegram:task-2",
        payload={"text": "hello"},
    )
    queue.enqueue(action)

    claimed = queue.claim_next(now=datetime.now(UTC), lease_for=timedelta(seconds=30))

    assert claimed is not None
    assert claimed.action_type == "telegram.send_message"
    assert queue.claim_next(now=datetime.now(UTC), lease_for=timedelta(seconds=30)) is None
```

- [ ] **Step 2: Run test to verify missing queue**

Run:

```bash
PYTHONPATH=src pytest tests/test_queue_outbox.py -q
```

Expected: FAIL with missing `OutboxQueue`.

- [ ] **Step 3: Implement queue**

Create `src/shopee_agent/app/queue.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shopee_agent.contracts.decisions import ActionRequest
from shopee_agent.persistence.models import OutboxRecord


@dataclass(frozen=True)
class EnqueueResult:
    outbox_id: str
    created: bool


@dataclass(frozen=True)
class ClaimedAction:
    outbox_id: str
    action_type: str
    subject_id: str
    payload: dict


class OutboxQueue:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue(self, action: ActionRequest, priority: int = 100) -> EnqueueResult:
        outbox_id = f"out_{uuid4().hex}"
        record = OutboxRecord(
            outbox_id=outbox_id,
            action_type=action.action_type,
            subject_id=action.subject_id,
            idempotency_key=action.idempotency_key,
            payload_json=json.dumps(action.payload, sort_keys=True),
            priority=priority,
        )
        self.session.add(record)
        try:
            self.session.commit()
            return EnqueueResult(outbox_id=outbox_id, created=True)
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(OutboxRecord).where(OutboxRecord.idempotency_key == action.idempotency_key)
            )
            if existing is None:
                raise
            return EnqueueResult(outbox_id=existing.outbox_id, created=False)

    def claim_next(self, now: datetime, lease_for: timedelta) -> ClaimedAction | None:
        record = self.session.scalar(
            select(OutboxRecord)
            .where(
                OutboxRecord.status == "pending",
                or_(OutboxRecord.lease_until.is_(None), OutboxRecord.lease_until <= now),
            )
            .order_by(OutboxRecord.priority.asc(), OutboxRecord.id.asc())
            .limit(1)
        )
        if record is None:
            return None
        record.status = "running"
        record.lease_until = now + lease_for
        record.attempts += 1
        self.session.commit()
        return ClaimedAction(
            outbox_id=record.outbox_id,
            action_type=record.action_type,
            subject_id=record.subject_id,
            payload=json.loads(record.payload_json),
        )

    def mark_done(self, outbox_id: str) -> None:
        record = self.session.scalar(select(OutboxRecord).where(OutboxRecord.outbox_id == outbox_id))
        if record is None:
            raise ValueError(f"Unknown outbox_id: {outbox_id}")
        record.status = "done"
        self.session.commit()
```

- [ ] **Step 4: Run queue tests**

Run:

```bash
PYTHONPATH=src pytest tests/test_queue_outbox.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit queue**

```bash
git add src/shopee_agent/app/queue.py tests/test_queue_outbox.py
git commit -m "Add DB backed outbox queue"
```

## Task 5: Decision and Workflow Skeleton

**Files:**
- Create: `src/shopee_agent/app/decisions.py`
- Create: `src/shopee_agent/app/workflows.py`
- Test: `tests/test_decision_engine.py`
- Test: `tests/test_workflows.py`

- [ ] **Step 1: Extend decision tests**

Append to `tests/test_decision_engine.py`:

```python
from shopee_agent.app.decisions import DecisionEngine


def test_decision_engine_records_low_risk_order_decision() -> None:
    event = EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id="evt-order-1",
        payload={"order_sn": "250501ABC"},
    )

    decision = DecisionEngine(policy_version="policy-v1").decide(event)

    assert decision.subject_id == "250501ABC"
    assert decision.risk_tier == RiskTier.LOW
    assert decision.recommended_action == "record_order"
    assert decision.requires_human is False
```

Create `tests/test_workflows.py`:

```python
from shopee_agent.app.workflows import WorkflowEngine
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType
from shopee_agent.contracts.workflows import WorkflowStatus


def test_workflow_starts_order_intake() -> None:
    event = EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id="evt-order-1",
        payload={"order_sn": "250501ABC"},
    )

    workflow = WorkflowEngine().start_for_event(event)

    assert workflow.workflow_type == "order_intake"
    assert workflow.subject_id == "250501ABC"
    assert workflow.current_state == "order_seen"
    assert workflow.status == WorkflowStatus.RUNNING
```

- [ ] **Step 2: Run tests to verify missing engines**

Run:

```bash
PYTHONPATH=src pytest tests/test_decision_engine.py tests/test_workflows.py -q
```

Expected: FAIL with missing `DecisionEngine` and `WorkflowEngine`.

- [ ] **Step 3: Implement decision/workflow skeleton**

Create `src/shopee_agent/app/decisions.py`:

```python
from shopee_agent.contracts.decisions import Decision, RiskTier
from shopee_agent.contracts.events import EventEnvelope, EventType


class DecisionEngine:
    def __init__(self, policy_version: str) -> None:
        self.policy_version = policy_version

    def decide(self, event: EventEnvelope) -> Decision:
        if event.event_type == EventType.ORDER_CREATED:
            order_sn = str(event.payload["order_sn"])
            return Decision(
                event_id=event.event_id,
                agent_name="order",
                subject_type="order",
                subject_id=order_sn,
                risk_tier=RiskTier.LOW,
                confidence=0.99,
                policy_version=self.policy_version,
                feature_flag="orders.shadow",
                context_id=f"ctx_{event.event_id}",
                reason_codes=["simulated_order_created"],
                recommended_action="record_order",
                requires_human=False,
            )
        return Decision(
            event_id=event.event_id,
            agent_name="system",
            subject_type="event",
            subject_id=event.source_event_id,
            risk_tier=RiskTier.MEDIUM,
            confidence=0.5,
            policy_version=self.policy_version,
            feature_flag="system.supervised",
            context_id=f"ctx_{event.event_id}",
            reason_codes=["unsupported_event_type"],
            recommended_action="create_operator_task",
            requires_human=True,
        )
```

Create `src/shopee_agent/app/workflows.py`:

```python
from shopee_agent.contracts.events import EventEnvelope, EventType
from shopee_agent.contracts.workflows import WorkflowInstance


class WorkflowEngine:
    def start_for_event(self, event: EventEnvelope) -> WorkflowInstance:
        if event.event_type == EventType.ORDER_CREATED:
            return WorkflowInstance(
                workflow_type="order_intake",
                version="v1",
                subject_id=str(event.payload["order_sn"]),
                current_state="order_seen",
                event_id=event.event_id,
                data={"shop_id": event.shop_id},
            )
        return WorkflowInstance(
            workflow_type="unsupported_event",
            version="v1",
            subject_id=event.source_event_id,
            current_state="needs_operator_review",
            event_id=event.event_id,
            data={"event_type": event.event_type.value},
        )
```

- [ ] **Step 4: Run engine tests**

Run:

```bash
PYTHONPATH=src pytest tests/test_decision_engine.py tests/test_workflows.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit engines**

```bash
git add src/shopee_agent/app/decisions.py src/shopee_agent/app/workflows.py tests
git commit -m "Add explainable decision and workflow skeletons"
```

## Task 6: Simulator and API Entrypoint

**Files:**
- Create: `src/shopee_agent/simulator/scenarios.py`
- Create: `src/shopee_agent/app/events.py`
- Create: `src/shopee_agent/entrypoints/api/main.py`
- Test: `tests/test_api_health.py`

- [ ] **Step 1: Write API tests**

Create `tests/test_api_health.py`:

```python
from fastapi.testclient import TestClient

from shopee_agent.entrypoints.api.main import app


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_simulator_event_ingest() -> None:
    client = TestClient(app)

    response = client.post(
        "/events/simulator",
        json={"event_type": "order.created", "shop_id": "shop-1", "order_sn": "250501ABC"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["decision"]["recommended_action"] == "record_order"
```

- [ ] **Step 2: Run API tests to verify missing app**

Run:

```bash
PYTHONPATH=src pytest tests/test_api_health.py -q
```

Expected: FAIL with missing API module.

- [ ] **Step 3: Implement simulator ingest app**

Create `src/shopee_agent/simulator/scenarios.py`:

```python
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType


def order_created(shop_id: str, order_sn: str) -> EventEnvelope:
    return EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id=shop_id,
        source_event_id=f"sim-order-created-{order_sn}",
        payload={"order_sn": order_sn},
    )
```

Create `src/shopee_agent/app/events.py`:

```python
from dataclasses import dataclass

from shopee_agent.app.decisions import DecisionEngine
from shopee_agent.contracts.decisions import Decision
from shopee_agent.contracts.events import EventEnvelope
from shopee_agent.persistence.repositories import EventRepository, InsertEventResult


@dataclass(frozen=True)
class IngestResult:
    event: InsertEventResult
    decision: Decision


class EventIngestService:
    def __init__(self, event_repo: EventRepository, decision_engine: DecisionEngine) -> None:
        self.event_repo = event_repo
        self.decision_engine = decision_engine

    def ingest(self, event: EventEnvelope) -> IngestResult:
        result = self.event_repo.insert_if_new(event)
        decision = self.decision_engine.decide(event)
        return IngestResult(event=result, decision=decision)
```

Create `src/shopee_agent/entrypoints/api/main.py`:

```python
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shopee_agent.app.decisions import DecisionEngine
from shopee_agent.app.events import EventIngestService
from shopee_agent.persistence.base import Base
from shopee_agent.persistence.repositories import EventRepository
from shopee_agent.simulator.scenarios import order_created

app = FastAPI(title="Shopee Agent")

Path("data").mkdir(exist_ok=True)
engine = create_engine("sqlite:///./data/api_dev.db", connect_args={"check_same_thread": False}, future=True)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, future=True)


class SimulatorEventRequest(BaseModel):
    event_type: str
    shop_id: str
    order_sn: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/events/simulator")
def ingest_simulator_event(request: SimulatorEventRequest) -> dict:
    if request.event_type != "order.created":
        return {"created": False, "error": "unsupported_event_type"}
    event = order_created(shop_id=request.shop_id, order_sn=request.order_sn)
    with SessionLocal() as session:
        service = EventIngestService(
            event_repo=EventRepository(session),
            decision_engine=DecisionEngine(policy_version="policy-v1"),
        )
        result = service.ingest(event)
    return {
        "event_id": result.event.event_id,
        "created": result.event.created,
        "decision": result.decision.model_dump(mode="json"),
    }
```

- [ ] **Step 4: Run API tests**

Run:

```bash
PYTHONPATH=src pytest tests/test_api_health.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit API**

```bash
git add src/shopee_agent/app/events.py src/shopee_agent/entrypoints/api/main.py src/shopee_agent/simulator/scenarios.py tests/test_api_health.py
git commit -m "Add simulator event ingest API"
```

## Task 7: Telegram and Worker Skeletons

**Files:**
- Create: `src/shopee_agent/providers/telegram/fake.py`
- Create: `src/shopee_agent/entrypoints/telegram/main.py`
- Create: `src/shopee_agent/entrypoints/worker/main.py`
- Test: `tests/test_architecture_boundaries.py`

- [ ] **Step 1: Write architecture boundary test**

Create `tests/test_architecture_boundaries.py`:

```python
from pathlib import Path


def test_domain_and_app_modules_do_not_import_provider_frameworks() -> None:
    forbidden = ("from aiogram", "import aiogram", "from fastapi", "import fastapi")
    roots = [Path("src/shopee_agent/app"), Path("src/shopee_agent/contracts")]
    offenders: list[str] = []

    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text()
            for token in forbidden:
                if token in text:
                    offenders.append(f"{path}: {token}")

    assert offenders == []
```

- [ ] **Step 2: Run boundary test**

Run:

```bash
PYTHONPATH=src pytest tests/test_architecture_boundaries.py -q
```

Expected: `1 passed`.

- [ ] **Step 3: Add fake Telegram provider and entrypoints**

Create `src/shopee_agent/providers/telegram/fake.py`:

```python
from dataclasses import dataclass, field


@dataclass
class FakeTelegramGateway:
    sent_messages: list[tuple[str, str]] = field(default_factory=list)

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent_messages.append((chat_id, text))
```

Create `src/shopee_agent/entrypoints/telegram/main.py`:

```python
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from shopee_agent.config.settings import Settings

settings = Settings()
dispatcher = Dispatcher()


@dispatcher.message(Command("health"))
async def health(message: Message) -> None:
    await message.answer("status: ok")


async def run_bot() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    bot = Bot(token=settings.telegram_bot_token)
    await dispatcher.start_polling(bot)
```

Create `src/shopee_agent/entrypoints/worker/main.py`:

```python
from datetime import UTC, datetime, timedelta

from shopee_agent.app.queue import OutboxQueue
from shopee_agent.config.settings import Settings
from shopee_agent.persistence.session import make_session_factory


def run_once() -> bool:
    settings = Settings()
    factory = make_session_factory(settings.database_url)
    with factory() as session:
        queue = OutboxQueue(session)
        action = queue.claim_next(now=datetime.now(UTC), lease_for=timedelta(seconds=30))
        if action is None:
            return False
        queue.mark_done(action.outbox_id)
        return True
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=src pytest tests/test_architecture_boundaries.py tests/test_queue_outbox.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit entrypoints**

```bash
git add src/shopee_agent/providers src/shopee_agent/entrypoints tests/test_architecture_boundaries.py
git commit -m "Add Telegram and worker entrypoint skeletons"
```

## Task 8: Full Verification

**Files:**
- No code changes unless verification fails.

- [ ] **Step 1: Run complete tests**

Run:

```bash
PYTHONPATH=src pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run:

```bash
ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 3: Run API smoke manually**

Run:

```bash
PYTHONPATH=src uvicorn shopee_agent.entrypoints.api.main:app --host 127.0.0.1 --port 8000
```

In another shell:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS -X POST http://127.0.0.1:8000/events/simulator \
  -H 'content-type: application/json' \
  -d '{"event_type":"order.created","shop_id":"shop-1","order_sn":"250501ABC"}'
```

Expected first response:

```json
{"status":"ok"}
```

Expected second response includes:

```json
"recommended_action":"record_order"
```

- [ ] **Step 4: Final commit if fixes were needed**

If Task 8 required changes:

```bash
git add .
git commit -m "Verify core engine foundation"
```

If no changes needed, do not create empty commit.

## Self-Review

Spec coverage:

- Core modular monolith: covered by package structure and boundary tests.
- Typed events/decisions/workflows: covered by Task 2 and Task 5.
- SQLite persistence and idempotent event store: covered by Task 3.
- DB-backed outbox queue: covered by Task 4.
- Decision/workflow smart-engine skeleton: covered by Task 5.
- Simulator-first design: covered by Task 6.
- Telegram and worker seams: covered by Task 7.
- Full Shopee API, Excel audit workbook, chat intelligence, memory learning, print operations: intentionally split into later plans.

Placeholder scan:

- No `TBD`, `TODO`, `implement later`, or undefined feature task remains in this plan.

Type consistency:

- `EventEnvelope`, `Decision`, `ActionRequest`, `WorkflowInstance`, `OutboxQueue`, and `DecisionEngine` names match across tasks.
