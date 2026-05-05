from __future__ import annotations

from shopee_agent.contracts.domain import FinanceLedgerData
from shopee_agent.contracts.operations import OperatorTask, TaskSeverity
from shopee_agent.persistence.repositories import FinanceLedgerRepository
from shopee_agent.app.operations import OperationsSupervisorAgent

MISMATCH_THRESHOLD = 500.0  # IDR – flag if actual income differs from estimate by more


class FinanceAgent:
    """Populates the finance ledger and flags settlement mismatches."""

    def __init__(
        self,
        ledger_repo: FinanceLedgerRepository,
        supervisor: OperationsSupervisorAgent,
    ) -> None:
        self.ledger_repo = ledger_repo
        self.supervisor = supervisor

    def sync_finance(self, order_sn: str, shop_id: str, raw: dict) -> None:
        """
        Upsert ledger record from raw finance/escrow data (Shopee v2).
        Flags mismatches between estimated and final income.
        """
        # Shopee v2 nests details under 'order_income'
        income = raw.get("order_income", raw) 
        
        escrow = float(income.get("escrow_amount", 0))
        commission = float(income.get("commission_fee", 0))
        service = float(income.get("service_fee", 0))
        
        # Shipping is often split between seller_absorbed and actual_shipping
        shipping = float(income.get("seller_absorbed_shipping_fee", 0)) + float(income.get("actual_shipping_fee", 0))
        
        # New Standard: Final Income is the actual escrow amount received
        final = float(income.get("escrow_amount", 0))
        estimated = float(income.get("estimated_income", 0))

        data = FinanceLedgerData(
            order_sn=order_sn,
            shop_id=shop_id,
            escrow_amount=escrow,
            commission_fee=commission,
            service_fee=service,
            shipping_fee=shipping,
            estimated_income=estimated,
            final_income=final,
            settlement_status=raw.get("settlement_status", "pending"),
            data_json=json.dumps(income)
        )
        self.ledger_repo.upsert_ledger(data)

        # Shipping Overcharge Detection
        actual_shipping = float(income.get("actual_shipping_fee", 0))
        est_shipping = float(income.get("estimated_shipping_fee", 0))
        
        if actual_shipping > est_shipping + 100: # Small buffer
            overcharge = actual_shipping - est_shipping
            self.supervisor.create_task(OperatorTask(
                task_id=f"fin_ship_over_{order_sn}",
                category="FINANCE",
                subject_id=order_sn,
                shop_id=shop_id,
                severity=TaskSeverity.MEDIUM,
                title=f"📦 Overcharge Ongkir: {order_sn}",
                summary=(
                    f"⚠️ **Selisih Ongkos Kirim Terdeteksi**\n\n"
                    f"Estimasi: `Rp {est_shipping:,.0f}`\n"
                    f"Tagihan Kurir: `Rp {actual_shipping:,.0f}`\n"
                    f"Kelebihan Bayar: **Rp {overcharge:,.0f}**\n\n"
                    f"Kemungkinan besar disebabkan oleh perbedaan berat timbangan atau dimensi paket. "
                    f"Mohon audit SOP packing Anda."
                ),
            ))

        # Mismatch detection (Total Income)
        if estimated > 0 and abs(final - estimated) > MISMATCH_THRESHOLD:
            delta = final - estimated
            self.supervisor.create_task(OperatorTask(
                task_id=f"fin_mismatch_{order_sn}",
                category="FINANCE",
                subject_id=order_sn,
                shop_id=shop_id,
                severity=TaskSeverity.HIGH,
                title=f"🚨 Selisih Dana: {order_sn}",
                summary=(
                    f"⚠️ **Ketidaksesuaian Pembayaran**\n\n"
                    f"Estimasi: `Rp {estimated:,.0f}`\n"
                    f"Diterima: `Rp {final:,.0f}`\n"
                    f"Selisih: **Rp {delta:+,.0f}**\n\n"
                    f"Mohon verifikasi potongan biaya Shopee atau voucher seller yang digunakan."
                ),
            ))

    def get_daily_flash(self, shop_id: str) -> dict:
        """Calculate financial performance for today (since 00:00)."""
        from datetime import datetime, time
        from sqlalchemy import func, select
        from shopee_agent.persistence.models import OrderRecord, FinanceLedgerRecord
        
        today_start = datetime.combine(datetime.now().date(), time.min)
        
        # 1. Total Orders Today
        order_count = self.ledger_repo.session.scalar(
            select(func.count(OrderRecord.id)).where(
                OrderRecord.shop_id == shop_id,
                OrderRecord.pay_time >= today_start
            )
        ) or 0
        
        # 2. Total Revenue & Income Today
        # Joining with Ledger to get accurate figures
        stmt = select(
            func.sum(OrderRecord.total_amount).label("revenue"),
            func.sum(FinanceLedgerRecord.final_income).label("income"),
            func.sum(FinanceLedgerRecord.shipping_fee).label("shipping")
        ).join(
            FinanceLedgerRecord, OrderRecord.order_sn == FinanceLedgerRecord.order_sn
        ).where(
            OrderRecord.shop_id == shop_id,
            OrderRecord.pay_time >= today_start
        )
        
        res = self.ledger_repo.session.execute(stmt).one()
        
        return {
            "order_count": order_count,
            "total_revenue": float(res.revenue or 0),
            "total_income": float(res.income or 0),
            "total_shipping": float(res.shipping or 0),
        }

    def get_performance_report(self, shop_id: str, days: int = 7) -> dict:
        """Deep analysis of profit margins and top performers."""
        from datetime import datetime, timedelta, UTC
        from sqlalchemy import func, select
        from shopee_agent.persistence.models import OrderRecord, FinanceLedgerRecord
        
        since = datetime.now(UTC) - timedelta(days=days)
        
        # 1. Core Metrics
        stmt = select(
            func.sum(OrderRecord.total_amount).label("revenue"),
            func.sum(FinanceLedgerRecord.final_income).label("income"),
            func.count(OrderRecord.id).label("count")
        ).join(
            FinanceLedgerRecord, OrderRecord.order_sn == FinanceLedgerRecord.order_sn
        ).where(
            OrderRecord.shop_id == shop_id,
            OrderRecord.pay_time >= since
        )
        
        res = self.ledger_repo.session.execute(stmt).one()
        rev = float(res.revenue or 0)
        inc = float(res.income or 0)
        
        margin = (inc / rev * 100) if rev > 0 else 0
        
        # 2. Top Items (using OrderRepository logic simplified here)
        # In a real app, we'd query the item sales stats
        from shopee_agent.persistence.repositories import OrderRepository
        order_repo = OrderRepository(self.ledger_repo.session)
        item_stats = order_repo.get_item_sales_stats(shop_id, days=days)
        
        # Sort items by quantity
        sorted_items = sorted(item_stats.items(), key=lambda x: x[1], reverse=True)
        top_items = []
        for iid, qty in sorted_items[:3]:
            # Try to get name from KB
            from shopee_agent.persistence.repositories import ProductKnowledgeRepository
            pk_repo = ProductKnowledgeRepository(self.ledger_repo.session)
            pk = pk_repo.get_pk(shop_id, iid)
            top_items.append({
                "item_id": iid,
                "name": pk.name if pk else f"Item {iid}",
                "qty": qty
            })
            
        return {
            "period_days": days,
            "total_revenue": rev,
            "total_income": inc,
            "order_count": int(res.count or 0),
            "profit_margin": round(margin, 2),
            "top_items": top_items,
            "avg_order_value": rev / res.count if res.count and res.count > 0 else 0
        }
