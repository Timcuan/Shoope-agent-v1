from pathlib import Path

from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import hmac
import hashlib
import json

from shopee_agent.app.decisions import DecisionEngine
from shopee_agent.app.events import EventIngestService
from shopee_agent.config.settings import get_settings
from shopee_agent.persistence.base import Base
from shopee_agent.persistence.repositories import EventRepository, ShopTokenRepository
from shopee_agent.providers.shopee.client import ShopeeClient
from shopee_agent.providers.shopee.gateway import ShopeeGateway
from shopee_agent.simulator.scenarios import order_created
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

app = FastAPI(title="Shopee Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()

Path("data").mkdir(exist_ok=True)
engine = create_engine("sqlite:///./data/api_dev.db", connect_args={"check_same_thread": False}, future=True)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, future=True)


class SimulatorEventRequest(BaseModel):
    event_type: str
    shop_id: str
    order_sn: str


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Depends(api_key_header)):
    if not settings.api_secret_key:
        # If no key configured, allow access (for backward compatibility/dev)
        return True
    if api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/stats", dependencies=[Depends(verify_api_key)])
def get_stats() -> dict:
    from shopee_agent.persistence.models import EventRecord, DecisionRecord, OutboxRecord, OperatorTaskRecord
    with SessionLocal() as session:
        events = session.scalar(select(func.count(EventRecord.id))) or 0
        decisions_low = session.scalar(select(func.count(DecisionRecord.id)).where(DecisionRecord.risk_tier == "low")) or 0
        decisions_medium = session.scalar(select(func.count(DecisionRecord.id)).where(DecisionRecord.risk_tier == "medium")) or 0
        decisions_high = session.scalar(select(func.count(DecisionRecord.id)).where(DecisionRecord.risk_tier == "high")) or 0
        outbox_pending = session.scalar(select(func.count(OutboxRecord.id)).where(OutboxRecord.status == "pending")) or 0
        tasks_open = session.scalar(select(func.count(OperatorTaskRecord.id)).where(OperatorTaskRecord.status == "open")) or 0
        total_logs = session.scalar(select(func.count(ActivityLogRecord.id))) or 0
        
    return {
        "events": events,
        "decisions": {
            "low": decisions_low,
            "medium": decisions_medium,
            "high": decisions_high
        },
        "queue": outbox_pending,
        "tasks": tasks_open,
        "total_logs": total_logs
    }


@app.get("/api/analytics", dependencies=[Depends(verify_api_key)])
def get_analytics(shop_id: str = None) -> dict:
    from shopee_agent.persistence.repositories import OrderRepository, ReturnDisputeRepository
    from shopee_agent.app.analytics_agent import AnalyticsAgent
    with SessionLocal() as session:
        agent = AnalyticsAgent(OrderRepository(session), ReturnDisputeRepository(session))
        report = agent.get_monthly_dashboard(shop_id)
    return report


@app.get("/api/logs", dependencies=[Depends(verify_api_key)])
def get_logs(shop_id: str = None, limit: int = 10) -> list[dict]:
    from shopee_agent.persistence.models import ActivityLogRecord
    with SessionLocal() as session:
        stmt = select(ActivityLogRecord).order_by(ActivityLogRecord.created_at.desc()).limit(limit)
        if shop_id:
            stmt = stmt.where(ActivityLogRecord.shop_id == shop_id)
        logs = session.scalars(stmt).all()
        return [
            {
                "id": l.id,
                "type": l.activity_type,
                "message": l.message,
                "severity": l.severity,
                "created_at": l.created_at.isoformat()
            } for l in logs
        ]


@app.post("/events/simulator", dependencies=[Depends(verify_api_key)])
def ingest_simulator_event(request: SimulatorEventRequest) -> dict:
    if request.event_type != "order.created":
        return {"created": False, "error": "unsupported_event_type"}
    event = order_created(shop_id=request.shop_id, order_sn=request.order_sn)
    with SessionLocal() as session:
        from shopee_agent.app.workflows import WorkflowEngine
        from shopee_agent.persistence.repositories import DecisionRepository, WorkflowRepository
        from shopee_agent.app.queue import OutboxQueue
        
        service = EventIngestService(
            event_repo=EventRepository(session),
            decision_engine=DecisionEngine(policy_version="policy-v1"),
            decision_repo=DecisionRepository(session),
            workflow_engine=WorkflowEngine(),
            workflow_repo=WorkflowRepository(session),
            outbox_queue=OutboxQueue(session),
        )
        result = service.ingest(event)
    return {
        "event_id": result.event.event_id,
        "created": result.event.created,
        "decision": result.decision.model_dump(mode="json"),
    }


def verify_shopee_signature(url: str, body: bytes, partner_key: str, signature: str) -> bool:
    base_string = f"{url}|{body.decode('utf-8')}"
    expected_sign = hmac.new(
        partner_key.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_sign, signature)


@app.post("/events/webhook")
async def shopee_webhook(request: Request, authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    body = await request.body()
    # The URL needs to be the exact callback URL configured in Shopee Partner Console
    # For now we use the requested URL, but in production it might need to match exactly
    url = str(request.url)
    
    if not verify_shopee_signature(url, body, settings.shopee_partner_key, authorization):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    shop_id = str(payload.get("shop_id", ""))
    code = payload.get("code")
    data = payload.get("data", {})

    # Map Shopee code to internal EventType
    event_type = EventType.SYSTEM_COMMAND
    source_event_id = f"{shop_id}_{code}"
    
    if code == 1: # Order Status Update
        event_type = EventType.ORDER_UPDATED
        source_event_id = str(data.get("ordersn", ""))
    elif code == 2: # Return Update
        event_type = EventType.RETURN_UPDATED
        source_event_id = str(data.get("return_sn", ""))
    elif code == 3: # Order Tracking No
        event_type = EventType.ORDER_UPDATED
        source_event_id = str(data.get("ordersn", ""))
    elif code == 4: # Order Escrow Update (Settlement)
        event_type = EventType.ORDER_ESCROW_UPDATED
        source_event_id = str(data.get("ordersn", ""))
    elif code == 10: # New Chat Message
        event_type = EventType.CHAT_MESSAGE_RECEIVED
        source_event_id = str(data.get("message_id", ""))

    event = EventEnvelope(
        source=EventSource.SHOPEE_WEBHOOK,
        event_type=event_type,
        shop_id=shop_id,
        source_event_id=source_event_id,
        payload=payload,
    )

    def _ingest_event(evt):
        with SessionLocal() as session:
            from shopee_agent.app.workflows import WorkflowEngine
            from shopee_agent.persistence.repositories import DecisionRepository, WorkflowRepository
            from shopee_agent.app.queue import OutboxQueue
            
            service = EventIngestService(
                event_repo=EventRepository(session),
                decision_engine=DecisionEngine(policy_version="policy-v1"),
                decision_repo=DecisionRepository(session),
                workflow_engine=WorkflowEngine(),
                workflow_repo=WorkflowRepository(session),
                outbox_queue=OutboxQueue(session),
            )
            return service.ingest(evt)

    await run_in_threadpool(_ingest_event, event)

    return {"status": "success"}


@app.get("/api/shopee/auth/callback")
async def shopee_auth_callback(code: str, shop_id: str) -> dict:
    if not code or not shop_id:
        return {"status": "error", "message": "Missing code or shop_id"}
    
    with SessionLocal() as session:
        client = ShopeeClient(
            base_url=settings.shopee_base_url,
            partner_id=settings.shopee_partner_id,
            partner_key=settings.shopee_partner_key,
        )
        token_repo = ShopTokenRepository(session)
        gateway = ShopeeGateway(client, token_repo)
        
        try:
            await gateway.get_access_token(code, shop_id)
            return {"status": "success", "message": f"Successfully linked shop {shop_id}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            await client.close()
