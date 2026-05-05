from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_task_keyboard(task_id: str, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if status == "open":
        builder.button(text="Ack", callback_data=f"task_ack:{task_id}")
        builder.button(text="Resolve", callback_data=f"task_resolve:{task_id}")
    elif status == "acknowledged":
        builder.button(text="Resolve", callback_data=f"task_resolve:{task_id}")
        builder.button(text="Waiting", callback_data=f"task_wait:{task_id}")
        
    builder.button(text="Dismiss", callback_data=f"task_dismiss:{task_id}")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_pagination_keyboard(page: int, has_next: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text="⬅️ Prev", callback_data=f"inbox_page:{page - 1}")
    if has_next:
        builder.button(text="Next ➡️", callback_data=f"inbox_page:{page + 1}")
    builder.adjust(2)
    return builder.as_markup()


def get_shop_selection_keyboard(shop_ids: list[str], action_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sid in shop_ids:
        builder.button(text=f"Shop: {sid}", callback_data=f"{action_prefix}:{sid}")
    builder.adjust(1)
    return builder.as_markup()

def get_logistics_keyboard(order_sn: str, shop_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Ship Order", callback_data=f"ship_order:{shop_id}:{order_sn}")
    builder.button(text="📄 Get Label", callback_data=f"get_label:{shop_id}:{order_sn}")
    builder.adjust(2)
    return builder.as_markup()


def get_ship_approval_keyboard(order_sn: str, shop_id: str) -> InlineKeyboardMarkup:
    """HITL approval keyboard for SLA-risk orders."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Konfirmasi Kirim", callback_data=f"confirm_ship:{shop_id}:{order_sn}")
    builder.button(text="❌ Tunda", callback_data=f"defer_ship:{shop_id}:{order_sn}")
    builder.adjust(2)
    return builder.as_markup()

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📥 Inbox"), KeyboardButton(text="📋 Agenda")],
        [KeyboardButton(text="📈 Analytics"), KeyboardButton(text="⭐ Reviews")],
        [KeyboardButton(text="📦 Inventory"), KeyboardButton(text="💰 Finance")],
        [KeyboardButton(text="🏪 Shops"), KeyboardButton(text="⚙️ Settings")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_post_sync_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 View Inbox", callback_data="view_inbox")
    builder.button(text="📊 View Dashboard", callback_data="view_dashboard")
    builder.adjust(2)
    return builder.as_markup()

def get_chat_keyboard(chat_id: str, shop_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Draft AI", callback_data=f"chat_draft:{shop_id}:{chat_id}")
    builder.button(text="✅ Quick OK", callback_data=f"chat_quick_ok:{shop_id}:{chat_id}")
    builder.button(text="⚠️ Escalate", callback_data=f"chat_escalate:{shop_id}:{chat_id}")
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
