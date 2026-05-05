from typing import Protocol

class NotificationProvider(Protocol):
    async def send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown"):
        ...
