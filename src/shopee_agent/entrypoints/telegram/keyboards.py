from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_task_keyboard(task_id: str, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if status == "open":
        builder.button(text="Mulai Kerjakan 🏃", callback_data=f"task_ack:{task_id}")
        builder.button(text="Selesai ✅", callback_data=f"task_resolve:{task_id}")
    elif status == "acknowledged":
        builder.button(text="Selesai ✅", callback_data=f"task_resolve:{task_id}")
        builder.button(text="Tunda Dulu ⏳", callback_data=f"task_wait:{task_id}")
        
    builder.button(text="Abaikan 🗑️", callback_data=f"task_dismiss:{task_id}")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_pagination_keyboard(page: int, has_next: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text="⬅️ Sebelumnya", callback_data=f"inbox_page:{page - 1}")
    if has_next:
        builder.button(text="Selanjutnya ➡️", callback_data=f"inbox_page:{page + 1}")
    builder.adjust(2)
    return builder.as_markup()


def get_shop_selection_keyboard(shop_ids: list[str], action_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sid in shop_ids:
        builder.button(text=f"Toko: {sid}", callback_data=f"{action_prefix}:{sid}")
    builder.adjust(1)
    return builder.as_markup()

def get_logistics_keyboard(order_sn: str, shop_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Atur Pengiriman", callback_data=f"ship_order:{shop_id}:{order_sn}")
    builder.button(text="📄 Cetak Resi", callback_data=f"get_label:{shop_id}:{order_sn}")
    builder.adjust(2)
    return builder.as_markup()


def get_ship_approval_keyboard(order_sn: str, shop_id: str) -> InlineKeyboardMarkup:
    """HITL approval keyboard for SLA-risk orders."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Konfirmasi Kirim", callback_data=f"confirm_ship:{shop_id}:{order_sn}")
    builder.button(text="❌ Tunda Dulu", callback_data=f"defer_ship:{shop_id}:{order_sn}")
    builder.adjust(2)
    return builder.as_markup()

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📥 Tugas Hari Ini"), KeyboardButton(text="📅 Jadwal & Agenda")],
        [KeyboardButton(text="📈 Laporan Penjualan"), KeyboardButton(text="⭐ Ulasan Pembeli")],
        [KeyboardButton(text="📦 Cek Stok"), KeyboardButton(text="💰 Uang Masuk")],
        [KeyboardButton(text="🏪 Daftar Toko"), KeyboardButton(text="⚙️ Pengaturan")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_post_sync_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Cek Tugas", callback_data="view_inbox")
    builder.button(text="📊 Cek Laporan", callback_data="view_dashboard")
    builder.adjust(2)
    return builder.as_markup()

def get_chat_keyboard(chat_id: str, shop_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Minta AI Balas", callback_data=f"chat_draft:{shop_id}:{chat_id}")
    builder.button(text="✅ Balas Cepat (Oke!)", callback_data=f"chat_quick_ok:{shop_id}:{chat_id}")
    builder.button(text="👤 Saya Balas Sendiri", callback_data=f"chat_escalate:{shop_id}:{chat_id}")
    builder.adjust(2, 1)
    return builder.as_markup()

def get_print_options_keyboard(order_sn: str, shop_id: str) -> InlineKeyboardMarkup:
    """Manual print triggers for workers."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Print Resi", callback_data=f"print_resi:{shop_id}:{order_sn}")
    builder.button(text="📋 Print Instruksi", callback_data=f"print_instr:{shop_id}:{order_sn}")
    builder.button(text="✨ Print Keduanya", callback_data=f"print_both:{shop_id}:{order_sn}")
    builder.adjust(2, 1)
    return builder.as_markup()
def get_audit_period_keyboard(year: int) -> InlineKeyboardMarkup:
    """Select month for audit rekap."""
    builder = InlineKeyboardBuilder()
    months = [
        ("Jan", 1), ("Feb", 2), ("Mar", 3), ("Apr", 4),
        ("Mei", 5), ("Jun", 6), ("Jul", 7), ("Agu", 8),
        ("Sep", 9), ("Okt", 10), ("Nov", 11), ("Des", 12)
    ]
    for name, m in months:
        builder.button(text=name, callback_data=f"audit_month:{year}:{m}")
    
    builder.button(text=f"Change Year ({year})", callback_data=f"audit_year_sel")
    builder.adjust(4, 4, 4, 1)
    return builder.as_markup()

def get_audit_result_keyboard(excel_id: str, gsheets_url: str) -> InlineKeyboardMarkup:
    """Post-audit action buttons."""
    builder = InlineKeyboardBuilder()
    if gsheets_url:
        builder.button(text="☁️ Buka di Google Sheets", url=gsheets_url)
    builder.button(text="📩 Kirim Ulang Excel", callback_data=f"audit_resend:{excel_id}")
    builder.adjust(1)
    return builder.as_markup()
