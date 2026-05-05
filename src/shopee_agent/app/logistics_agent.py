from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from shopee_agent.contracts.domain import LogisticsData
from shopee_agent.providers.shopee.gateway import ShopeeGateway
from shopee_agent.persistence.repositories import OrderRepository, LogisticsRepository

logger = logging.getLogger("shopee_agent.logistics")


@dataclass
class ShipmentResult:
    order_sn: str
    success: bool
    tracking_no: str | None = None
    error: str | None = None
    label_path: Path | None = None


from shopee_agent.app.print_agent import PrintAgent

class LogisticsAgent:
    def __init__(
        self,
        shopee_gateway: ShopeeGateway,
        order_repo: OrderRepository,
        logistics_repo: LogisticsRepository,
        download_dir: str = "./data/labels",
        print_agent: PrintAgent | None = None,
    ) -> None:
        from shopee_agent.app.instruction_generator import InstructionGenerator
        self.shopee_gateway = shopee_gateway
        self.order_repo = order_repo
        self.logistics_repo = logistics_repo
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.print_agent = print_agent or PrintAgent()
        self.instr_gen = InstructionGenerator()

    async def arrange_shipment(self, shop_id: str, order_sn: str) -> ShipmentResult:
        """
        Ship order, persist resi/tracking number, then auto-download label PDF.
        Returns a ShipmentResult with all details for the HITL confirmation message.
        """
        try:
            res = await self.shopee_gateway.ship_order(shop_id, order_sn)
            tracking_no = res.get("tracking_no") or res.get("tracking_number")

            # Persist logistics record with tracking_no
            self.logistics_repo.upsert_logistics(LogisticsData(
                order_sn=order_sn,
                shop_id=shop_id,
                ship_status="shipped",
                tracking_no=tracking_no,
                label_status="not_generated",
            ))

            # Auto-download label PDF immediately after ship
            label_path = None
            try:
                label_path = await self.get_label_pdf(shop_id, order_sn)
                # Auto-print Label
                await self.print_agent.print_label(label_path)
                
                # --- Worker Instruction ---
                try:
                    order = self.order_repo.get_order(order_sn, shop_id)
                    if order:
                        order_data = json.loads(order.data_json)
                        # Fetch Product Facts for specs
                        from shopee_agent.persistence.repositories import ProductKnowledgeRepository
                        pk_repo = ProductKnowledgeRepository(self.order_repo.session)
                        
                        items = order_data.get("item_list", [])
                        facts = []
                        for itm in items:
                            f = pk_repo.get_pk(shop_id, str(itm.get("item_id", "")))
                            if f: facts.append(f)
                            
                        instr_path = await self.instr_gen.generate_instruction_file(order_data, product_facts=facts)
                        await self.print_agent.print_label(instr_path)
                        logger.info(f"[Logistics] Technical Instruction printed for {order_sn}")
                except Exception as instr_err:
                    logger.warning(f"[Logistics] Instruction print failed: {instr_err}")

                # Mark label as printed/generated
                self.logistics_repo.upsert_logistics(LogisticsData(
                    order_sn=order_sn,
                    shop_id=shop_id,
                    ship_status="shipped",
                    tracking_no=tracking_no,
                    label_status="generated",
                    file_path=str(label_path),
                ))
                logger.info(f"[Logistics] Label saved: {label_path}")
            except Exception as label_err:
                logger.warning(f"[Logistics] Label download failed for {order_sn}: {label_err}")

            return ShipmentResult(
                order_sn=order_sn,
                success=True,
                tracking_no=tracking_no,
                label_path=label_path,
            )

        except Exception as e:
            logger.error(f"[Logistics] ship_order failed for {order_sn}: {e}")
            return ShipmentResult(order_sn=order_sn, success=False, error=str(e))

    async def get_label_pdf(self, shop_id: str, order_sn: str) -> Path:
        """Download and save the PDF label, returning the path."""
        pdf_data = await self.shopee_gateway.download_shipping_document(shop_id, order_sn)
        file_path = self.download_dir / f"label_{order_sn}.pdf"
        file_path.write_bytes(pdf_data)
        return file_path

    async def bulk_print_labels(self, shop_id: str) -> list[ShipmentResult]:
        """
        Find all shipped-but-unlabeled orders and download their labels in bulk.
        Returns list of results for each order.
        """
        unlabeled = self.logistics_repo.get_unlabeled(shop_id)
        results = []
        for record in unlabeled:
            try:
                label_path = await self.get_label_pdf(shop_id, record.order_sn)
                self.logistics_repo.upsert_logistics(LogisticsData(
                    order_sn=record.order_sn,
                    shop_id=shop_id,
                    ship_status=record.ship_status,
                    tracking_no=record.tracking_no,
                    label_status="generated",
                    file_path=str(label_path),
                ))
                results.append(ShipmentResult(
                    order_sn=record.order_sn, success=True,
                    tracking_no=record.tracking_no, label_path=label_path,
                ))
                logger.info(f"[BulkPrint] Label ready: {label_path}")
            except Exception as e:
                results.append(ShipmentResult(order_sn=record.order_sn, success=False, error=str(e)))
                logger.error(f"[BulkPrint] Failed for {record.order_sn}: {e}")
        return results

    async def bulk_ship_and_print(self, shop_id: str) -> list[ShipmentResult]:
        """
        Automate the entire flow for all READY_TO_SHIP orders:
        Arrange Shipment -> Download Label -> Send to Printer.
        """
        orders = self.order_repo.get_active_orders(shop_id)
        rts = [o for o in orders if o.status in ("READY_TO_SHIP", "PROCESSED")]
        
        results = []
        for order in rts:
            res = await self.arrange_shipment(shop_id, order.order_sn)
            results.append(res)
        
        return results

    async def check_sla_health(self, shop_id: str) -> int:
        """
        Monitor near-expiry shipping deadlines (SLA).
        Flags orders with < 12 hours left to ship.
        """
        from shopee_agent.contracts.operations import TaskSeverity, OperatorTask
        from datetime import datetime, timedelta
        
        active_orders = self.order_repo.get_active_orders(shop_id)
        near_expiry = []
        now = datetime.now()
        threshold = now + timedelta(hours=12)
        
        for order in active_orders:
            if order.status in ("READY_TO_SHIP", "PROCESSED", "UNPAID"):
                continue # Only check if it's supposed to be shipped but isn't
            
            # Actually we only care about READY_TO_SHIP orders that haven't been 'arranged'
            if order.status == "READY_TO_SHIP" and order.ship_by_date:
                if order.ship_by_date < threshold:
                    near_expiry.append(order)
                    
        count = 0
        for order in near_expiry:
            time_left = order.ship_by_date - now
            hours_left = time_left.total_seconds() / 3600
            
            task_id = f"sla_{order.order_sn}"
            if not self.order_repo.session.query(OperatorTaskRecord).filter_by(task_id=task_id).first():
                from shopee_agent.app.operations import OperationsSupervisorAgent
                supervisor = OperationsSupervisorAgent(self.order_repo.session)
                supervisor.create_task(OperatorTask(
                    task_id=task_id,
                    category="LOGISTICS",
                    subject_id=order.order_sn,
                    shop_id=shop_id,
                    severity=TaskSeverity.P0 if hours_left < 4 else TaskSeverity.P1,
                    title=f"🚨 DEADLINE PENGIRIMAN: {order.order_sn}",
                    summary=(
                        f"⚠️ **SLA HAMPIR BERAKHIR**\n\n"
                        f"Order ID: `{order.order_sn}`\n"
                        f"Batas Waktu: `{order.ship_by_date.strftime('%d %b %Y %H:%M')}`\n"
                        f"Sisa Waktu: **{hours_left:.1f} jam**\n\n"
                        f"Segera atur pengiriman (Arrange Shipment) untuk menghindari poin penalti Shopee."
                    ),
                    due_at=order.ship_by_date
                ))
                count += 1
        return count
