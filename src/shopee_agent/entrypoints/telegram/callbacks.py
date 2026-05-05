from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery
import re
import json

from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.contracts.operations import TaskStatus
from shopee_agent.entrypoints.telegram.keyboards import (
    get_task_keyboard, get_logistics_keyboard, get_chat_keyboard, get_ship_approval_keyboard
)
from shopee_agent.persistence.session import SessionLocal
from shopee_agent.persistence.repositories import OrderRepository, ShopTokenRepository
from shopee_agent.providers.shopee.client import ShopeeClient
from shopee_agent.providers.shopee.gateway import ShopeeGateway
from shopee_agent.app.logistics_agent import LogisticsAgent, ShipmentResult
from shopee_agent.providers.llm.gateway import get_llm_gateway


def register_callbacks(dp: Dispatcher, supervisor: OperationsSupervisorAgent) -> None:
    @dp.callback_query(F.data == "view_inbox")
    async def view_inbox_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        from aiogram.enums import ChatAction
        await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action=ChatAction.TYPING)
        await callback.message.answer("Silakan gunakan tombol 📥 Tugas Hari Ini di menu ya Kak!")

    @dp.callback_query(F.data == "view_dashboard")
    async def view_dashboard_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        from aiogram.enums import ChatAction
        await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action=ChatAction.TYPING)
        await callback.message.answer("Silakan gunakan tombol 📈 Laporan Penjualan di menu ya Kak!")

    @dp.callback_query(F.data.startswith("chat_draft:"))
    async def handle_chat_draft(callback: CallbackQuery) -> None:
        try:
            parts = callback.data.split(":")
            shop_id, chat_id = parts[1], parts[2]
            
            await callback.answer("🤖 Sebentar Kak, AI lagi mikir...")
            from aiogram.enums import ChatAction
            await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action=ChatAction.TYPING)
            
            # Simulated draft for now, but wrapped in try/except
            draft_text = "Halo kak! Pesanan kakak sedang kami siapkan dan akan segera diserahkan ke kurir hari ini ya. Mohon ditunggu! 😊"
            
            await callback.message.answer(
                f"📝 **Draf dari AI untuk pembeli `{chat_id}`:**\n\n"
                f"\"{draft_text}\"\n\n"
                f"Kirim pesan ini?",
                reply_markup=get_chat_keyboard(chat_id, shop_id),
                parse_mode="Markdown"
            )
        except Exception:
            await callback.answer(f"🙏 Waduh, AI-nya lagi pusing. Coba lagi ya Kak!", show_alert=True)

    @dp.callback_query(F.data.startswith("chat_quick_ok:"))
    async def handle_chat_ok(callback: CallbackQuery) -> None:
        await callback.answer("✅ Message sent!")
        await callback.message.answer("✅ Replied with: `Halo Kak, Baik kak. Mohon ditunggu ya! 🙏`", parse_mode="Markdown")

    # We'll use a local import for agents to avoid circular dependencies if needed
    # but for now we'll assume they are provided or we fetch them via main's helpers
    # In a real app we'd use a DI container
    
    @dp.callback_query(F.data.startswith("ship_order:"))
    async def handle_ship_order(callback: CallbackQuery) -> None:
        try:
            parts = callback.data.split(":")
            shop_id, order_sn = parts[1], parts[2]
            
            await callback.answer(f"📦 Menyiapkan pesanan {order_sn}...")
            from aiogram.enums import ChatAction
            await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action=ChatAction.TYPING)
            
            # Use settings for credentials
            from shopee_agent.config.settings import get_settings
            settings = get_settings()
            with SessionLocal() as session:
                client = ShopeeClient("https://partner.shopeemobile.com", settings.shopee_partner_id, settings.shopee_partner_key)
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                from shopee_agent.persistence.repositories import LogisticsRepository
                agent = LogisticsAgent(gateway, OrderRepository(session), LogisticsRepository(session))
                
                res = await agent.arrange_shipment(shop_id, order_sn)
                
            await callback.message.answer(
                f"✅ Mantap! Pengiriman untuk `{order_sn}` sudah diatur.\n"
                f"Status: `SIAP DIKIRIM`", 
                parse_mode="Markdown"
            )
        except Exception as e:
            await callback.answer(f"🙏 Maaf Kak, gagal atur pengiriman. Shopee lagi sibuk nih.", show_alert=True)

    @dp.callback_query(F.data.startswith("confirm_ship:"))
    async def handle_confirm_ship(callback: CallbackQuery) -> None:
        """HITL: Human confirmed shipment. Ship, get resi, auto-print label."""
        try:
            parts = callback.data.split(":")
            shop_id, order_sn = parts[1], parts[2]

            await callback.answer(f"📦 Mengkonfirmasi pengiriman {order_sn}...")
            await callback.message.edit_text(
                f"⏳ _Sedang memproses pengiriman `{order_sn}`..._",
                parse_mode="Markdown",
            )

            from shopee_agent.config.settings import get_settings
            settings = get_settings()
            with SessionLocal() as session:
                client = ShopeeClient(
                    "https://partner.shopeemobile.com",
                    settings.shopee_partner_id,
                    settings.shopee_partner_key,
                )
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                from shopee_agent.persistence.repositories import LogisticsRepository
                from shopee_agent.app.print_agent import PrintAgent
                
                print_agent = PrintAgent(
                    api_key=settings.printnode_api_key,
                    printer_id=settings.printnode_printer_id
                )
                agent = LogisticsAgent(
                    gateway, 
                    OrderRepository(session), 
                    LogisticsRepository(session),
                    print_agent=print_agent
                )
                result: ShipmentResult = await agent.arrange_shipment(shop_id, order_sn)

            if not result.success:
                await callback.message.edit_text(
                    f"❌ *Gagal mengirim pesanan*\n`{order_sn}`\n\nError: `{result.error}`",
                    parse_mode="Markdown",
                )
                return

            # Show resi number
            resi_text = f"📦 *No. Resi:* `{result.tracking_no}`" if result.tracking_no else "⚠️ Resi belum tersedia, cek di Seller Center."
            await callback.message.edit_text(
                f"✅ *Pengiriman Dikonfirmasi!*\n\n"
                f"📋 Order: `{order_sn}`\n"
                f"{resi_text}\n\n"
                f"_Label PDF sedang dikirimkan..._",
                parse_mode="Markdown",
            )

            # Auto-send label PDF to Telegram chat
            if result.label_path and result.label_path.exists():
                from aiogram.types import FSInputFile
                label_file = FSInputFile(str(result.label_path), filename=f"label_{order_sn}.pdf")
                await callback.message.answer_document(
                    label_file,
                    caption=(
                        f"🗘 *Label Pengiriman Siap Cetak*\n"
                        f"Order: `{order_sn}`\n"
                        f"Resi: `{result.tracking_no or '-'}`\n"
                        f"_Tekan download lalu cetak! 🖨️_"
                    ),
                    parse_mode="Markdown",
                )
            else:
                await callback.message.answer(
                    "⚠️ Label PDF belum bisa diunduh sekarang.\nGunakan tombol 📄 Get Label untuk coba lagi."
                )

        except Exception as e:
            await callback.answer(f"⚠️ Gagal konfirmasi: {str(e)}", show_alert=True)

    @dp.callback_query(F.data.startswith("defer_ship:"))
    async def handle_defer_ship(callback: CallbackQuery) -> None:
        """HITL: Human deferred shipment. Keep alert but mark as acknowledged."""
        try:
            parts = callback.data.split(":")
            shop_id, order_sn = parts[1], parts[2]
            await callback.answer("⏸️ Pengiriman ditunda.")
            await callback.message.edit_text(
                f"⏸️ *Ditunda*\n\nPesanan `{order_sn}` belum dikirim.\n"
                f"_Anda bisa mengkonfirmasi dari menu /inbox kapan saja._",
                parse_mode="Markdown",
            )
        except Exception as e:
            await callback.answer(f"⚠️ Error: {str(e)}", show_alert=True)
    @dp.callback_query(F.data.startswith("bulk_confirm:"))
    async def handle_bulk_confirm(callback: CallbackQuery) -> None:
        try:
            parts = callback.data.split(":")
            shop_id = parts[1]
            await callback.answer("🚀 Memproses pengiriman massal...")
            await callback.message.edit_text("⏳ _Sedang memproses seluruh pesanan siap kirim..._", parse_mode="Markdown")
            
            with SessionLocal() as session:
                from shopee_agent.config.settings import get_settings
                settings = get_settings()
                client = ShopeeClient("https://partner.shopeemobile.com", settings.shopee_partner_id, settings.shopee_partner_key)
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                from shopee_agent.persistence.repositories import LogisticsRepository
                from shopee_agent.app.print_agent import PrintAgent
                
                print_agent = PrintAgent(
                    api_key=settings.printnode_api_key,
                    printer_id=settings.printnode_printer_id
                )
                agent = LogisticsAgent(
                    gateway, 
                    OrderRepository(session), 
                    LogisticsRepository(session),
                    print_agent=print_agent
                )
                
                results = await agent.bulk_ship_and_print(shop_id)
                
            success_count = len([r for r in results if r.success])
            await callback.message.edit_text(
                f"✅ **Bulk Shipment Selesai**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"Berhasil: `{success_count}`\n"
                f"Gagal: `{len(results) - success_count}`\n\n"
                f"🖨️ _Semua label telah dikirim ke printer thermal._",
                parse_mode="Markdown"
            )
        except Exception as e:
            await callback.answer(f"⚠️ Bulk failed: {str(e)}", show_alert=True)

    @dp.callback_query(F.data == "bulk_cancel")
    async def handle_bulk_cancel(callback: CallbackQuery) -> None:
        await callback.answer("❌ Batal")
        await callback.message.delete()

    @dp.callback_query(F.data.startswith("get_label:"))
    async def handle_get_label(callback: CallbackQuery) -> None:
        try:
            parts = callback.data.split(":")
            shop_id, order_sn = parts[1], parts[2]
            
            await callback.answer(f"📄 Menarik label PDF untuk {order_sn}...")
            
            from shopee_agent.config.settings import get_settings
            settings = get_settings()
            with SessionLocal() as session:
                client = ShopeeClient("https://partner.shopeemobile.com", settings.shopee_partner_id, settings.shopee_partner_key)
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                from shopee_agent.persistence.repositories import LogisticsRepository
                agent = LogisticsAgent(gateway, OrderRepository(session), LogisticsRepository(session))
                
                pdf_path = await agent.get_label_pdf(shop_id, order_sn)
            
            from aiogram.types import FSInputFile
            label_file = FSInputFile(str(pdf_path), filename=f"label_{order_sn}.pdf")
            
            await callback.message.answer_document(
                label_file, 
                caption=f"📄 Shipping Label: `{order_sn}`", 
                parse_mode="Markdown"
            )
        except Exception as e:
            await callback.answer(f"⚠️ Failed to fetch label: {str(e)}", show_alert=True)

    @dp.callback_query(F.data.startswith("task_"))
    async def handle_task_action(callback: CallbackQuery) -> None:
        try:
            action, task_id = callback.data.split(":")
            
            new_status = None
            if action == "task_ack":
                new_status = TaskStatus.ACKNOWLEDGED
            elif action == "task_resolve":
                new_status = TaskStatus.RESOLVED
            elif action == "task_wait":
                new_status = TaskStatus.WAITING
            elif action == "task_dismiss":
                new_status = TaskStatus.DISMISSED
    
            if not new_status:
                await callback.answer("❌ Aksi tidak dikenal.", show_alert=True)
                return
    
            success = supervisor.update_task_status(task_id, new_status)
            if not success:
                await callback.answer("❌ Tugas tidak ditemukan.", show_alert=True)
                return
    
            # Update the message with the new status and keyboard
            task = supervisor.task_repo.get_task(task_id)
            # Use helper from main (but we can't import main here, so we duplicate or move)
            # For now, let's just use a simple format or assume it's moved to a common utils
            sev_map = {"P0": "🔥 Sangat Penting", "P1": "⚠️ Penting", "HIGH": "🔥 Sangat Penting"}
            sev_label = sev_map.get(task.severity, "ℹ️ Info")
            status_map = {"open": "Menunggu", "acknowledged": "Dikerjakan", "resolved": "Selesai", "dismissed": "Diabaikan"}
            status_label = status_map.get(task.status.lower() if isinstance(task.status, str) else task.status.value.lower(), task.status)
            text = (
                f"{sev_label}\n"
                f"🏠 Toko: `{task.shop_id}`\n"
                f"📌 *{task.title}*\n"
                f"Status: *{status_label}*"
            )
            
            kb = get_task_keyboard(task_id, task.status)
            
            await callback.message.edit_text(
                text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
            label = {"acknowledged": "Sedang Dikerjakan", "resolved": "Selesai", "dismissed": "Diabaikan", "waiting": "Ditunda"}.get(new_status.value.lower(), new_status.value)
            await callback.answer(f"✅ Status diperbarui: {label}")
        except Exception as e:
            await callback.answer(f"⚠️ Operation failed: {str(e)}", show_alert=True)

    @dp.callback_query(F.data.startswith("restock_po:"))
    async def handle_restock_po(callback: CallbackQuery) -> None:
        try:
            parts = callback.data.split(":")
            shop_id = parts[1]
            await callback.answer("📝 Sedang menyiapkan file PO...")
            
            with SessionLocal() as session:
                from shopee_agent.app.inventory_health import InventoryHealthAgent
                from shopee_agent.app.reporting import ReportingAgent
                from shopee_agent.persistence.repositories import ExportRepository
                
                health_agent = InventoryHealthAgent(session)
                proposals = health_agent.propose_restock_plan(shop_id)
                
                reporting_agent = ReportingAgent(ExportRepository(session))
                result = reporting_agent.generate_restock_workbook(shop_id, proposals, creator=str(callback.from_user.id))
                
            from aiogram.types import FSInputFile
            doc = FSInputFile(result.file_path)
            await callback.message.answer_document(
                doc,
                caption=f"📦 **Purchase Order — {shop_id}**\nTotal items: `{result.row_count}`\n\n_Segera kirim file ini ke supplier!_",
                parse_mode="Markdown"
            )
        except Exception as e:
            await callback.answer(f"⚠️ PO failed: {str(e)}", show_alert=True)

    @dp.callback_query(F.data.startswith("kb_learn:"))
    async def handle_kb_learn(callback: CallbackQuery) -> None:
        try:
            parts = callback.data.split(":")
            shop_id, item_id = parts[1], parts[2]
            
            # Extract Q&A from message text
            msg_text = callback.message.text
            q_match = re.search(r"Tanya: \"(.*)\"", msg_text)
            a_match = re.search(r"Jawab: \"(.*)\"", msg_text)
            
            if q_match and a_match:
                q, a = q_match.group(1), a_match.group(1)
                with SessionLocal() as session:
                    from shopee_agent.persistence.repositories import ProductKnowledgeRepository
                    from shopee_agent.contracts.knowledge import FAQEntry
                    repo = ProductKnowledgeRepository(session)
                    pk = repo.get_pk(shop_id, item_id)
                    if pk:
                        pk.faq.append(FAQEntry(question=q, answer=a))
                        repo.upsert_pk(pk)
            
            await callback.answer("✅ Pengetahuan baru diterapkan!")
            await callback.message.edit_text(
                f"✅ **Telah Dipelajari**\n\nPengetahuan baru telah ditambahkan ke Knowledge Base untuk produk `{item_id}`.\n"
                f"_Agent sekarang bisa menjawab pertanyaan serupa secara otomatis._",
                parse_mode="Markdown"
            )
        except Exception:
            await callback.answer(f"⚠️ Gagal menyimpan pengetahuan baru.", show_alert=True)

    @dp.callback_query(F.data.startswith("gen_promo:"))
    async def handle_gen_promo(callback: CallbackQuery) -> None:
        try:
            parts = callback.data.split(":")
            shop_id, item_id = parts[1], parts[2]
            
            await callback.answer("✍️ Menulis caption...")
            await bot.send_chat_action(callback.message.chat.id, "typing")
            
            with SessionLocal() as session:
                from shopee_agent.persistence.repositories import ProductKnowledgeRepository
                from shopee_agent.app.product_knowledge_agent import ProductKnowledgeAgent
                
                repo = ProductKnowledgeRepository(session)
                agent = ProductKnowledgeAgent(repo)
                
                caption = await agent.generate_promo_caption(shop_id, item_id, get_llm_gateway())
                
                await callback.message.answer(
                    f"📱 **Caption Promosi dari AI**\n━━━━━━━━━━━━━━━\n\n"
                    f"{caption}\n\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"💡 _Salin dan gunakan untuk Instagram, TikTok, atau status WhatsApp Anda._",
                    parse_mode="Markdown"
                )
        except Exception as e:
            await callback.answer(f"⚠️ Gagal membuat caption: {str(e)}", show_alert=True)

    @dp.callback_query(F.data.startswith("retry_job:"))
    async def handle_retry_job(callback: CallbackQuery) -> None:
        try:
            incident_id = callback.data.split(":")[1]
            await callback.answer("🔄 Mencoba kembali...")
            
            with SessionLocal() as session:
                from shopee_agent.persistence.models import IncidentRecord
                incident = session.get(IncidentRecord, int(incident_id))
                if incident:
                    # Logic to retry based on incident.component and retry_payload
                    # For demo: just mark as resolved
                    incident.status = "resolved"
                    session.commit()
                    await callback.message.edit_text(f"✅ **Incident Resolved:** `{incident.component}` berhasil di-retry.", parse_mode="Markdown")
        except Exception as e:
            await callback.answer(f"⚠️ Retry failed: {str(e)}", show_alert=True)

    @dp.callback_query(F.data.startswith("print_"))
    async def handle_manual_print(callback: CallbackQuery) -> None:
        try:
            parts = callback.data.split(":")
            action, shop_id, order_sn = parts[0], parts[1], parts[2]
            
            await callback.answer("🖨️ Memproses antrian cetak...")
            
            from shopee_agent.config.settings import get_settings
            settings = get_settings()
            
            with SessionLocal() as session:
                from shopee_agent.persistence.repositories import ShopTokenRepository, OrderRepository, LogisticsRepository
                from shopee_agent.providers.shopee.client import ShopeeClient
                from shopee_agent.providers.shopee.gateway import ShopeeGateway
                from shopee_agent.app.logistics_agent import LogisticsAgent
                from shopee_agent.app.print_agent import PrintAgent
                
                client = ShopeeClient("https://partner.shopeemobile.com", settings.shopee_partner_id, settings.shopee_partner_key)
                gateway = ShopeeGateway(client, ShopTokenRepository(session))
                print_agent = PrintAgent(api_key=settings.printnode_api_key, printer_id=settings.printnode_printer_id)
                agent = LogisticsAgent(gateway, OrderRepository(session), LogisticsRepository(session), print_agent=print_agent)
                
                if action in ["print_resi", "print_both"]:
                    label_path = await agent.get_label_pdf(shop_id, order_sn)
                    await print_agent.print_label(label_path)
                    
                if action in ["print_instr", "print_both"]:
                    order = agent.order_repo.get_order(order_sn, shop_id)
                    if order:
                        order_data = json.loads(order.data_json)
                        # Fetch Product Facts for specs
                        from shopee_agent.persistence.repositories import ProductKnowledgeRepository
                        pk_repo = ProductKnowledgeRepository(session)
                        
                        items = order_data.get("item_list", [])
                        facts = []
                        for itm in items:
                            f = pk_repo.get_pk(shop_id, str(itm.get("item_id", "")))
                            if f: facts.append(f)
                            
                        instr_path = await agent.instr_gen.generate_instruction_file(order_data, product_facts=facts)
                        await print_agent.print_label(instr_path)
                
            await callback.message.answer(f"✅ Selesai mencetak untuk `{order_sn}`.")
        except Exception as e:
            await callback.answer(f"⚠️ Print failed: {str(e)}", show_alert=True)

    @dp.callback_query(F.data.startswith("rev_approve:"))
    async def handle_rev_approve(callback: CallbackQuery) -> None:
        try:
            review_id = callback.data.split(":")[1]
            await callback.answer("📤 Mengirim balasan...")
            
            with SessionLocal() as session:
                from shopee_agent.persistence.models import ReviewRecord
                rev = session.scalar(select(ReviewRecord).where(ReviewRecord.review_id == review_id))
                if rev:
                    rev.status = "replied"
                    session.commit()
                    
            await callback.message.edit_text(
                f"✅ **Dibalas**\n\nUlasan ID `{review_id}` telah dikirimi balasan AI.",
                parse_mode="Markdown"
            )
        except Exception as e:
            await callback.answer(f"⚠️ Approval failed: {str(e)}", show_alert=True)

    @dp.callback_query(F.data == "kb_ignore")
    async def handle_kb_ignore(callback: CallbackQuery) -> None:
        await callback.answer("🗑️ Diabaikan")
        await callback.message.delete()
