from dataclasses import dataclass, field


@dataclass
class FakeTelegramGateway:
    sent_messages: list[tuple[str, str]] = field(default_factory=list)

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent_messages.append((chat_id, text))
