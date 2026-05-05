from aiogram import Bot
from shopee_agent.contracts.notifications import NotificationProvider

class TelegramNotificationProvider(NotificationProvider):
    def __init__(self, token: str):
        self.bot = Bot(token=token)

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown"):
        await self.bot.send_message(chat_id, text, parse_mode=parse_mode)
        # We might want to keep the bot session open or close it
        # For simple use, closing is safer if infrequent
        await self.bot.session.close()
