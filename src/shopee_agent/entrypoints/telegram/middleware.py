from typing import Any, Callable, Dict, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from shopee_agent.config.settings import Settings
from shopee_agent.persistence.session import SessionLocal
from shopee_agent.persistence.repositories import ActivityLogRepository

import time

class AdminLockdownMiddleware(BaseMiddleware):
    # In-memory rate limiter state
    user_timestamps: Dict[str, list[float]] = {}
    RATE_LIMIT_SECONDS = 1.0
    RATE_LIMIT_MAX = 3

    def __init__(self, settings: Settings):
        self.settings = settings
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = str(event.from_user.id)
        elif isinstance(event, CallbackQuery):
            user_id = str(event.from_user.id)

        if not user_id:
            return await handler(event, data)

        # Rate Limiting
        now = time.time()
        timestamps = self.user_timestamps.get(user_id, [])
        # Remove timestamps older than our window
        timestamps = [t for t in timestamps if now - t < self.RATE_LIMIT_SECONDS]
        
        if len(timestamps) >= self.RATE_LIMIT_MAX:
            # Drop silently to prevent DB overload from spam
            return None
            
        timestamps.append(now)
        self.user_timestamps[user_id] = timestamps

        # Check against admin_chat_id or allowed_list
        allowed_ids = [self.settings.admin_chat_id]
        if self.settings.telegram_allowed_user_ids:
            allowed_ids.extend(self.settings.telegram_allowed_user_ids.split(","))

        if user_id not in allowed_ids:
            # Log intruder
            with SessionLocal() as session:
                log_repo = ActivityLogRepository(session)
                log_repo.log(
                    shop_id="system",
                    activity_type="unauthorized_access",
                    message=f"Intruder blocked: User {user_id} tried to access {type(event).__name__}",
                    severity="warning"
                )
            
            if isinstance(event, Message):
                await event.answer("⚠️ **Akses Ditolak**\nAnda tidak memiliki izin untuk mengoperasikan bot ini. Kejadian ini telah dicatat.", parse_mode="Markdown")
            return

        return await handler(event, data)
