from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.contracts.domain import FinanceLedgerData, OrderData
from shopee_agent.contracts.operations import OperatorTask, TaskSeverity, TaskStatus
from shopee_agent.persistence.repositories import FinanceLedgerRepository, OrderRepository
from shopee_agent.providers.llm.gateway import LLMGateway
from shopee_agent.app.events import EventIngestService
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType

logger = logging.getLogger("shopee_agent.order")


@dataclass
class SyncOrdersResult:
    synced: int
    created: int
    updated: int
    sla_tasks_created: int


class OrderAgent:
    """Syncs orders from a data source and manages their local lifecycle."""

    SLA_WARNING_HOURS = 12  # create P1 task if ship_by_date within this many hours

    def __init__(
        self,
        order_repo: OrderRepository,
        ledger_repo: FinanceLedgerRepository,
        supervisor: OperationsSupervisorAgent,
        event_service: EventIngestService | None = None,
        llm: LLMGateway | None = None,
    ) -> None:
        self.order_repo = order_repo
        self.ledger_repo = ledger_repo
        self.supervisor = supervisor
        self.event_service = event_service
        self.llm = llm

    async def ingest_orders(self, orders: list[dict], shop_id: str) -> SyncOrdersResult:
        """
        Ingest a list of raw order dicts (from gateway or simulator) and
        upsert them into the local database.
        """
        created = 0
        updated = 0
        sla_tasks = 0

        try:
            for raw in orders:
                order_sn = raw.get("order_sn", "")
                status = raw.get("order_status", raw.get("status", "UNKNOWN"))
                total = float(raw.get("total_amount", 0))
                pay_ts = raw.get("pay_time")
                ship_ts = raw.get("ship_by_date")

                pay_time = datetime.fromtimestamp(pay_ts, tz=UTC) if pay_ts else None
                ship_by = datetime.fromtimestamp(ship_ts, tz=UTC) if ship_ts else None

                data = OrderData(
                    order_sn=order_sn,
                    shop_id=shop_id,
                    buyer_id=str(raw.get("buyer_user_id", "")),
                    status=status,
                    total_amount=total,
                    pay_time=pay_time,
                    ship_by_date=ship_by,
                    data_json=json.dumps(raw, default=str),
                )
                
                # Check existence for stats
                existing = self.order_repo.get_order(order_sn, shop_id)
                self.order_repo.upsert_order(data)
                if not existing:
                    created += 1
                    # Emit Event
                    if self.event_service:
                        event = EventEnvelope(
                            source=EventSource.SHOPEE_POLL,
                            event_type=EventType.ORDER_CREATED,
                            shop_id=shop_id,
                            source_event_id=order_sn,
                            payload=raw,
                        )
                        self.event_service.ingest(event)
                else:
                    updated += 1

                # Upsert initial ledger entry (estimated)
                self.ledger_repo.upsert_ledger(FinanceLedgerData(
                    order_sn=order_sn,
                    shop_id=shop_id,
                    estimated_income=total * 0.98,
                ))

                # SLA check with deduplication
                if ship_by and status in ("READY_TO_SHIP", "PROCESSED"):
                    hours_left = (ship_by - datetime.now(UTC)).total_seconds() / 3600
                    
                    # AI Urgency Check
                    note = raw.get("message_to_seller", "")
                    is_urgent = await self._check_urgency(note) if note and self.llm else False
                    
                    if hours_left <= self.SLA_WARNING_HOURS or is_urgent:
                        task_id = f"sla_{order_sn}"
                        if not self.supervisor.task_repo.task_exists(task_id):
                            severity = TaskSeverity.P0 if (hours_left <= 4 or is_urgent) else TaskSeverity.P1
                            title = f"🚀 URGENT: {order_sn}" if is_urgent else f"SLA Risk: {order_sn}"
                            
                            self.supervisor.create_task(OperatorTask(
                                 task_id=task_id,
                                 category="order",
                                 subject_id=order_sn,
                                 shop_id=shop_id,
                                 severity=severity,
                                 title=title,
                                 summary=(
                                     f"━━━━━━━━━━━━━━━━━━━━\n"
                                     f"⏰ **DEADLINE PENGIRIMAN**\n"
                                     f"Sisa Waktu: `{hours_left:.1f} jam`\n"
                                     f"Batas Waktu: `{ship_by.strftime('%Y-%m-%d %H:%M')}`\n"
                                     f"━━━━━━━━━━━━━━━━━━━━\n"
                                     f"💬 **CATATAN PEMBELI**\n"
                                     f"_{note or 'Tidak ada catatan khusus'}_\n"
                                     f"━━━━━━━━━━━━━━━━━━━━\n"
                                     f"🤖 **KEPUTUSAN URGENSI**\n"
                                     f"Status: {'🚨 KRITIS' if is_urgent else '⚠️ PERINGATAN'}\n"
                                     f"Tindakan: **KIRIM SEGERA**"
                                 ),
                                 due_at=ship_by,
                             ))
                            sla_tasks += 1
            
            return SyncOrdersResult(synced=len(orders), created=created, updated=updated, sla_tasks_created=sla_tasks)
        except Exception as e:
            logger.error(f"Ingestion error for {shop_id}: {e}")
            raise

    async def sync_order_finances(self, shop_id: str, order_sn: str, gateway: any) -> None:
        """Fetch accurate escrow/income breakdown from Shopee API."""
        try:
            raw = await gateway.get_escrow_detail(shop_id, order_sn)
            if not raw:
                return

            income_info = raw.get("order_income", {})
            
            escrow_amount = float(income_info.get("escrow_amount", 0))
            commission_fee = float(income_info.get("commission_fee", 0))
            service_fee = float(income_info.get("service_fee", 0))
            shipping_fee = float(income_info.get("actual_shipping_fee", 0))
            
            final_income = float(income_info.get("seller_income", 0))
            settlement_status = "settled" if raw.get("escrow_status") == "COMPLETED" else "pending"

            ledger = FinanceLedgerData(
                order_sn=order_sn,
                shop_id=shop_id,
                escrow_amount=escrow_amount,
                commission_fee=commission_fee,
                service_fee=service_fee,
                shipping_fee=shipping_fee,
                estimated_income=escrow_amount - commission_fee - service_fee,
                final_income=final_income,
                settlement_status=settlement_status,
                data_json=json.dumps(raw, default=str),
            )
            self.ledger_repo.upsert_ledger(ledger)
            logger.info(f"Synced finances for {order_sn}: Income={final_income}")
        except Exception as e:
            logger.warning(f"Could not sync finances for {order_sn}: {e}")

    async def _check_urgency(self, note: str) -> bool:
        """Use LLM to detect if a customer note implies high urgency."""
        if not self.llm or not note:
            return False
        
        prompt = (
            f"Analyze this customer order note: \"{note}\"\n"
            "Does the customer express a strong need for urgent shipping or a time-sensitive request? "
            "Reply only with 'YES' or 'NO'."
        )
        try:
            response = await self.llm.generate_response(prompt)
            return "YES" in response.upper()
        except Exception:
            return False

    async def alert_sla_risk_orders(
        self,
        shop_id: str,
        notify_fn=None,
    ) -> list[str]:
        """
        HUMAN-IN-THE-LOOP SLA Enforcement.
        Scan orders approaching SLA and send a Telegram alert with an 'Approve Ship' button.
        """
        alerted = []
        # Get orders due within 24h
        threshold = datetime.now(UTC) + timedelta(hours=24)
        orders = self.order_repo.get_active_orders(shop_id)
        
        for order in orders:
            if order.ship_by_date and order.ship_by_date <= threshold and order.status in ("READY_TO_SHIP", "PROCESSED"):
                hours_left = (order.ship_by_date - datetime.now(UTC)).total_seconds() / 3600
                severity_icon = "🔴" if hours_left < 6 else "🟡"
                
                if notify_fn:
                    await notify_fn(order.order_sn, shop_id, hours_left, severity_icon)
                
                alerted.append(order.order_sn)
        
        return alerted
