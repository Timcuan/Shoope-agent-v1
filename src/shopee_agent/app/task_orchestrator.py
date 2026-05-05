import asyncio
import logging
from datetime import datetime, timedelta
from shopee_agent.app.queue import OutboxQueue
from shopee_agent.contracts.notifications import NotificationProvider
from shopee_agent.persistence.repositories import InventoryRepository, OrderRepository
from shopee_agent.persistence.session import SessionLocal

logger = logging.getLogger("shopee_agent.orchestrator")

class TaskOrchestrator:
    """Manages the background worker pool and ensures API rate limits are respected per shop."""
    
    def __init__(self, num_workers: int = 5, rps_per_shop: int = 3, notifier: NotificationProvider | None = None):
        self.num_workers = num_workers
        self.rps_limit = rps_per_shop
        self.notifier = notifier
        self.shop_semaphores = {} # shop_id -> Semaphore
        self.workers = []
        self.watchdog = None
        self.recurring = None
        self._stop_event = asyncio.Event()

    async def start(self):
        """Starts the background workers, health watchdog, and recurring tasks."""
        logger.info(f"Starting TaskOrchestrator with {self.num_workers} workers...")
        self.workers = [asyncio.create_task(self._worker_loop(i)) for i in range(self.num_workers)]
        self.watchdog = asyncio.create_task(self._watchdog_loop())
        self.recurring = asyncio.create_task(self._recurring_tasks_loop())
 
    async def _watchdog_loop(self):
        """Monitors workers and restarts them if they are stuck or dead."""
        while not self._stop_event.is_set():
            await asyncio.sleep(60)
            for i, worker in enumerate(self.workers):
                if worker.done():
                    if worker.exception():
                        logger.error(f"Worker {i} died with error: {worker.exception()}. Restarting...")
                    else:
                        logger.warning(f"Worker {i} finished unexpectedly. Restarting...")
                    self.workers[i] = asyncio.create_task(self._worker_loop(i))

    async def _recurring_tasks_loop(self):
        """Periodically enqueues high-value recurring maintenance tasks."""
        logger.info("Autonomous Health Watchdog started.")
        while not self._stop_event.is_set():
            try:
                with SessionLocal() as session:
                    from shopee_agent.persistence.repositories import ShopTokenRepository
                    from shopee_agent.app.queue import OutboxQueue
                    token_repo = ShopTokenRepository(session)
                    queue = OutboxQueue(session)
                    
                    shops = token_repo.get_all_shops()
                    now = datetime.now()
                    
                    for shop in shops:
                        shop_id = shop.shop_id
                        
                        # 1. Dispute Sync (Every 1h) - HIGHEST PRIORITY
                        queue.enqueue(
                            action_type="SYNC_DISPUTE",
                            subject_id=f"dispute_sync_{shop_id}",
                            payload={"shop_id": shop_id},
                            idempotency_key=f"recurring_dispute_{shop_id}_{now.strftime('%Y%m%d_%H')}",
                            priority=150 # Top Priority
                        )

                        # 2. Inventory & Logistics Health (Every 4h)
                        queue.enqueue(
                            action_type="CHECK_INVENTORY",
                            subject_id=f"bi_{shop_id}",
                            payload={"shop_id": shop_id},
                            idempotency_key=f"recurring_bi_{shop_id}_{now.strftime('%Y%m%d_%H')}",
                            priority=50
                        )
                        queue.enqueue(
                            action_type="CHECK_LOGISTICS_SLA",
                            subject_id=f"sla_{shop_id}",
                            payload={"shop_id": shop_id},
                            idempotency_key=f"recurring_sla_{shop_id}_{now.strftime('%Y%m%d_%H')}",
                            priority=120 # High Priority
                        )
                        
                        # 2. Finance Reconciliation (Every 24h - midnight)
                        if now.hour == 0:
                            queue.enqueue(
                                action_type="RECONCILE_FINANCE",
                                subject_id=f"audit_{shop_id}",
                                payload={"shop_id": shop_id, "month": now.month, "year": now.year},
                                idempotency_key=f"recurring_audit_{shop_id}_{now.strftime('%Y%m%d')}",
                                priority=30
                            )

                        # 3. Token & Review Health (Every 12h)
                        if now.hour in [0, 12]:
                            queue.enqueue(
                                action_type="CHECK_TOKEN_HEALTH",
                                subject_id=f"token_health_{shop_id}",
                                payload={"shop_id": shop_id},
                                idempotency_key=f"recurring_token_{shop_id}_{now.strftime('%Y%m%d_%H')}",
                                priority=100 # High priority
                            )
                            queue.enqueue(
                                action_type="SYNC_REVIEWS",
                                subject_id=f"reviews_{shop_id}",
                                payload={"shop_id": shop_id},
                                idempotency_key=f"recurring_reviews_{shop_id}_{now.strftime('%Y%m%d_%H')}",
                                priority=40
                            )
                            
                    session.commit()
            except Exception as e:
                logger.error(f"Recurring tasks error: {e}")
            
            # Tick every hour to check for hour-based tasks
            await asyncio.sleep(3600)

    async def stop(self):
        """Stops all workers gracefully."""
        self._stop_event.set()
        tasks = self.workers + [self.watchdog, self.recurring]
        await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
        logger.info("TaskOrchestrator stopped.")

    async def run_operational_maintenance(self, shop_id: str):
        """Execute high-value operational tasks for a shop."""
        logger.info(f"--- Starting Operational Maintenance for {shop_id} ---")
        
        # 1. Booster Rotation (Naikkan Produk)
        from shopee_agent.app.booster_agent import BoosterAgent
        booster = BoosterAgent(self.session, self.gateway)
        newly_boosted = await booster.auto_rotate_boosts(shop_id)
        if newly_boosted:
            logger.info(f"[BI] Booster rotated: {len(newly_boosted)} items promoted.")

        # 2. Review Management (Sync & Auto-reply)
        from shopee_agent.app.review_agent import ReviewAgent
        reviewer = ReviewAgent(self.session, self.llm)
        res = await self.gateway.get_review_list(shop_id)
        reviewer.sync_reviews(shop_id, res.get("comment_list", []))
        replied_count = await reviewer.draft_all_pending(shop_id)
        
        # Auto-execute high-rating replies (Safe automation)
        pending_replies = reviewer.get_pending_replies(shop_id)
        for rev in pending_replies:
            if rev.rating_star >= 4: # Safe to auto-reply to good reviews
                await self.gateway.reply_review(shop_id, int(rev.review_id), rev.reply_comment)
                rev.status = "replied"
        self.session.commit()

        # 3. Inventory Health Analysis
        from shopee_agent.app.inventory_health import InventoryHealthAgent
        inventory = InventoryHealthAgent(self.session)
        alerts = inventory.audit_shop_stock(shop_id)
        for alert in alerts:
            if alert.severity == "CRITICAL":
                from shopee_agent.contracts.operations import OperatorTask, TaskCategory, TaskSeverity, TaskStatus
                from uuid import uuid4
                task = OperatorTask(
                    task_id=f"inv_{uuid4().hex[:8]}",
                    category=TaskCategory.INVENTORY,
                    subject_id=alert.item_id,
                    shop_id=shop_id,
                    severity=TaskSeverity.HIGH,
                    title=f"STOK KRITIS: {alert.item_name}",
                    summary=f"Stok tinggal {alert.current_stock}. Estimasi habis dalam {alert.days_left} hari.",
                    status=TaskStatus.OPEN,
                    due_at=datetime.now() + timedelta(hours=12)
                )
                from shopee_agent.app.operations import OperationsSupervisorAgent
                from shopee_agent.persistence.repositories import OperatorTaskRepository
                ops = OperationsSupervisorAgent(OperatorTaskRepository(self.session), session=self.session)
                ops.create_task(task)

        logger.info(f"--- Operational Maintenance Completed for {shop_id} ---")

    async def _get_shop_semaphore(self, shop_id: str) -> asyncio.Semaphore:
        if shop_id not in self.shop_semaphores:
            self.shop_semaphores[shop_id] = asyncio.Semaphore(self.rps_limit)
        return self.shop_semaphores[shop_id]

    async def _worker_loop(self, worker_id: int):
        consecutive_errors = 0
        while not self._stop_event.is_set():
            try:
                with SessionLocal() as session:
                    queue = OutboxQueue(session)
                    action = queue.claim_next(datetime.now(), timedelta(minutes=5))
                    
                    if not action:
                        consecutive_errors = 0 # Reset on healthy empty check
                        await asyncio.sleep(1) 
                        continue
                    
                    # Identify shop from subject_id or payload
                    shop_id = action.payload.get("shop_id", "default")
                    sem = await self._get_shop_semaphore(shop_id)
                    
                    async with sem:
                        logger.info(f"[Worker {worker_id}] Processing {action.action_type} for {action.subject_id} (Shop: {shop_id})")
                        try:
                            success = await asyncio.wait_for(self._dispatch_action(action), timeout=30.0)
                            if success:
                                queue.mark_done(action.outbox_id)
                                session.commit()
                                consecutive_errors = 0
                            else:
                                # Logic for retry count could be added here
                                logger.warning(f"[Worker {worker_id}] Task {action.outbox_id} returned failure.")
                        except asyncio.TimeoutError:
                            logger.error(f"[Worker {worker_id}] Task {action.outbox_id} timed out.")
                        
                    await asyncio.sleep(0.1) 
            except Exception as e:
                consecutive_errors += 1
                backoff = min(60, 2 ** consecutive_errors)
                logger.error(f"[Worker {worker_id}] Global Loop Error: {e}. Backing off {backoff}s...")
                await asyncio.sleep(backoff)

    async def _dispatch_action(self, action) -> bool:
        """Central dispatching point for all outbox tasks."""
        shop_id = action.payload.get("shop_id", "default")
        
        with SessionLocal() as session:
            from shopee_agent.config.settings import get_settings
            settings = get_settings()
            
            if action.action_type == "CHECK_INVENTORY":
                inv_repo = InventoryRepository(session)
                order_repo = OrderRepository(session)
                from shopee_agent.app.bi_agent import BusinessIntelligenceAgent
                bi = BusinessIntelligenceAgent(order_repo, inv_repo)
                snapshot = bi.format_dashboard_text(bi.get_monthly_dashboard(shop_id), shop_id)
                
                if self.notifier and settings.admin_chat_id:
                     await self.notifier.send_message(settings.admin_chat_id, f"💡 **Laporan Proaktif BI**\n\n{snapshot}")
                return True
                
            elif action.action_type == "RECONCILE_FINANCE":
                from shopee_agent.app.gsheets_agent import GSheetsAgent
                from shopee_agent.contracts.reporting import ReportRequest
                from shopee_agent.persistence.repositories import FinanceRepository
                
                fin_repo = FinanceRepository(session)
                transactions = fin_repo.get_audit_transactions(shop_id, action.payload["month"], action.payload["year"])
                
                request = ReportRequest(
                    shop_id=shop_id,
                    month=action.payload["month"],
                    year=action.payload["year"],
                    transactions=transactions,
                    admin_rate=0.04 # Standardized rate
                )
                
                gsheets = GSheetsAgent()
                url = gsheets.sync_audit_report(request)
                
                if self.notifier and settings.admin_chat_id:
                     await self.notifier.send_message(settings.admin_chat_id, f"📅 **Audit Bulanan Otomatis Berhasil**\n\nShop: `{shop_id}`\nLaporan: [Lihat di Google Sheets]({url})")
                return True
                       
            elif action.action_type == "CHECK_LOGISTICS_SLA":
                from shopee_agent.app.logistics_agent import LogisticsAgent
                from shopee_agent.providers.shopee.gateway import ShopeeGateway
                from shopee_agent.persistence.repositories import ShopTokenRepository, LogisticsRepository
                from shopee_agent.providers.shopee.client import ShopeeClient
                
                client = ShopeeClient(settings.shopee_base_url, settings.shopee_partner_id, settings.shopee_partner_key)
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                logistics = LogisticsAgent(gateway, OrderRepository(session), LogisticsRepository(session))
                await logistics.check_sla_health(shop_id)
                await client.close()
                return True
                
            elif action.action_type == "CHECK_TOKEN_HEALTH":
                from shopee_agent.app.health_agent import HealthAgent
                from shopee_agent.persistence.repositories import ShopTokenRepository
                
                health = HealthAgent(ShopTokenRepository(session))
                status = health.get_shop_health(shop_id)
                
                if status["needs_reauth"] and self.notifier and settings.admin_chat_id:
                     await self.notifier.send_message(settings.admin_chat_id, f"🚨 **Token Critical: {shop_id}**\n\nSegera lakukan re-autentikasi.")
                return True
                
            elif action.action_type == "SYNC_DISPUTE":
                from shopee_agent.app.dispute_agent import DisputeAgent
                from shopee_agent.persistence.repositories import ReturnDisputeRepository
                from shopee_agent.app.operations import OperationsSupervisorAgent
                from shopee_agent.providers.shopee.client import ShopeeClient
                from shopee_agent.providers.shopee.gateway import ShopeeGateway
                from shopee_agent.persistence.repositories import ShopTokenRepository
                from shopee_agent.providers.llm.gateway import LLMGateway
                
                # Setup dependencies for DisputeAgent
                client = ShopeeClient(settings.shopee_base_url, settings.shopee_partner_id, settings.shopee_partner_key)
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                supervisor = OperationsSupervisorAgent(session)
                llm = LLMGateway(settings.openai_api_key) if settings.openai_api_key else None
                
                agent = DisputeAgent(gateway, ReturnDisputeRepository(session), supervisor, llm)
                count = await agent.sync_returns(shop_id)
                
                if count > 0 and self.notifier and settings.admin_chat_id:
                    await self.notifier.send_message(settings.admin_chat_id, f"🛡️ **Sinkronisasi Komplain Selesai**\n\nBerhasil memproses `{count}` kasus baru untuk toko `{shop_id}`.")
                
                await client.close()
                return True

            elif action.action_type == "SYNC_REVIEWS":
                from shopee_agent.app.review_agent import ReviewAgent
                from shopee_agent.providers.shopee.gateway import ShopeeGateway
                from shopee_agent.persistence.repositories import ShopTokenRepository
                from shopee_agent.providers.llm.gateway import LLMGateway
                
                client = ShopeeClient(settings.shopee_base_url, settings.shopee_partner_id, settings.shopee_partner_key)
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                
                # Fetch reviews from Shopee
                raw_reviews = await gateway.get_reviews(shop_id)
                
                llm = LLMGateway(settings.gemini_api_key)
                reviews = ReviewAgent(session, llm=llm)
                reviews.sync_reviews(shop_id, raw_reviews)
                await reviews.draft_all_pending(shop_id)
                
                await client.close()
                return True
                
            elif action.action_type == "SYNC_FINANCE":
                from shopee_agent.app.finance_agent import FinanceAgent
                from shopee_agent.persistence.repositories import FinanceLedgerRepository, OrderRepository
                from shopee_agent.app.operations import OperationsSupervisorAgent
                from shopee_agent.providers.shopee.client import ShopeeClient
                from shopee_agent.providers.shopee.gateway import ShopeeGateway
                from shopee_agent.persistence.repositories import ShopTokenRepository
                
                client = ShopeeClient(settings.shopee_base_url, settings.shopee_partner_id, settings.shopee_partner_key)
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                
                order_sn = action.payload["order_sn"]
                escrow_data = await gateway.get_escrow_detail(shop_id, order_sn)
                
                finance = FinanceAgent(FinanceLedgerRepository(session), OperationsSupervisorAgent(session))
                finance.sync_finance(order_sn, shop_id, escrow_data)
                
                await client.close()
                return True
                
        await asyncio.sleep(0.5) 
        return True
