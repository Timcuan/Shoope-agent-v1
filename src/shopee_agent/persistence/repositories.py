from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shopee_agent.contracts.events import EventEnvelope
from shopee_agent.contracts.domain import OrderData, LogisticsData, FinanceLedgerData, InventoryItem
from shopee_agent.contracts.knowledge import ProductFact, FAQEntry, ChatMessage
from shopee_agent.contracts.dispute import ReturnData
from shopee_agent.persistence.models import (
    EventRecord, ExportRecord, FinanceLedgerRecord,
    InventoryRecord, LogisticsRecord, OperatorTaskRecord,
    OrderRecord, ShopTokenRecord, ProductKnowledgeRecord,
    ChatSessionRecord, ReturnDisputeRecord, DecisionRecord, WorkflowRecord,
)
from shopee_agent.contracts.decisions import Decision, RiskTier
from shopee_agent.contracts.workflows import WorkflowInstance, WorkflowStatus


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
        try:
            with self.session.begin_nested():
                self.session.add(record)
                self.session.flush()
            return InsertEventResult(event_id=event.event_id, created=True)
        except IntegrityError:
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


@dataclass
class ShopTokenData:
    shop_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime


class ShopTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_token(self, shop_id: str) -> ShopTokenData | None:
        record = self.session.scalar(select(ShopTokenRecord).where(ShopTokenRecord.shop_id == shop_id))
        if not record:
            return None
        return ShopTokenData(
            shop_id=record.shop_id,
            access_token=record.access_token,
            refresh_token=record.refresh_token,
            expires_at=record.expires_at,
        )

    def upsert_token(self, data: ShopTokenData) -> None:
        record = self.session.scalar(select(ShopTokenRecord).where(ShopTokenRecord.shop_id == data.shop_id))
        if record:
            record.access_token = data.access_token
            record.refresh_token = data.refresh_token
            record.expires_at = data.expires_at
        else:
            record = ShopTokenRecord(
                shop_id=data.shop_id,
                access_token=data.access_token,
                refresh_token=data.refresh_token,
                expires_at=data.expires_at,
            )
            self.session.add(record)
        self.session.commit()

    def get_all_tokens(self) -> list[ShopTokenData]:
        records = self.session.scalars(select(ShopTokenRecord)).all()
        return [
            ShopTokenData(
                shop_id=r.shop_id,
                access_token=r.access_token,
                refresh_token=r.refresh_token,
                expires_at=r.expires_at,
            )
            for r in records
        ]


@dataclass
class OperatorTaskData:
    task_id: str
    category: str
    subject_id: str
    shop_id: str
    severity: str
    title: str
    summary: str
    status: str
    due_at: datetime | None = None
    is_notified: bool = False


class OperatorTaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_task(self, data: OperatorTaskData) -> None:
        record = self.session.scalar(select(OperatorTaskRecord).where(OperatorTaskRecord.task_id == data.task_id))
        if record:
            record.status = data.status
            record.title = data.title
            record.summary = data.summary
            record.due_at = data.due_at
        else:
            record = OperatorTaskRecord(
                task_id=data.task_id,
                category=data.category,
                subject_id=data.subject_id,
                shop_id=data.shop_id,
                severity=data.severity,
                title=data.title,
                summary=data.summary,
                status=data.status,
                due_at=data.due_at,
            )
            self.session.add(record)
        self.session.commit()

    def get_task(self, task_id: str) -> OperatorTaskData | None:
        record = self.session.scalar(select(OperatorTaskRecord).where(OperatorTaskRecord.task_id == task_id))
        if not record:
            return None
        return OperatorTaskData(
            task_id=record.task_id,
            category=record.category,
            subject_id=record.subject_id,
            shop_id=record.shop_id,
            severity=record.severity,
            title=record.title,
            summary=record.summary,
            status=record.status,
            due_at=record.due_at,
            is_notified=record.is_notified,
        )

    def task_exists(self, task_id: str) -> bool:
        return self.session.scalar(select(func.count()).select_from(OperatorTaskRecord).where(OperatorTaskRecord.task_id == task_id)) > 0

    def get_open_tasks(self, limit: int = 10, offset: int = 0) -> list[OperatorTaskData]:
        records = self.session.scalars(
            select(OperatorTaskRecord)
            .where(OperatorTaskRecord.status.in_(["open", "waiting", "acknowledged"]))
            .order_by(OperatorTaskRecord.severity.asc(), OperatorTaskRecord.created_at.asc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [
            OperatorTaskData(
                task_id=r.task_id,
                category=r.category,
                subject_id=r.subject_id,
                shop_id=r.shop_id,
                severity=r.severity,
                title=r.title,
                summary=r.summary,
                status=r.status,
                due_at=r.due_at,
                is_notified=r.is_notified,
            )
            for r in records
        ]

    def get_pending_notifications(self) -> list[OperatorTaskData]:
        records = self.session.scalars(
            select(OperatorTaskRecord)
            .where(OperatorTaskRecord.is_notified == False)
            .where(OperatorTaskRecord.status == "open")
            .where(OperatorTaskRecord.severity.in_(["P0", "P1"]))
        ).all()
        return [
            OperatorTaskData(
                task_id=r.task_id, category=r.category, subject_id=r.subject_id,
                shop_id=r.shop_id, severity=r.severity, title=r.title,
                summary=r.summary, status=r.status, due_at=r.due_at, is_notified=r.is_notified
            ) for r in records
        ]

    def mark_notified(self, task_id: str) -> None:
        record = self.session.scalar(select(OperatorTaskRecord).where(OperatorTaskRecord.task_id == task_id))
        if record:
            record.is_notified = True
            self.session.commit()


@dataclass
class ExportLogData:
    export_id: str
    report_type: str
    shop_id: str
    period_start: datetime
    period_end: datetime
    file_path: str
    checksum: str
    creator: str = "system"


class ExportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def log_export(self, data: ExportLogData) -> None:
        record = ExportRecord(
            export_id=data.export_id,
            report_type=data.report_type,
            shop_id=data.shop_id,
            period_start=data.period_start,
            period_end=data.period_end,
            file_path=data.file_path,
            checksum=data.checksum,
            creator=data.creator,
        )
        self.session.add(record)
        self.session.commit()

    def get_recent_exports(self, report_type: str, limit: int = 10) -> list[ExportLogData]:
        records = self.session.scalars(
            select(ExportRecord)
            .where(ExportRecord.report_type == report_type)
            .order_by(ExportRecord.created_at.desc())
            .limit(limit)
        ).all()
        return [
            ExportLogData(
                export_id=r.export_id,
                report_type=r.report_type,
                shop_id=r.shop_id,
                period_start=r.period_start,
                period_end=r.period_end,
                file_path=r.file_path,
                checksum=r.checksum,
                creator=r.creator,
            )
            for r in records
        ]


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_order(self, data: OrderData) -> None:
        record = self.session.scalar(
            select(OrderRecord).where(
                OrderRecord.shop_id == data.shop_id, OrderRecord.order_sn == data.order_sn
            )
        )
        if record:
            record.status = data.status
            record.total_amount = data.total_amount
            record.pay_time = data.pay_time
            record.ship_by_date = data.ship_by_date
            record.data_json = data.data_json
        else:
            record = OrderRecord(
                order_sn=data.order_sn,
                shop_id=data.shop_id,
                buyer_id=data.buyer_id,
                status=data.status,
                total_amount=data.total_amount,
                pay_time=data.pay_time,
                ship_by_date=data.ship_by_date,
                data_json=data.data_json,
            )
            self.session.add(record)
        self.session.commit()

    def get_orders_by_status(self, shop_id: str, status: str, limit: int = 50) -> list[OrderData]:
        records = self.session.scalars(
            select(OrderRecord)
            .where(OrderRecord.shop_id == shop_id, OrderRecord.status == status)
            .order_by(OrderRecord.ship_by_date.asc())
            .limit(limit)
        ).all()
        return [OrderData(
            order_sn=r.order_sn, shop_id=r.shop_id, status=r.status,
            total_amount=r.total_amount, buyer_id=r.buyer_id,
            pay_time=r.pay_time, ship_by_date=r.ship_by_date, data_json=r.data_json,
        ) for r in records]

    def get_item_sales_stats(self, shop_id: str, days: int = 7) -> dict[str, int]:
        """Aggregate item quantities sold by parsing data_json of orders in a period."""
        from datetime import datetime, timedelta, UTC
        since = datetime.now(UTC) - timedelta(days=days)
        orders = self.session.scalars(
            select(OrderRecord).where(
                OrderRecord.shop_id == shop_id,
                OrderRecord.pay_time >= since
            )
        ).all()
        
        stats = {}
        for order in orders:
            try:
                data = json.loads(order.data_json)
                # Shopee v2 get_order_list usually has item_list in detail or basic list
                items = data.get("item_list", [])
                for itm in items:
                    item_id = str(itm.get("item_id", ""))
                    qty = int(itm.get("model_quantity_purchased", itm.get("quantity", 1)))
                    if item_id:
                        stats[item_id] = stats.get(item_id, 0) + qty
            except (json.JSONDecodeError, TypeError):
                continue
        return stats

    def get_pending_orders(self, shop_id: str, limit: int = 50) -> list[OrderData]:
        """Fetch orders that are paid but not yet shipped (Ready to ship)."""
        return self.get_orders_by_status(shop_id, "READY_TO_SHIP", limit)

    def get_order(self, order_sn: str, shop_id: str) -> OrderData | None:
        record = self.session.scalar(
            select(OrderRecord).where(
                OrderRecord.shop_id == shop_id, OrderRecord.order_sn == order_sn
            )
        )
        if not record:
            return None
        return OrderData(
            order_sn=record.order_sn, shop_id=record.shop_id, status=record.status,
            total_amount=record.total_amount, buyer_id=record.buyer_id,
            pay_time=record.pay_time, ship_by_date=record.ship_by_date, data_json=record.data_json,
        )

    def get_revenue_sum(self, shop_id: str | None, start: datetime, end: datetime) -> float:
        from sqlalchemy import func
        stmt = select(func.sum(OrderRecord.total_amount)).where(
            OrderRecord.pay_time >= start,
            OrderRecord.pay_time < end
        )
        if shop_id:
            stmt = stmt.where(OrderRecord.shop_id == shop_id)
        return float(self.session.scalar(stmt) or 0.0)

    def get_order_count(self, shop_id: str | None, start: datetime, end: datetime) -> int:
        from sqlalchemy import func
        stmt = select(func.count(OrderRecord.order_sn)).where(
            OrderRecord.pay_time >= start,
            OrderRecord.pay_time < end
        )
        if shop_id:
            stmt = stmt.where(OrderRecord.shop_id == shop_id)
        return int(self.session.scalar(stmt) or 0)

    def get_shop_performance(self, start: datetime, end: datetime, limit: int = 5) -> list[tuple[str, float]]:
        from sqlalchemy import func
        stmt = select(OrderRecord.shop_id, func.sum(OrderRecord.total_amount)).where(
            OrderRecord.pay_time >= start,
            OrderRecord.pay_time < end
        ).group_by(OrderRecord.shop_id).order_by(func.sum(OrderRecord.total_amount).desc()).limit(limit)
        
        return [(r[0], float(r[1] or 0.0)) for r in self.session.execute(stmt).all()]


class LogisticsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_logistics(self, data: LogisticsData) -> None:
        record = self.session.scalar(
            select(LogisticsRecord).where(LogisticsRecord.order_sn == data.order_sn)
        )
        if record:
            record.tracking_no = data.tracking_no
            record.logistics_channel = data.logistics_channel
            record.ship_status = data.ship_status
            record.label_status = data.label_status
            record.file_path = data.file_path
        else:
            record = LogisticsRecord(
                order_sn=data.order_sn, shop_id=data.shop_id,
                tracking_no=data.tracking_no, logistics_channel=data.logistics_channel,
                ship_status=data.ship_status, label_status=data.label_status,
                file_path=data.file_path,
            )
            self.session.add(record)
        self.session.commit()

    def get_unlabeled(self, shop_id: str) -> list[LogisticsData]:
        records = self.session.scalars(
            select(LogisticsRecord).where(
                LogisticsRecord.shop_id == shop_id,
                LogisticsRecord.label_status == "not_generated",
            )
        ).all()
        return [LogisticsData(
            order_sn=r.order_sn, shop_id=r.shop_id, tracking_no=r.tracking_no,
            logistics_channel=r.logistics_channel, ship_status=r.ship_status,
            label_status=r.label_status, file_path=r.file_path,
        ) for r in records]


class FinanceLedgerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_ledger(self, data: FinanceLedgerData) -> None:
        record = self.session.scalar(
            select(FinanceLedgerRecord).where(FinanceLedgerRecord.order_sn == data.order_sn)
        )
        if record:
            record.escrow_amount = data.escrow_amount
            record.commission_fee = data.commission_fee
            record.service_fee = data.service_fee
            record.shipping_fee = data.shipping_fee
            record.estimated_income = data.estimated_income
            record.final_income = data.final_income
            record.settlement_status = data.settlement_status
            record.data_json = data.data_json
        else:
            record = FinanceLedgerRecord(
                order_sn=data.order_sn,
                shop_id=data.shop_id,
                escrow_amount=data.escrow_amount,
                commission_fee=data.commission_fee,
                service_fee=data.service_fee,
                shipping_fee=data.shipping_fee,
                estimated_income=data.estimated_income,
                final_income=data.final_income,
                settlement_status=data.settlement_status,
                data_json=data.data_json,
            )
            self.session.add(record)
        self.session.commit()

    def get_unsettled_ledger_orders(self, shop_id: str) -> list[str]:
        """Return list of order_sn for orders that are not yet settled."""
        return list(self.session.scalars(
            select(FinanceLedgerRecord.order_sn).where(
                FinanceLedgerRecord.shop_id == shop_id,
                FinanceLedgerRecord.settlement_status == "pending"
            )
        ).all())

    def get_ledger_for_period(self, shop_id: str, year: int, month: int) -> list[tuple[OrderRecord, FinanceLedgerRecord]]:
        """Fetch orders and their corresponding ledger entries for a specific month."""
        from datetime import datetime
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)

        query = select(OrderRecord, FinanceLedgerRecord).join(
            FinanceLedgerRecord, OrderRecord.order_sn == FinanceLedgerRecord.order_sn
        ).where(
            OrderRecord.shop_id == shop_id,
            OrderRecord.pay_time >= start,
            OrderRecord.pay_time < end
        )
        return self.session.execute(query).all()


class InventoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_item(self, item: InventoryItem) -> None:
        record = self.session.scalar(
            select(InventoryRecord).where(
                InventoryRecord.shop_id == item.shop_id,
                InventoryRecord.item_id == item.item_id,
                InventoryRecord.model_id == item.model_id,
            )
        )
        if record:
            record.sku = item.sku
            record.name = item.name
            record.stock = item.stock
            record.reserved_stock = item.reserved_stock
            record.price = item.price
        else:
            record = InventoryRecord(
                shop_id=item.shop_id, item_id=item.item_id, model_id=item.model_id,
                sku=item.sku, name=item.name, stock=item.stock,
                reserved_stock=item.reserved_stock, price=item.price,
            )
            self.session.add(record)
        self.session.commit()

    def get_low_stock(self, shop_id: str, threshold: int = 5) -> list[InventoryItem]:
        records = self.session.scalars(
            select(InventoryRecord).where(
                InventoryRecord.shop_id == shop_id,
                InventoryRecord.stock <= threshold,
            ).order_by(InventoryRecord.stock.asc())
        ).all()
        return [InventoryItem(
            shop_id=r.shop_id, item_id=r.item_id, model_id=r.model_id,
            sku=r.sku, name=r.name, stock=r.stock,
            reserved_stock=r.reserved_stock, price=r.price,
        ) for r in records]


class ProductKnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_pk(self, fact: ProductFact) -> None:
        record = self.session.scalar(
            select(ProductKnowledgeRecord).where(
                ProductKnowledgeRecord.shop_id == fact.shop_id,
                ProductKnowledgeRecord.item_id == fact.item_id,
            )
        )
        faq_json = json.dumps([{"question": f.question, "answer": f.answer} for f in fact.faq])
        aliases_json = json.dumps(fact.aliases)
        variants_json = json.dumps([
            {"model_id": v.model_id, "name": v.name, "price": v.price, "stock": v.stock, "sku": v.sku}
            for v in fact.variants
        ])
        spec_json = json.dumps(fact.spec_json)

        fields = dict(
            name=fact.name,
            category=fact.category,
            price_min=fact.price_min,
            price_max=fact.price_max,
            variants_json=variants_json,
            weight_gram=fact.weight_gram,
            condition=fact.condition,
            description=fact.description,
            spec_json=spec_json,
            selling_points="\n".join(fact.selling_points),
            forbidden_claims="\n".join(fact.forbidden_claims),
            faq_json=faq_json,
            aliases_json=aliases_json,
            freshness_at=func.now(),
        )

        if record:
            for k, v in fields.items():
                setattr(record, k, v)
        else:
            record = ProductKnowledgeRecord(
                item_id=fact.item_id,
                shop_id=fact.shop_id,
                **fields,
            )
            self.session.add(record)
        self.session.commit()

    def get_pk(self, shop_id: str, item_id: str) -> ProductFact | None:
        from shopee_agent.contracts.knowledge import ProductVariant
        record = self.session.scalar(
            select(ProductKnowledgeRecord).where(
                ProductKnowledgeRecord.shop_id == shop_id,
                ProductKnowledgeRecord.item_id == item_id,
            )
        )
        if not record:
            return None

        faq_data = json.loads(record.faq_json)
        faq = [FAQEntry(question=f["question"], answer=f["answer"]) for f in faq_data]
        aliases = json.loads(record.aliases_json)
        variants_data = json.loads(getattr(record, "variants_json", "[]") or "[]")
        variants = [
            ProductVariant(
                model_id=v.get("model_id", ""),
                name=v.get("name", ""),
                price=v.get("price", 0.0),
                stock=v.get("stock", 0),
                sku=v.get("sku", ""),
            )
            for v in variants_data
        ]
        spec_json = json.loads(getattr(record, "spec_json", "{}") or "{}")

        return ProductFact(
            item_id=record.item_id,
            shop_id=record.shop_id,
            name=record.name,
            category=record.category,
            price_min=getattr(record, "price_min", 0.0) or 0.0,
            price_max=getattr(record, "price_max", 0.0) or 0.0,
            variants=variants,
            weight_gram=getattr(record, "weight_gram", 0) or 0,
            condition=getattr(record, "condition", "NEW") or "NEW",
            description=getattr(record, "description", "") or "",
            spec_json=spec_json,
            selling_points=record.selling_points.split("\n") if record.selling_points else [],
            forbidden_claims=record.forbidden_claims.split("\n") if record.forbidden_claims else [],
            faq=faq,
            aliases=aliases,
        )

    def add_faq_to_product(self, shop_id: str, item_id: str, question: str, answer: str) -> bool:
        """Append a new FAQ entry to an existing product knowledge record."""
        record = self.session.scalar(
            select(ProductKnowledgeRecord).where(
                ProductKnowledgeRecord.shop_id == shop_id,
                ProductKnowledgeRecord.item_id == item_id
            )
        )
        if not record:
            return False
            
        faqs = json.loads(record.faq_json or "[]")
        # Check for duplicates
        if any(f["question"].lower() == question.lower() for f in faqs):
            return True # Already exists
            
        faqs.append({"question": question, "answer": answer})
        record.faq_json = json.dumps(faqs)
        self.session.commit()
        return True


class ChatSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_session(
        self, session_id: str, shop_id: str, buyer_id: str | None = None, order_sn: str | None = None
    ) -> ChatSessionRecord:
        record = self.session.scalar(
            select(ChatSessionRecord).where(ChatSessionRecord.session_id == session_id)
        )
        if not record:
            record = ChatSessionRecord(
                session_id=session_id,
                shop_id=shop_id,
                buyer_id=buyer_id,
                order_sn=order_sn,
            )
            self.session.add(record)
            self.session.commit()
        return record

    def get_unresolved_sessions(self, shop_id: str, limit: int = 10) -> list[ChatSessionRecord]:
        """Fetch sessions where the AI couldn't fully resolve the buyer inquiry."""
        return list(self.session.scalars(
            select(ChatSessionRecord)
            .where(
                ChatSessionRecord.shop_id == shop_id,
                ChatSessionRecord.risk_tier.in_(["medium", "high"]),
                ChatSessionRecord.status == "open"
            )
            .order_by(ChatSessionRecord.updated_at.desc())
            .limit(limit)
        ).all())

    def update_session(
        self,
        session_id: str,
        status: str | None = None,
        last_intent: str | None = None,
        risk_tier: str | None = None,
    ) -> None:
        record = self.session.scalar(
            select(ChatSessionRecord).where(ChatSessionRecord.session_id == session_id)
        )
        if record:
            if status:
                record.status = status
            if last_intent:
                record.last_intent = last_intent
            if risk_tier:
                record.risk_tier = risk_tier
            self.session.commit()

    def add_message(self, session_id: str, message: ChatMessage) -> None:
        record = self.session.scalar(
            select(ChatSessionRecord).where(ChatSessionRecord.session_id == session_id)
        )
        if record:
            messages = json.loads(record.messages_json)
            messages.append({
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
            })
            record.messages_json = json.dumps(messages)
            self.session.commit()


class ReturnDisputeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_return(self, data: ReturnData) -> None:
        record = self.session.scalar(
            select(ReturnDisputeRecord).where(ReturnDisputeRecord.return_sn == data.return_sn)
        )
        if record:
            record.status = data.status
            record.amount = data.amount
            record.reason = data.reason
            record.text_reason = data.text_reason
            record.evidence_json = json.dumps(data.evidence_urls)
        else:
            record = ReturnDisputeRecord(
                return_sn=data.return_sn,
                order_sn=data.order_sn,
                shop_id=data.shop_id,
                buyer_id=data.buyer_id,
                reason=data.reason,
                status=data.status,
                amount=data.amount,
                text_reason=data.text_reason,
                evidence_json=json.dumps(data.evidence_urls),
            )
            self.session.add(record)
        self.session.commit()

    def update_analysis(self, return_sn: str, recommendation: str, risk_score: float) -> None:
        record = self.session.scalar(
            select(ReturnDisputeRecord).where(ReturnDisputeRecord.return_sn == return_sn)
        )
        if record:
            record.agent_recommendation = recommendation
            record.risk_score = risk_score
            self.session.commit()

    def get_return(self, return_sn: str) -> ReturnData | None:
        record = self.session.scalar(
            select(ReturnDisputeRecord).where(ReturnDisputeRecord.return_sn == return_sn)
        )
        if not record:
            return None
        return ReturnData(
            return_sn=record.return_sn,
            order_sn=record.order_sn,
            shop_id=record.shop_id,
            buyer_id=record.buyer_id,
            reason=record.reason,
            status=record.status,
            amount=record.amount,
            text_reason=record.text_reason,
            evidence_urls=json.loads(record.evidence_json),
            created_at=record.created_at,
        )

    def get_active_returns(self, shop_id: str) -> list[ReturnData]:
        records = self.session.scalars(
            select(ReturnDisputeRecord).where(
                ReturnDisputeRecord.shop_id == shop_id,
                ReturnDisputeRecord.status.in_(["REQUESTED", "PROCESSING", "SELLER_DISPUTE"])
            )
        ).all()
        return [ReturnData(
            return_sn=r.return_sn,
            order_sn=r.order_sn,
            shop_id=r.shop_id,
            buyer_id=r.buyer_id,
            reason=r.reason,
            status=r.status,
            amount=r.amount,
            text_reason=r.text_reason,
            evidence_urls=json.loads(r.evidence_json),
            created_at=r.created_at,
        ) for r in records]

    def get_dispute_count(self, shop_id: str | None, start: datetime, end: datetime) -> int:
        from sqlalchemy import func
        stmt = select(ReturnDisputeRecord.return_sn).where(
            ReturnDisputeRecord.created_at >= start,
            ReturnDisputeRecord.created_at < end
        )
        if shop_id:
            stmt = stmt.where(ReturnDisputeRecord.shop_id == shop_id)
        # Using count logic
        return len(self.session.scalars(stmt).all())

class ActivityLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def log(self, shop_id: str, activity_type: str, message: str, severity: str = "info") -> None:
        record = ActivityLogRecord(
            shop_id=shop_id,
            activity_type=activity_type,
            message=message,
            severity=severity
        )
        self.session.add(record)
        self.session.commit()

    def get_recent(self, limit: int = 10) -> list[ActivityLogRecord]:
        return list(self.session.scalars(
            select(ActivityLogRecord).order_by(ActivityLogRecord.created_at.desc()).limit(limit)
        ).all())

    def get_for_period(self, shop_id: str, start_dt: datetime, end_dt: datetime) -> list[ActivityLogRecord]:
        return list(self.session.scalars(
            select(ActivityLogRecord).where(
                ActivityLogRecord.shop_id == shop_id,
                ActivityLogRecord.created_at >= start_dt,
                ActivityLogRecord.created_at < end_dt
            ).order_by(ActivityLogRecord.created_at.asc())
        ).all())

    def get_errors(self, limit: int = 10) -> list[ActivityLogRecord]:
        return list(self.session.scalars(
            select(ActivityLogRecord).where(ActivityLogRecord.severity == "error")
            .order_by(ActivityLogRecord.created_at.desc()).limit(limit)
        ).all())


class DecisionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_decision(self, decision: Decision) -> None:
        record = DecisionRecord(
            decision_id=decision.decision_id,
            event_id=decision.event_id,
            agent_name=decision.agent_name,
            subject_type=decision.subject_type,
            subject_id=decision.subject_id,
            risk_tier=decision.risk_tier.value,
            confidence=decision.confidence,
            policy_version=decision.policy_version,
            recommended_action=decision.recommended_action,
            requires_human=decision.requires_human,
            reason_json=json.dumps(decision.reason_codes),
        )
        self.session.add(record)
        self.session.commit()


class WorkflowRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_workflow(self, wf: WorkflowInstance) -> None:
        record = self.session.scalar(
            select(WorkflowRecord).where(WorkflowRecord.workflow_id == wf.workflow_id)
        )
        if record:
            record.current_state = wf.current_state
            record.status = wf.status.value
            record.data_json = json.dumps(wf.data)
        else:
            record = WorkflowRecord(
                workflow_id=wf.workflow_id,
                workflow_type=wf.workflow_type,
                version=wf.version,
                subject_id=wf.subject_id,
                current_state=wf.current_state,
                status=wf.status.value,
                event_id=wf.event_id,
                data_json=json.dumps(wf.data),
            )
            self.session.add(record)
        self.session.commit()
