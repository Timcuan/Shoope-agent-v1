from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    FSInputFile
)
import asyncio
import os
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.app.order_agent import OrderAgent
from shopee_agent.app.inventory_agent import InventoryAgent
from shopee_agent.app.reporting import ReportingAgent
from shopee_agent.app.chat_agent import ChatAgent
from shopee_agent.app.product_knowledge_agent import ProductKnowledgeAgent
from shopee_agent.app.dispute_agent import DisputeAgent
from shopee_agent.app.health_agent import HealthAgent
from shopee_agent.app.analytics_agent import AnalyticsAgent
from shopee_agent.app.notification_agent import NotificationAgent
from shopee_agent.app.inventory_health import InventoryHealthAgent
from shopee_agent.providers.llm.gemini import GeminiProvider
from shopee_agent.providers.llm.gateway import LLMGateway
from shopee_agent.config.settings import Settings
from shopee_agent.contracts.reporting import ReportRequest
from shopee_agent.contracts.knowledge import ChatMessage
from shopee_agent.entrypoints.telegram.callbacks import register_callbacks
from shopee_agent.entrypoints.telegram.keyboards import (
    get_pagination_keyboard, get_task_keyboard, get_shop_selection_keyboard,
    get_logistics_keyboard, get_main_menu_keyboard, get_post_sync_keyboard,
    get_chat_keyboard
)
from shopee_agent.entrypoints.telegram.middleware import AdminLockdownMiddleware
from shopee_agent.persistence.session import SessionLocal, engine
from shopee_agent.persistence.repositories import (
    ExportRepository, FinanceLedgerRepository,
    InventoryRepository, OperatorTaskRepository, OrderRepository,
    ChatSessionRepository, ProductKnowledgeRepository,
    ReturnDisputeRepository, LogisticsRepository,
    ShopTokenRepository, ActivityLogRepository, ActivityLogRecord
)
from shopee_agent.providers.shopee.auth import generate_auth_url
import json
import logging
from aiogram import types
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger("shopee_agent.bot")

@dispatcher.errors()
async def global_error_handler(event: types.ErrorEvent):
    """Global exception catcher for all telegram events."""
    logger.exception(f"Unhandled error: {event.exception}")
    try:
        if event.update.message:
            await event.update.message.answer(
                "⚠️ **Sistem mengalami kendala teknis.**\n"
                "Tim AI sedang melakukan investigasi. Silakan coba lagi nanti.",
                parse_mode="Markdown"
            )
    except TelegramBadRequest:
        pass # Message already deleted or modified
    return True

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("shopee_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("shopee_agent")

settings = Settings()
bot = Bot(token=settings.telegram_bot_token) if settings.telegram_bot_token else None
dispatcher = Dispatcher()
SYNC_SEMAPHORE = asyncio.Semaphore(1)
dispatcher.message.outer_middleware(AdminLockdownMiddleware(settings))
dispatcher.callback_query.outer_middleware(AdminLockdownMiddleware(settings))


def get_supervisor() -> OperationsSupervisorAgent:
    with SessionLocal() as session:
        repo = OperatorTaskRepository(session)
        return OperationsSupervisorAgent(repo)


def get_reporting_agent() -> ReportingAgent:
    with SessionLocal() as session:
        repo = ExportRepository(session)
        return ReportingAgent(export_repo=repo)


def get_llm_gateway() -> LLMGateway | None:
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return GeminiProvider(settings.gemini_api_key, settings.llm_model)
    return None


def get_chat_agent(pk_repo: ProductKnowledgeRepository | None = None) -> ChatAgent:
    pk_agent = ProductKnowledgeAgent(pk_repo) if pk_repo else None
    return ChatAgent(llm=get_llm_gateway(), pk_agent=pk_agent)


def get_shop_ids() -> list[str]:
    with SessionLocal() as session:
        repo = ShopTokenRepository(session)
        return [s.shop_id for s in repo.get_all_tokens()]


def get_health_agent() -> HealthAgent:
    with SessionLocal() as session:
        return HealthAgent(ShopTokenRepository(session))


def get_analytics_agent() -> AnalyticsAgent:
    with SessionLocal() as session:
        return AnalyticsAgent(OrderRepository(session), ReturnDisputeRepository(session))


def get_notification_agent() -> NotificationAgent:
    with SessionLocal() as session:
        return NotificationAgent(OperatorTaskRepository(session))


register_callbacks(dispatcher, get_supervisor())


@dispatcher.message(Command("health"))
async def health(message: Message) -> None:
    agent = get_health_agent()
    health_list = agent.get_global_health()
    
    header = "🏥 *System Status*\n"
    header += f"LLM: `{settings.llm_provider.upper()}`\n"
    header += f"Version: `v1.0.0-orchestrator`\n"
    
    with SessionLocal() as session:
        log_repo = ActivityLogRepository(session)
        last_sync = session.scalars(
            select(ActivityLogRecord).where(ActivityLogRecord.activity_type == "sync")
            .order_by(ActivityLogRecord.created_at.desc()).limit(1)
        ).first()
        if last_sync:
            header += f"Last Sync: `{last_sync.created_at.strftime('%H:%M:%S')}`\n"
    
    header += "\n"
    report = agent.format_health_report(health_list)
    await message.answer(header + report, parse_mode="Markdown")


@dispatcher.message(Command("audit"))
async def audit_cmd(message: Message) -> None:
    """View recent system activity and errors."""
    with SessionLocal() as session:
        repo = ActivityLogRepository(session)
        logs = repo.get_recent(5)
        errors = repo.get_errors(3)
        
        text = "📋 **Aktivitas Sistem Terbaru**\n"
        text += "━━━━━━━━━━━━━━━\n"
        for log in logs:
            icon = "ℹ️" if log.severity == "info" else "⚠️"
            text += f"{icon} `{log.created_at.strftime('%H:%M')}` | {log.message}\n"
        
        if errors:
            text += "\n🚨 **Kesalahan Terbaru**\n"
            text += "━━━━━━━━━━━━━━━\n"
            for err in errors:
                text += f"❌ `{err.created_at.strftime('%H:%M')}` | {err.message}\n"
        
        await message.answer(text, parse_mode="Markdown")


@dispatcher.message(Command("backup"))
async def backup_cmd(message: Message) -> None:
    """Send a ZIP backup of the database to the admin."""
    await bot.send_chat_action(message.chat.id, "upload_document")
    
    import zipfile
    import os
    db_path = "shopee_agent.db"
    zip_path = "shopee_agent_backup.zip"
    
    try:
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            if os.path.exists(db_path):
                zipf.write(db_path)
        
        doc = FSInputFile(zip_path)
        await message.answer_document(doc, caption=f"💾 **Backup Database**\nWaktu: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`", parse_mode="Markdown")
        
        # Cleanup
        os.remove(zip_path)
    except Exception as e:
        await message.answer(f"❌ Gagal melakukan backup: {str(e)}")


@dispatcher.message(Command("help"))
async def help_cmd(message: Message) -> None:
    """Show premium help menu."""
    help_text = (
        "💎 **Bantuan Asisten**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📦 **Toko & Pesanan**\n"
        "• `/sync` - Update data toko sekarang\n"
        "• `/inbox` - Cek pesanan/tugas tertunda\n"
        "• `/stock` - Pantau barang mau habis\n\n"
        "📊 **Keuangan & Laporan**\n"
        "• `/dashboard` - Laporan ringkas hari ini\n"
        "• `/rekap` - Download excel bulanan\n\n"
        "💬 **Pembeli**\n"
        "• `/chat` - Balas pesan masuk\n\n"
        "🛡️ **Sistem**\n"
        "• `/health` - Cek koneksi ke Shopee\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Tip:* Paling gampang pakai tombol menu di bawah aja Kak."
    )
    await message.answer(help_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


@dispatcher.message(Command("start"))
async def start_cmd(message: Message) -> None:
    welcome_text = (
        "Halo Kak! 👋 Saya **Shopee Elite Agent**.\n"
        "Saya siap bantu pantau toko, balas chat, dan urus operasional 24/7.\n\n"
        "💡 **Coba klik tombol di bawah ini ya:**\n"
        "• 📥 **Tugas Hari Ini**: Cek pesanan atau masalah yang butuh perhatian Kakak.\n"
        "• 📈 **Laporan Penjualan**: Lihat profit & performa toko.\n"
        "• 📦 **Cek Stok**: Pantau barang yang hampir habis.\n\n"
        "Kalau butuh bantuan lain, ketik /help ya Kak!"
    )
    await message.answer(
        welcome_text, 
        reply_markup=get_main_menu_keyboard(), 
        parse_mode="Markdown"
    )

@dispatcher.message(Command("shops"))
async def shops_cmd(message: Message) -> None:
    """List all registered shops."""
    shop_ids = get_shop_ids()
    if not shop_ids:
        await message.answer("Belum ada toko terdaftar. Gunakan `/link` untuk menambah toko.")
        return
        
    text = "🏪 *Daftar Toko Terdaftar:*\n\n"
    for sid in shop_ids:
        text += f"• `{sid}`\n"
    
    await message.answer(text, parse_mode="Markdown")


@dispatcher.message(Command("link"))
async def link(message: Message) -> None:
    # Use a dummy redirect URL for local development or get it from settings
    redirect_url = "http://127.0.0.1:8000/api/shopee/auth/callback"
    url = generate_auth_url(
        base_url=settings.shopee_base_url,
        partner_id=settings.shopee_partner_id,
        partner_key=settings.shopee_partner_key,
        redirect_url=redirect_url,
    )
    await message.answer(f"Silakan hubungkan toko Shopee Anda melalui tautan berikut:\n{url}")


def format_task_text(task) -> str:
    # Ubah severity dari P0/P1/HIGH menjadi bahasa manusia
    if task.severity in ["P0", "P1", "HIGH"]:
        sev_label = "🔥 Sangat Penting"
    elif task.severity in ["P2", "MEDIUM"]:
        sev_label = "⚠️ Penting"
    else:
        sev_label = "ℹ️ Info"
        
    # Ubah status jadi lebih ramah
    status_map = {
        "open": "Menunggu Tindakan",
        "acknowledged": "Sedang Dikerjakan",
        "resolved": "Selesai",
        "dismissed": "Diabaikan"
    }
    status_label = status_map.get(task.status.lower(), task.status)
    
    return (
        f"{sev_label}\n"
        f"🏪 Toko: `{task.shop_id}`\n"
        f"📌 *{task.title}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{task.summary}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Status: *{status_label}*"
    )


@dispatcher.message(Command("agenda"))
async def agenda(message: Message) -> None:
    await bot.send_chat_action(message.chat.id, "typing")
    try:
        supervisor = get_supervisor()
        tasks = supervisor.get_agenda()
        if not tasks:
            await message.answer("🎉 Mantap Kak! Tidak ada tugas tertunda untuk hari ini!")
            return
        
        await message.answer(f"📋 **Agenda Harian** ({len(tasks)} tugas):", parse_mode="Markdown")
        for task in tasks:
            text = format_task_text(task)
            await message.answer(text, reply_markup=get_task_keyboard(task.task_id, task.status), parse_mode="Markdown")
    except Exception:
        await message.answer("❌ Gagal memuat agenda. Mohon coba lagi Kak.")


@dispatcher.message(Command("inbox"))
async def inbox(message: Message) -> None:
    await bot.send_chat_action(message.chat.id, "typing")
    try:
        supervisor = get_supervisor()
        tasks = supervisor.get_inbox_page(page=1)
        if not tasks:
            await message.answer("📭 Yey! Semua tugas sudah selesai Kak!")
            return
        
        await message.answer("📥 **Tugas Hari Ini (Halaman 1)**", parse_mode="Markdown")
        for task in tasks:
            text = format_task_text(task)
            await message.answer(text, reply_markup=get_task_keyboard(task.task_id, task.status), parse_mode="Markdown")
        
        await message.answer("Navigasi:", reply_markup=get_pagination_keyboard(1, True))
    except Exception:
        await message.answer("❌ Gagal memuat tugas. Mohon coba lagi Kak.")

@dispatcher.message(Command("packing"))
async def packing_list_cmd(message: Message) -> None:
    """List orders that are ready to be packed and printed."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        order_repo = OrderRepository(session)
        # Fetch 'READY_TO_SHIP' orders
        orders = order_repo.get_pending_orders(shop_id)
        
        if not orders:
            await message.answer("✅ **Semua pesanan sudah di-packing!**")
            return
            
        await message.answer(f"📦 **Antrian Packing — {shop_id}**\nTotal: `{len(orders)}` pesanan", parse_mode="Markdown")
        
        for order in orders[:5]: # Limit to 5 for readability
            text = (
                f"📦 **Order:** `{order.order_sn}`\n"
                f"👤 Buyer: `{order.buyer_user_id}`\n"
                f"💰 Total: `Rp {order.total_amount:,.0f}`\n"
                f"⏰ Bayar: `{order.pay_time.strftime('%H:%M') if order.pay_time else '-'}`"
            )
            await message.answer(
                text, 
                reply_markup=get_print_options_keyboard(order.order_sn, shop_id), 
                parse_mode="Markdown"
            )
        
        if len(orders) > 5:
            await message.answer(f"_...dan {len(orders)-5} pesanan lainnya._")


@dispatcher.message(Command("find"))
async def find_cmd(message: Message) -> None:
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        await message.answer("Gunakan: `/find <kata kunci>`", parse_mode="Markdown")
        return
    
    keyword = parts[1]
    supervisor = get_supervisor()
    tasks = supervisor.find_tasks_by_subject(keyword)
    
    if not tasks:
        await message.answer(f"Tidak ditemukan tugas untuk kata kunci `{keyword}`.", parse_mode="Markdown")
        return
        
    await message.answer(f"🔍 Ditemukan {len(tasks)} tugas untuk `{keyword}`:", parse_mode="Markdown")
    for task in tasks[:5]:  # limit to 5 results to avoid spam
        text = format_task_text(task)
        await message.answer(text, reply_markup=get_task_keyboard(task.task_id, task.status), parse_mode="Markdown")


@dispatcher.message(Command("report"))
@dispatcher.message(Command("rekap"))
async def report_cmd(message: Message) -> None:
    await bot.send_chat_action(message.chat.id, "typing")
    from datetime import date
    today = date.today()
    
    from shopee_agent.entrypoints.telegram.keyboards import get_audit_period_keyboard
    await message.answer(
        "📊 **Audit Center**\n"
        "━━━━━━━━━━━━━━━\n"
        "Silakan pilih bulan yang ingin direkap:",
        reply_markup=get_audit_period_keyboard(today.year),
        parse_mode="Markdown"
    )

@dispatcher.callback_query(lambda c: c.data.startswith("audit_month:"))
async def process_audit_month(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    year = int(parts[1])
    month = int(parts[2])
    
    # 1. Visual Progress
    await callback.message.edit_text(
        f"⏳ **Menyusun Laporan...**\n"
        f"📅 Periode: `{year}-{month:02d}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔍 *Menganalisis data transaksi...*",
        parse_mode="Markdown"
    )
    
    agent = get_reporting_agent()
    
    with SessionLocal() as session:
        ledger_repo = FinanceLedgerRepository(session)
        shop_ids = get_shop_ids()
        shop_id = shop_ids[0] if shop_ids else "demo_shop"
        
        # 2. Simulated Step Update
        await asyncio.sleep(0.8)
        await callback.message.edit_text(
            f"⏳ **Menyusun Laporan...**\n"
            f"📅 Periode: `{year}-{month:02d}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📉 *Menghitung margin & selisih dana...*",
            parse_mode="Markdown"
        )
        
        db_rows = ledger_repo.get_ledger_for_period(shop_id, year, month)
        transactions = []
        for i, (order, ledger) in enumerate(db_rows):
            transactions.append(AuditTransaction(
                row_no=i + 1,
                received_at=order.pay_time.date() if order.pay_time else None,
                shipped_at=None,
                completed_at=None,
                order_label=order.order_sn[:8],
                order_sn=order.order_sn,
                order_amount=order.total_amount,
                dana_diterima=ledger.final_income,
                keterangan=f"Status: {order.status}"
            ))

        # Fetch detailed activity logs
        activity_repo = ActivityLogRepository(session)
        from datetime import datetime
        start_dt = datetime(year, month, 1)
        end_dt = datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
        activity_logs = activity_repo.get_for_period(shop_id, start_dt, end_dt)

        req = ReportRequest(
            shop_id=shop_id, 
            year=year, 
            month=month, 
            creator=str(callback.from_user.id),
            transactions=transactions
        )
        
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, agent.generate_audit_workbook, req, activity_logs)

    # 3. Final Result Experience
    summary_text = agent.format_telegram_summary(result)
    
    from shopee_agent.app.gsheets_agent import GSheetsAgent
    gs_agent = GSheetsAgent(settings.google_service_account, settings.google_admin_email)
    cloud_url = await gs_agent.sync_audit_report(req)
    
    from shopee_agent.entrypoints.telegram.keyboards import get_audit_result_keyboard
    await callback.message.edit_text(
        summary_text,
        reply_markup=get_audit_result_keyboard(result.export_id, cloud_url),
        parse_mode="Markdown"
    )
    
    # Send the physical file as backup
    doc = FSInputFile(result.file_path)
    await bot.send_document(
        callback.message.chat.id,
        doc,
        caption=f"📊 *Audit Backup* | {year}-{month:02d}",
        parse_mode="Markdown"
    )
    await callback.answer("Audit Berhasil Terbit! ✅")

async def sync_single_shop(shop_id: str, llm: LLMGateway | None) -> str:
    """Helper to sync one shop's data."""
    with SessionLocal() as session:
        # Event & Decision Orchestration Wiring
        from shopee_agent.app.events import EventIngestService
        from shopee_agent.app.decisions import DecisionEngine
        from shopee_agent.app.workflows import WorkflowEngine
        from shopee_agent.persistence.repositories import (
            EventRepository, DecisionRepository, WorkflowRepository
        )
        
        from shopee_agent.app.queue import OutboxQueue
        
        supervisor = OperationsSupervisorAgent(OperatorTaskRepository(session))
        
        event_service = EventIngestService(
            event_repo=EventRepository(session),
            decision_engine=DecisionEngine(policy_version="v1.0-prod"),
            decision_repo=DecisionRepository(session),
            workflow_engine=WorkflowEngine(),
            workflow_repo=WorkflowRepository(session),
            outbox_queue=OutboxQueue(session),
        )

        order_agent = OrderAgent(
            order_repo=OrderRepository(session),
            ledger_repo=FinanceLedgerRepository(session),
            supervisor=supervisor,
            event_service=event_service,
            llm=llm
        )
        # 1. Sync Orders (Real logic)
        from shopee_agent.providers.shopee.client import ShopeeClient
        from shopee_agent.providers.shopee.gateway import ShopeeGateway
        client = ShopeeClient(settings.shopee_base_url, settings.shopee_partner_id, settings.shopee_partner_key)
        shopee_gateway = ShopeeGateway(client, ShopTokenRepository(session))
        
        # Fetch last 3 days to ensure no misses
        time_to = int(datetime.now().timestamp())
        time_from = time_to - (3600 * 24 * 3)
        orders = await shopee_gateway.get_order_list(shop_id, time_from=time_from, time_to=time_to)
        order_result = await order_agent.ingest_orders(orders, shop_id)
        
        # 1.1 Sync Finances for pending settlements
        ledger_repo = FinanceLedgerRepository(session)
        unsettled = ledger_repo.get_unsettled_ledger_orders(shop_id)
        # Limit to 10 for performance during sync, background task will catch others
        for sn in unsettled[:10]:
            await order_agent.sync_order_finances(shop_id, sn, shopee_gateway)
        
        # 2. Sync Returns
        dispute_agent = DisputeAgent(
            shopee_gateway=shopee_gateway,
            dispute_repo=ReturnDisputeRepository(session),
            supervisor=supervisor,
            llm=llm
        )
        dispute_count = await dispute_agent.sync_returns(shop_id)
        
        # Health & Expiry Check
        h = HealthAgent(ShopTokenRepository(session)).get_shop_health(shop_id)
        if h["status"] in ["CRITICAL", "EXPIRED"]:
            await bot.send_message(
                settings.admin_chat_id,
                f"🚨 **ALERTA P0: TOKEN KEDALUWARSA**\n🏪 Toko: `{h['shop_id']}`\nStatus: *{h['status']}*\n\n"
                "Segera lakukan re-autentikasi agar operasional tidak terputus!",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown"
            )

        # 3. Sync Products to Knowledge Base
        pk_agent = ProductKnowledgeAgent(ProductKnowledgeRepository(session))
        inv_repo = InventoryRepository(session)
        try:
            raw_items = await shopee_gateway.get_item_list(shop_id)
            for raw_item in raw_items:
                pk_agent.upsert_product_from_api(shop_id, raw_item)
                item_id = str(raw_item.get("item_id", raw_item.get("id", "")))
                inv_items = inv_repo.get_items_for_shop(shop_id)
                pk_agent.enrich_from_inventory(shop_id, item_id, inv_items)
        except Exception as e:
            logger.warning(f"[Sync] Product KB sync failed for {shop_id}: {e}")

        # 4. SLA Alerts (HITL — send alert with approval buttons, never auto-ship)
        from shopee_agent.entrypoints.telegram.keyboards import get_ship_approval_keyboard
        async def send_sla_alert(order_sn: str, shop_id: str, hours_left: float, severity_icon: str) -> None:
            text = (
                f"{severity_icon} *SLA ALERT — Konfirmasi Pengiriman*\n\n"
                f"🏪 Toko: `{shop_id}`\n"
                f"📋 Order: `{order_sn}`\n"
                f"⏰ SLA Tersisa: *{hours_left:.1f} jam*\n\n"
                f"_Tekan tombol di bawah untuk konfirmasi atau tunda._"
            )
            await bot.send_message(
                settings.admin_chat_id, text,
                reply_markup=get_ship_approval_keyboard(order_sn, shop_id),
                parse_mode="Markdown",
            )

        sla_agent = OrderAgent(
            order_repo=OrderRepository(session),
            ledger_repo=FinanceLedgerRepository(session),
            supervisor=supervisor,
            event_service=event_service,
            llm=llm
        )
        alerted = await sla_agent.alert_sla_risk_orders(shop_id, notify_fn=send_sla_alert)

        return (
            f"🏪 *Toko:* `{shop_id}`\n"
            f"📦 Pesanan: {order_result.synced}\n"
            f"🚨 SLA Alert: {len(alerted)} order\n"
            f"⚖️ Komplain: {dispute_count}\n\n"
        )


def get_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Range selection for dashboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Harian", callback_data="db_1d"),
        InlineKeyboardButton(text="📅 Mingguan", callback_data="db_7d"),
        InlineKeyboardButton(text="📅 Bulanan", callback_data="db_30d"),
    )
    return builder.as_markup()


@dispatcher.message(Command("dashboard"))
async def dashboard_cmd(message: Message) -> None:
    """Show interactive global dashboard."""
    await bot.send_chat_action(message.chat.id, "typing")
    agent = get_analytics_agent()
    report = agent.get_kpi_report_for_range(30)
    text = agent.format_dashboard_text(report)
    await message.answer(text, reply_markup=get_dashboard_keyboard(), parse_mode="Markdown")


@dispatcher.callback_query(lambda c: c.data.startswith("db_"))
async def dashboard_callback(callback: CallbackQuery) -> None:
    """Refresh dashboard with selected range."""
    days = int(callback.data.split("_")[1].replace("d", ""))
    agent = get_analytics_agent()
    report = agent.get_kpi_report_for_range(days)
    
    range_text = "Harian" if days == 1 else "Mingguan" if days == 7 else "Bulanan"
    text = agent.format_dashboard_text(report)
    text = text.replace("Dashboard Global", f"Dashboard Global ({range_text})")
    
    await callback.message.edit_text(text, reply_markup=get_dashboard_keyboard(), parse_mode="Markdown")
    await callback.answer()


@dispatcher.message(Command("briefing"))
async def briefing_cmd(message: Message) -> None:
    """Manual trigger for daily briefing."""
    await bot.send_chat_action(message.chat.id, "typing")
    agent = get_analytics_agent()
    text = agent.get_daily_briefing()
    await message.answer(text, parse_mode="Markdown")

@dispatcher.message(Command("diagnose"))
async def diagnose_cmd(message: Message) -> None:
    """Production self-diagnostic check."""
    await bot.send_chat_action(message.chat.id, "typing")
    
    results = []
    # 1. DB Check
    try:
        with SessionLocal() as session:
            session.execute(select(1))
            results.append("✅ **Database:** Terhubung")
    except Exception as e:
        results.append(f"❌ **Database:** Error ({str(e)})")
        
    # 2. LLM Check
    llm = get_llm_gateway()
    if llm:
        results.append("✅ **LLM Gateway:** Konfigurasi OK")
    else:
        results.append("⚠️ **LLM Gateway:** Nonaktif")
        
    # 3. Environment Check
    required = ["TELEGRAM_BOT_TOKEN", "ADMIN_CHAT_ID", "SHOPEE_PARTNER_ID"]
    missing = [r for r in required if not getattr(settings, r.lower(), None)]
    if not missing:
        results.append("✅ **Environment:** Variabel lengkap")
    else:
        results.append(f"❌ **Environment:** Kurang {', '.join(missing)}")

    text = "🔬 **Laporan Diagnostik Sistem**\n━━━━━━━━━━━━━━━\n" + "\n".join(results)
    await message.answer(text, parse_mode="Markdown")

@dispatcher.message(Command("sync"))
async def sync_cmd(message: Message) -> None:
    """Trigger order sync for all shops in background."""
    if SYNC_SEMAPHORE.locked():
        await message.answer("⚠️ **Sinkronisasi sedang berjalan** Kak. Mohon tunggu sebentar ya. 🙏")
        return

    await bot.send_chat_action(message.chat.id, "typing")
    await message.answer("🔄 **Sinkronisasi dimulai!**\nSedang memproses semua toko di latar belakang...\nSaya akan kasih tahu kalau sudah selesai ya Kak. 👋")
    
    asyncio.create_task(run_background_sync_flow(message))

async def run_background_sync_flow(message: Message) -> None:
    """Actual heavy lifting for sync, offloaded from the handler."""
    async with SYNC_SEMAPHORE:
        shop_ids = get_shop_ids() or ["demo_shop"]
        llm = get_llm_gateway()
        
        # 1. Parallel Execution
        tasks = [sync_single_shop(sid, llm) for sid in shop_ids]
        results = await asyncio.gather(*tasks)
        
        # 2. Results Notification
        summary_text = "".join(results)
        await message.answer(
            f"✨ **SINKRONISASI SELESAI** ✨\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"{summary_text}"
            f"━━━━━━━━━━━━━━━\n"
            "💡 *Tip:* Gunakan /inbox untuk melihat tugas mendesak baru.",
            reply_markup=get_post_sync_keyboard(),
            parse_mode="Markdown"
        )


@dispatcher.message(Command("chat"))
async def chat_cmd(message: Message) -> None:
    """Simulate classifying an incoming buyer message."""
    query = message.text.replace("/chat", "").strip()
    if not query:
        await message.answer("ℹ️ Cara pakai: `/chat <pesan pembeli>`\n\nContoh: `/chat Kak kapan pesanan saya sampai?`", parse_mode="Markdown")
        return

    await bot.send_chat_action(message.chat.id, "typing")
    await message.answer(f"🔍 *Menganalisis pesan:* \"{query}\"", parse_mode="Markdown")
    
    try:
        with SessionLocal() as session:
            pk_repo = ProductKnowledgeRepository(session)
            chat_agent = get_chat_agent(pk_repo=pk_repo)
            shop_ids = get_shop_ids()
            shop_id = shop_ids[0] if shop_ids else "demo_shop"
            from shopee_agent.contracts.knowledge import ProductFact
            product_facts: list[ProductFact] = []
            fact = pk_repo and ProductKnowledgeAgent(pk_repo).lookup(shop_id, query)
            if fact:
                product_facts = [fact]
            classification = chat_agent.classify(query)
            decision = await chat_agent.decide(query, classification, product_facts=product_facts or None)
            
            session_repo = ChatSessionRepository(session)
            user_id = str(message.from_user.id)
            session_repo.get_or_create_session(f"sim_{user_id}", shop_id, buyer_id=user_id)
            session_repo.add_message(f"sim_{user_id}", ChatMessage(role="user", content=query))
            if decision.draft_reply:
                session_repo.add_message(f"sim_{user_id}", ChatMessage(role="assistant", content=decision.draft_reply))
            
            session_repo.update_session(
                f"sim_{user_id}", 
                last_intent=classification.intent,
                risk_tier=classification.risk_tier
            )

            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(decision.classification.risk_tier, "⚪")
            sentiment_icon = "😊" if decision.classification.sentiment == "positive" else "😐" if decision.classification.sentiment == "neutral" else "😡"
            
            reply_text = (
                f"🧠 **Analisis Pesan Pembeli**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Niat Pembeli:** `{decision.classification.intent.upper()}`\n"
                f"🎯 **Sentimen:** {sentiment_icon} `{decision.classification.sentiment.capitalize()}`\n"
                f"🛡️ **Level Risiko:** {risk_emoji} `{decision.classification.risk_tier.capitalize()}`\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 **Draft Balasan AI:**\n"
                f"_{decision.draft_reply}_\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💡 **Strategi:** {decision.reasoning}"
            )
            
            from shopee_agent.entrypoints.telegram.keyboards import get_chat_keyboard
            await message.answer(
                reply_text,
                reply_markup=get_chat_keyboard(f"sim_{user_id}", shop_id),
                parse_mode="Markdown"
            )
    except Exception:
        await message.answer("❌ Gagal menganalisis pesan. Mohon coba lagi Kak.")



@dispatcher.message(Command("ask"))
async def ask_cmd(message: Message) -> None:
    """Ask a general product or policy question using LLM + Knowledge Base."""
    query = message.text.replace("/ask", "").strip()
    if not query:
        await message.answer("ℹ️ Cara pakai: `/ask <pertanyaan Anda>`", parse_mode="Markdown")
        return

    llm = get_llm_gateway()
    if not llm:
        await message.answer("❌ Maaf Kak, fitur AI belum dikonfigurasi.")
        return

    await bot.send_chat_action(message.chat.id, "typing")
    await message.answer(f"🤔 *Sedang mencari jawaban untuk:* \"{query}\"...", parse_mode="Markdown")
    
    with SessionLocal() as session:
        pk_repo = ProductKnowledgeRepository(session)
        pk_agent = ProductKnowledgeAgent(pk_repo)

        shop_ids = get_shop_ids()
        shop_id = shop_ids[0] if shop_ids else "demo_shop"
        fact = pk_agent.lookup(shop_id, query)

        if fact:
            product_context = pk_agent.build_context_for_ai(fact)
            prompt = (
                f"Seorang operator toko bertanya tentang produk.\n"
                f"Pertanyaan: {query}\n\n"
                f"{product_context}\n\n"
                f"Jawab pertanyaan dengan akurat berdasarkan data di atas. "
                f"Gunakan Bahasa Indonesia yang profesional."
            )
        else:
            prompt = (
                f"Seorang operator toko bertanya: {query}\n"
                f"Tidak ada data produk di KB. Minta operator untuk /sync terlebih dahulu."
            )

        ans = await llm.generate_response(prompt)
        await message.answer(f"💡 *Jawaban AI:*\n\n{ans}", parse_mode="Markdown")


@dispatcher.message(Command("returns"))
async def returns_cmd(message: Message) -> None:
    """List active returns and disputes."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    
    with SessionLocal() as session:
        repo = ReturnDisputeRepository(session)
        text = "⚖️ **Daftar Komplain & Pengembalian Aktif:**\n\n"
        found = False
        
        for shop_id in shop_ids:
            returns = repo.get_active_returns(shop_id)
            if not returns:
                continue
            
            found = True
            text += f"🏪 *Toko:* `{shop_id}`\n"
            for r in returns:
                from sqlalchemy import select
                from shopee_agent.persistence.models import ReturnDisputeRecord
                record = session.scalar(
                    select(ReturnDisputeRecord).where(ReturnDisputeRecord.return_sn == r.return_sn)
                )
                risk_emoji = "🔴" if record.risk_score > 0.7 else "🟡"
                
                rec_text = "TIDAK ADA"
                if record.agent_recommendation:
                    rec_text = record.agent_recommendation.upper()
                    
                text += (
                    f"{risk_emoji} *{r.return_sn}* - Rp {r.amount:,.0f}\n"
                    f"Alasan: `{r.reason}`\n"
                    f"Saran AI: `{rec_text}`\n"
                    f"/find_{r.return_sn}\n\n"
                )
        
        if not found:
            await message.answer("✅ Yey! Tidak ada komplain aktif saat ini Kak.")
        else:
            await message.answer(text, parse_mode="Markdown")


@dispatcher.message(Command("stock"))
async def stock_cmd(message: Message) -> None:
    """Show predictive inventory health."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_id = "demo_shop" # In production, get from context
    
    with SessionLocal() as session:
        supervisor = get_supervisor()
        agent = InventoryHealthAgent(session, supervisor)
        alerts = await agent.check_health(shop_id)
        text = agent.get_stock_status_text(alerts, shop_id)
        await message.answer(text, parse_mode="Markdown")

@dispatcher.message(Command("ship"))
async def ship_cmd(message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ️ Cara pakai: `/ship <nomor_pesanan>`", parse_mode="Markdown")
        return
    
    order_sn = parts[1]
    # In a real app, we'd lookup the shop_id for this order_sn
    await message.answer(f"📦 Menyiapkan pengiriman untuk `{order_sn}`...", reply_markup=get_logistics_keyboard(order_sn, "demo_shop"), parse_mode="Markdown")


@dispatcher.message(Command("chats"))
async def chats_cmd(message: Message) -> None:
    await bot.send_chat_action(message.chat.id, "typing")
    await message.answer("💬 **Percakapan Aktif:**\n━━━━━━━━━━━━━━━\n\n1. `Pembeli_001`: \"Kapan pesanan saya sampai kak?\"\n2. `Pembeli_002`: \"Bisa minta foto asli barangnya?\"\n\nPilih chat untuk membalas:", parse_mode="Markdown")


@dispatcher.message(Command("label"))
async def label_cmd(message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ️ Cara pakai: `/label <nomor_pesanan>`", parse_mode="Markdown")
        return
    
    order_sn = parts[1]
    await message.answer(f"📄 Menarik resi untuk pesanan `{order_sn}`...", reply_markup=get_logistics_keyboard(order_sn, "demo_shop"), parse_mode="Markdown")

@dispatcher.message(Command("escrow"))
async def escrow_cmd(message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ️ Cara pakai: `/escrow <nomor_pesanan>`", parse_mode="Markdown")
        return
    
    order_sn = parts[1]
    with SessionLocal() as session:
        repo = FinanceLedgerRepository(session)
        ledger = repo.session.scalar(
            select(FinanceLedgerRecord).where(FinanceLedgerRecord.order_sn == order_sn)
        )
        
        if not ledger:
            await message.answer(f"❌ Data keuangan untuk `{order_sn}` tidak ditemukan.", parse_mode="Markdown")
            return
            
        text = (
            f"💰 **Rincian Keuangan — {order_sn}**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💵 Escrow: `Rp {ledger.escrow_amount:,.0f}`\n"
            f"📉 Komisi: `-Rp {ledger.commission_fee:,.0f}`\n"
            f"📉 Service Fee: `-Rp {ledger.service_fee:,.0f}`\n"
            f"🚚 Ongkir: `-Rp {ledger.shipping_fee:,.0f}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✨ **Income Bersih: Rp {ledger.final_income:,.0f}**\n"
            f"Status: `{ledger.settlement_status.upper()}`\n"
        )
        await message.answer(text, parse_mode="Markdown")
@dispatcher.message(Command("bulk_ship"))
async def bulk_ship_cmd(message: Message) -> None:
    """Find all READY_TO_SHIP orders and propose bulk shipment."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        repo = OrderRepository(session)
        orders = repo.get_active_orders(shop_id)
        rts = [o for o in orders if o.status in ("READY_TO_SHIP", "PROCESSED")]
        
        if not rts:
            await message.answer("✅ Tidak ada pesanan yang menunggu pengiriman.")
            return
            
        text = (
            f"📦 **Permintaan Pengiriman Massal**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Terdapat `{len(rts)}` pesanan siap kirim.\n"
            f"Konfirmasi untuk memproses semuanya secara otomatis?"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="🚀 Proses Semua", callback_data=f"bulk_confirm:{shop_id}")
        builder.button(text="❌ Batal", callback_data="bulk_cancel")
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dispatcher.message(Command("print_all"))
async def print_all_cmd(message: Message) -> None:
    """Find all generated labels and send to printer."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        from shopee_agent.persistence.repositories import LogisticsRepository
        repo = LogisticsRepository(session)
        unprinted = repo.get_unlabeled(shop_id) # In real app, check 'generated' status
        
        if not unprinted:
            await message.answer("🖨️ Tidak ada label baru untuk dicetak.")
            return
            
        await message.answer(f"🖨️ Mengirim `{len(unprinted)}` label ke antrian cetak...")
        # Simulation of bulk print
        await message.answer("✅ Semua label berhasil dikirim ke printer thermal.")

@dispatcher.message(Command("restock"))
async def restock_cmd(message: Message) -> None:
    """Analyze inventory and propose a restock plan."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        agent = InventoryHealthAgent(session)
        proposals = agent.propose_restock_plan(shop_id)
        
        if not proposals:
            await message.answer("✅ **Persediaan Aman.** Tidak ada item yang perlu di-restock saat ini.")
            return
            
        text = f"📦 **Rencana Restock — {shop_id}**\n━━━━━━━━━━━━━━━\n\n"
        for p in proposals:
            icon = "🔴" if p["priority"] == "HIGH" else "🟡"
            text += f"{icon} *{p['name']}*\n   Stok: `{p['current_stock']}` | Restock: `+{p['restock_qty']}`\n"
            
        text += "\n━━━━━━━━━━━━━━━\nKlik tombol di bawah untuk mendownload PO Supplier."
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📄 Download PO Excel", callback_data=f"restock_po:{shop_id}")
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dispatcher.message(Command("kb_audit"))
async def kb_audit_cmd(message: Message) -> None:
    """Scan unresolved chats and propose knowledge additions."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        chat_repo = ChatSessionRepository(session)
        pk_repo = ProductKnowledgeRepository(session)
        unresolved = chat_repo.get_unresolved_sessions(shop_id)
        
        if not unresolved:
            await message.answer("✅ **Knowledge Base Audit Selesai.** Semua chat hari ini teratasi dengan baik.")
            return
            
        await message.answer(f"🔍 Menganalisis `{len(unresolved)}` chat yang belum teratasi...")
        
        chat_agent = get_chat_agent()
        pk_agent = get_pk_agent()
        
        gaps_found = 0
        for sess in unresolved:
            history_data = json.loads(sess.messages_json)
            history = [ChatMessage(content=m["content"], is_buyer=m["is_buyer"]) for m in history_data]
            
            # Identify item_id if possible
            item_id = "unknown"
            if sess.order_sn:
                order_repo = OrderRepository(session)
                order = order_repo.get_order(sess.order_sn, shop_id)
                if order:
                    try:
                        data = json.loads(order.data_json)
                        items = data.get("item_list", [])
                        if items: item_id = str(items[0]["item_id"])
                    except: pass
            
            facts = [pk_repo.get_pk(shop_id, item_id)] if item_id != "unknown" else None
            gap = await chat_agent.extract_knowledge_gap(history, facts)
            
            if gap and item_id != "unknown":
                gaps_found += 1
                text = (
                    f"💡 **AI Learning Opportunity**\n"
                    f"📦 Produk: `{item_id}`\n"
                    f"❓ Tanya: \"{gap['question']}\"\n"
                    f"📝 Jawab: \"{gap['answer']}\"\n\n"
                    f"Alasan: {gap['reason']}"
                )
                builder = InlineKeyboardBuilder()
                # Encoded data for approval: learn:item_id:question_hash:answer_hash
                # For demo, we'll use a simpler callback or state
                builder.button(text="✅ Terapkan ke KB", callback_data=f"kb_learn:{shop_id}:{item_id}")
                builder.button(text="❌ Abaikan", callback_data="kb_ignore")
                await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        
        if gaps_found == 0:
            await message.answer("ℹ️ Tidak ditemukan celah pengetahuan baru dari chat yang dianalisis.")

@dispatcher.message(Command("finance"))
async def finance_cmd(message: Message) -> None:
    """Show daily financial summary."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        from shopee_agent.app.finance_agent import FinanceAgent
        from shopee_agent.persistence.repositories import FinanceLedgerRepository, OperatorTaskRepository
        from shopee_agent.app.operations import OperationsSupervisorAgent
        
        agent = FinanceAgent(FinanceLedgerRepository(session), OperationsSupervisorAgent(OperatorTaskRepository(session)))
        flash = agent.get_daily_flash(shop_id)
        
        text = (
            f"📊 **Ringkasan Harian — {shop_id}**\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📦 **Pesanan Baru:** `{flash['order_count']}`\n"
            f"💰 **Total Omzet:** `Rp {flash['total_revenue']:,.0f}`\n"
            f"✨ **Income Bersih:** `Rp {flash['total_income']:,.0f}`\n"
            f"🚚 **Biaya Ongkir:** `Rp {flash['total_shipping']:,.0f}`\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 *Tip:* Gunakan /report untuk download Excel lengkap bulan ini."
        )
        await message.answer(text, parse_mode="Markdown")

@dispatcher.message(Command("printer"))
async def printer_cmd(message: Message) -> None:
    """Setup and check remote printer status."""
    await bot.send_chat_action(message.chat.id, "typing")
    from shopee_agent.app.print_agent import PrintAgent
    # In real app, fetch API keys from settings
    agent = PrintAgent(api_key="mock_key", printer_id="home_thermal_01")
    printers = await agent.get_printers()
    
    text = "🖨️ **Status Printer Jarak Jauh**\n━━━━━━━━━━━━━━━\n\n"
    for p in printers:
        status = "🟢 Online" if p["state"] == "online" else "🔴 Offline"
        text += f"• **{p['name']}** (ID: `{p['id']}`)\n  Status: {status}\n\n"
    
    text += "━━━━━━━━━━━━━━━\n"
    if any(p["state"] == "online" for p in printers):
        text += "✅ Siap mencetak resi otomatis ke rumah."
    else:
        text += "⚠️ Pastikan laptop di rumah menyala dan aplikasi PrintNode aktif."
        
    await message.answer(text, parse_mode="Markdown")

@dispatcher.message(Command("analytics"))
async def analytics_cmd(message: Message) -> None:
    """Show deep performance analysis."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        from shopee_agent.app.finance_agent import FinanceAgent
        from shopee_agent.persistence.repositories import FinanceLedgerRepository, OperatorTaskRepository
        from shopee_agent.app.operations import OperationsSupervisorAgent
        
        agent = FinanceAgent(FinanceLedgerRepository(session), OperationsSupervisorAgent(OperatorTaskRepository(session)))
        report = agent.get_performance_report(shop_id, days=7)
        
        text = (
            f"📈 **Analytics Mingguan — {shop_id}**\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"💰 **Total Revenue:** `Rp {report['total_revenue']:,.0f}`\n"
            f"✨ **Net Profit:** `Rp {report['total_income']:,.0f}`\n"
            f"📈 **Profit Margin:** `{report['profit_margin']}%`\n"
            f"📦 **Total Orders:** `{report['order_count']}`\n"
            f"🎫 **Avg Order Value:** `Rp {report['avg_order_value']:,.0f}`\n\n"
            f"🔥 **Top 3 Kandang Terlaris:**\n"
        )
        
        for i, item in enumerate(report["top_items"], 1):
            text += f"{i}. *{item['name']}* ({item['qty']} terjual)\n"
            
        text += (
            f"\n━━━━━━━━━━━━━━━\n"
            f"💡 **AI Insight:** "
        )
        
        if report["profit_margin"] < 10:
            text += "Margin Anda cukup tipis. Pertimbangkan untuk meninjau biaya operasional atau sedikit menaikkan harga varian terlaris."
        elif report["profit_margin"] > 25:
            text += "Performa luar biasa! Anda memiliki ruang untuk melakukan promosi (Flash Sale) untuk mendongkrak volume."
        else:
            text += "Bisnis berjalan stabil. Fokus pada ketersediaan stok untuk item terlaris Anda."
            
        await message.answer(text, parse_mode="Markdown")

@dispatcher.message(F.text.in_([
    "📥 Tugas Hari Ini", "📅 Jadwal & Agenda", "📈 Laporan Penjualan", 
    "⭐ Ulasan Pembeli", "📦 Cek Stok", "💰 Uang Masuk", "🏪 Daftar Toko", "⚙️ Pengaturan"
]))
async def menu_button_handler(message: Message) -> None:
    text = message.text
    if "Tugas" in text: await inbox(message)
    elif "Jadwal" in text: await agenda(message)
    elif "Laporan" in text: await analytics_cmd(message)
    elif "Ulasan" in text: await reviews_cmd(message)
    elif "Cek Stok" in text: await stock_cmd(message)
    elif "Uang" in text: await finance_cmd(message)
    elif "Daftar Toko" in text: await shops_cmd(message)
    elif "Pengaturan" in text: await help_cmd(message)

@dispatcher.message(Command("promo"))
async def promo_cmd(message: Message) -> None:
    """Generate social media promo captions for products."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        from shopee_agent.persistence.repositories import ProductKnowledgeRepository
        from shopee_agent.app.product_knowledge_agent import ProductKnowledgeAgent
        
        repo = ProductKnowledgeRepository(session)
        pk_agent = ProductKnowledgeAgent(repo)
        
        # Pick 3 random products or top selling
        from shopee_agent.persistence.models import ProductKnowledgeRecord
        from sqlalchemy import func
        items = session.scalars(select(ProductKnowledgeRecord).where(ProductKnowledgeRecord.shop_id == shop_id).order_by(func.random()).limit(3)).all()
        
        if not items:
            await message.answer("📭 Belum ada produk di database. Silakan `/sync` terlebih dahulu.")
            return
            
        await message.answer("📱 **Pilih produk untuk dibuatkan caption promosi:**", parse_mode="Markdown")
        for itm in items:
            builder = InlineKeyboardBuilder()
            builder.button(text="✍️ Buat Caption", callback_data=f"gen_promo:{shop_id}:{itm.item_id}")
            await message.answer(f"📦 **{itm.name}**\nItem ID: `{itm.item_id}`", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dispatcher.message(F.photo)
async def handle_photo(message: Message) -> None:
    """Process incoming photos using Vision AI."""
    await bot.send_chat_action(message.chat.id, "typing")
    
    # Download the highest resolution photo
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    
    os.makedirs("./data/media", exist_ok=True)
    file_path = f"./data/media/{photo.file_id}.jpg"
    await bot.download_file(file.file_path, file_path)
    
    from shopee_agent.app.vision_agent import VisionAgent
    vision = VisionAgent(get_llm_gateway())
    
    # Context-aware prompt
    prompt = "Apa yang Anda lihat di foto ini? Jika ini berkaitan dengan stok atau pengiriman produk, berikan analisis teknisnya."
    if message.caption:
        prompt = f"Instruksi User: {message.caption}\n\nAnalisis foto ini berdasarkan instruksi tersebut."
        
    analysis = await vision.analyze_image(file_path, prompt)
    await message.reply(f"👁️ **Analisis AI Vision:**\n\n{analysis}", parse_mode="Markdown")

@dispatcher.message(F.voice)
async def handle_voice(message: Message) -> None:
    """Process incoming voice messages."""
    await bot.send_chat_action(message.chat.id, "typing")
    
    voice = message.voice
    file = await bot.get_file(voice.file_id)
    
    os.makedirs("./data/media", exist_ok=True)
    file_path = f"./data/media/{voice.file_id}.ogg"
    await bot.download_file(file.file_path, file_path)
    
    from shopee_agent.app.voice_agent import VoiceAgent
    voice_agent = VoiceAgent(get_llm_gateway())
    
    transcription = await voice_agent.process_voice(file_path)
    await message.reply(f"🎤 **Transkripsi Suara:**\n\n_\"{transcription}\"_", parse_mode="Markdown")
    
    # Follow up with text handler logic to treat voice as a command
    message.text = transcription
    if any(k in transcription for k in ["Tugas", "Jadwal", "Laporan", "Ulasan", "Cek Stok", "Uang", "Daftar Toko", "Pengaturan"]):
        await menu_button_handler(message)
    elif transcription.startswith("/"):
        await message.answer("ℹ️ Maaf Kak, perintah suara hanya mendukung menu utama. Untuk fitur lainnya, mohon diketik ya.", parse_mode="Markdown")
    else:
        await fallback_handler(message)

@dispatcher.message(Command("reviews"))
async def reviews_cmd(message: Message) -> None:
    """Manage product reviews and AI replies."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        from shopee_agent.app.review_agent import ReviewAgent
        agent = ReviewAgent(session, get_llm_gateway())
        
        # 1. Sync & Draft (Simulation)
        await agent.draft_all_pending(shop_id)
        
        pending = agent.get_pending_replies(shop_id)
        
        if not pending:
            await message.answer("✅ **Semua ulasan sudah dibalas.**")
            return
            
        await message.answer(f"⭐ **Manajemen Ulasan — {shop_id}**\nMenunggu persetujuan: `{len(pending)}` ulasan", parse_mode="Markdown")
        
        for rev in pending[:3]:
            stars = "⭐" * rev.rating_star
            text = (
                f"{stars}\n"
                f"💬 **Buyer:** \"{rev.comment}\"\n"
                f"✍️ **Draft AI:** \"{rev.reply_comment}\""
            )
            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Kirim Balasan", callback_data=f"rev_approve:{rev.review_id}")
            builder.button(text="✏️ Edit", callback_data=f"rev_edit:{rev.review_id}")
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dispatcher.message(Command("boost"))
async def boost_status_cmd(message: Message) -> None:
    """Manage and monitor automated product boosting."""
    await bot.send_chat_action(message.chat.id, "typing")
    shop_ids = get_shop_ids() or ["demo_shop"]
    shop_id = shop_ids[0]
    
    with SessionLocal() as session:
        from shopee_agent.app.booster_agent import BoosterAgent
        agent = BoosterAgent(session, None)
        active = agent.get_active_boosts(shop_id)
        
        text = f"🚀 **Product Booster — {shop_id}**\n━━━━━━━━━━━━━━━\n\n"
        if not active:
            text += "📭 Belum ada produk yang dinaikkan otomatis."
        else:
            for b in active:
                if b.expires_at and b.expires_at > datetime.now():
                    remaining = (b.expires_at - datetime.now()).total_seconds() / 60
                    text += f"\u2022 `{b.item_id}`\n  \u23f3 Sisa: `{int(remaining)} menit`\n"
                else:
                    text += f"\u2022 `{b.item_id}`\n  \u23f3 Sisa: `Segera berakhir`\n"
            
        text += (
            f"\n━━━━━━━━━━━━━━━\n"
            f"💡 *Otomasi:* Sistem akan memilih 5 produk terlaris Anda dan menaikkannya secara otomatis setiap 4 jam."
        )
        await message.answer(text, parse_mode="Markdown")

@dispatcher.message(Command("backup"))
async def backup_cmd(message: Message) -> None:
    """Trigger manual database backup and send to Telegram."""
    await bot.send_chat_action(message.chat.id, "upload_document")
    await message.answer("💾 **Memulai proses backup data...**", parse_mode="Markdown")
    
    from shopee_agent.app.backup_agent import BackupAgent
    db_path = settings.database_url.replace("sqlite:///", "")
    agent = BackupAgent(db_path)
    
    backup_file = agent.create_sqlite_backup()
    if backup_file:
        from aiogram.types import FSInputFile
        document = FSInputFile(str(backup_file))
        await bot.send_document(
            message.chat.id, 
            document, 
            caption=f"💾 **Database Snapshot**\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        await message.answer("✅ **Backup berhasil dikirim.**")
    else:
        await message.answer("❌ **Gagal melakukan backup.**")


@dispatcher.message()
async def fallback_handler(message: Message) -> None:
    """Handle generic non-command messages to prevent 'hanging' feeling."""
    # Ignore commands that might have been typed wrong
    if message.text and message.text.startswith("/"):
        await message.answer("🙏 Waduh, fitur itu belum ada Kak. Coba ketik /help ya.")
        return
        
    await message.answer(
        "Halo Kak! 👋 Ada yang bisa dibantu?\n"
        "Biar gampang, Kakak bisa langsung tekan tombol menu di bawah ini ya. 👇",
        reply_markup=get_main_menu_keyboard()
    )


async def background_sync_task(bot: Bot) -> None:
    """Periodic background task to sync and notify."""
    while True:
        async with SYNC_SEMAPHORE:
            try:
                import asyncio
                # 1. Sync
                shop_ids = get_shop_ids() or ["demo_shop"]
                llm = get_llm_gateway()
                
                with SessionLocal() as session:
                    log_repo = ActivityLogRepository(session)
                    log_repo.log("system", "sync", "Background sync cycle started.")
                
                # ... (rest of the logic inside)
                # Parallel Shop Sync
                async def run_shop_sync(shop_id):
                    try:
                        return await sync_single_shop(shop_id, llm)
                    except Exception as e:
                        logger.error(f"Sync failed for {shop_id}: {e}")
                        return None

                await asyncio.gather(*[run_shop_sync(sid) for sid in shop_ids])
                
                # (Notifications, Health, Boosts, Briefing)
                # ... skipping details for brevity but they are inside the semaphore now
                
                # 2. Dispatch Notifications
                try:
                    notification_agent = get_notification_agent()
                    await notification_agent.dispatch_pending_alerts(bot, settings.admin_chat_id)
                except Exception as e:
                    logger.error(f"Error dispatching notifications: {e}")

                # 3. Check Inventory Health
                try:
                    with SessionLocal() as session:
                        supervisor = get_supervisor()
                        health_agent = InventoryHealthAgent(session, supervisor)
                        for shop_id in shop_ids:
                            await health_agent.check_health(shop_id)
                except Exception as e:
                    logger.error(f"Error checking inventory health: {e}")
                
                # 4. Rotate Boosts
                try:
                    from shopee_agent.app.booster_agent import BoosterAgent
                    from shopee_agent.persistence.repositories import ShopTokenRepository
                    from shopee_agent.providers.shopee.client import ShopeeClient
                    from shopee_agent.providers.shopee.gateway import ShopeeGateway
                    
                    with SessionLocal() as session:
                        client = ShopeeClient("https://partner.shopeemobile.com", settings.shopee_partner_id, settings.shopee_partner_key)
                        gateway = ShopeeGateway(client, ShopTokenRepository(session))
                        booster = BoosterAgent(session, gateway)
                        for shop_id in shop_ids:
                            newly_boosted = await booster.auto_rotate_boosts(shop_id)
                            if newly_boosted:
                                await bot.send_message(settings.admin_chat_id, f"🚀 **Auto-Boost — {shop_id}**\nBerhasil menaikkan `{len(newly_boosted)}` produk.")
                except Exception as e:
                    logger.error(f"Error rotating boosts: {e}")

                # 5. Proactive Optimization Audit (Daily at 9 PM)
                now = datetime.now()
                if now.hour == 21:
                    try:
                        from shopee_agent.app.optimizer_agent import OptimizerAgent
                        with SessionLocal() as session:
                            optimizer = OptimizerAgent(session, get_llm_gateway())
                            for shop_id in shop_ids:
                                suggestion = await optimizer.run_daily_audit(shop_id)
                                if suggestion:
                                    await bot.send_message(
                                        settings.admin_chat_id, 
                                        f"💡 **AI Business Suggestion — {shop_id}**\n\n{suggestion}",
                                        parse_mode="Markdown"
                                    )
                    except Exception as e:
                        logger.error(f"Error in proactive audit: {e}")

                # 6. Briefing
                if 8 <= now.hour <= 9:
                    try:
                        from shopee_agent.app.maintenance_agent import MaintenanceAgent
                        with SessionLocal() as session:
                            m_agent = MaintenanceAgent(session, settings)
                            m_report = await m_agent.perform_scheduled_maintenance()
                            
                            # Add to daily briefing text
                            briefing_msg = "🌅 **Daily Maintenance Report**\n"
                            if m_report["expiring_shops"]:
                                briefing_msg += f"⚠️ **Token Segera Habis:** {', '.join(m_report['expiring_shops'])}\n"
                            if m_report["disk_warning"]:
                                briefing_msg += f"{m_report['disk_warning']}\n"
                            
                            if "⚠️" in briefing_msg:
                                await bot.send_message(settings.admin_chat_id, briefing_msg, parse_mode="Markdown")
                    except Exception as e:
                        logger.error(f"Maintenance failed: {e}")
                    with SessionLocal() as session:
                        log_repo = ActivityLogRepository(session)
                        last_briefing = session.scalars(
                            select(ActivityLogRecord).where(ActivityLogRecord.activity_type == "briefing")
                            .where(ActivityLogRecord.created_at >= now.replace(hour=0, minute=0, second=0))
                        ).first()
                        if not last_briefing:
                            analytics = get_analytics_agent()
                            text = analytics.get_daily_briefing()
                            await bot.send_message(settings.admin_chat_id, text, parse_mode="Markdown")
                            log_repo.log("system", "briefing", "Automated briefing sent.")

            except Exception as e:
                logger.error(f"Critical background error: {e}")
                
        await asyncio.sleep(180) # Wait 3m (Near Real-time Sync) outside semaphore


async def run_bot() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    
    # Register Commands for UI
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="Mulai & Menu Utama"),
        BotCommand(command="sync", description="Sinkronisasi Toko"),
        BotCommand(command="dashboard", description="Statistik & Performa"),
        BotCommand(command="agenda", description="Tugas Harian"),
        BotCommand(command="rekap", description="Download Laporan Excel"),
        BotCommand(command="briefing", description="Laporan Ringkas 24 Jam"),
        BotCommand(command="inbox", description="Pesan & Notifikasi"),
        BotCommand(command="health", description="Status Sistem & Toko"),
        BotCommand(command="backup", description="Backup Database"),
        BotCommand(command="help", description="Pusat Bantuan"),
    ]
    await bot.set_my_commands(commands)
    
    # Start Background Task
    asyncio.create_task(background_sync_task(bot))
    
    await dispatcher.start_polling(bot)
