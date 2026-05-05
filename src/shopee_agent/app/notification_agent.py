from shopee_agent.persistence.repositories import OperatorTaskRepository, OperatorTaskData


class NotificationAgent:
    def __init__(self, task_repo: OperatorTaskRepository) -> None:
        self.task_repo = task_repo

    def get_urgent_alerts(self) -> list[OperatorTaskData]:
        """Fetch tasks that need to be notified but haven't been."""
        return self.task_repo.get_pending_notifications()

    def format_alert_message(self, task: OperatorTaskData) -> str:
        icon = "🔴" if task.severity == "P0" else "🟠"
        text = (
            f"{icon} **URGENT ALERT: {task.severity}**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🏪 Shop: `{task.shop_id}`\n"
            f"📌 Task: *{task.title}*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{task.summary}\n\n"
            f"Use `/inbox` to take action."
        )
        return text

    async def notify_incident(self, bot, chat_id: str, incident: dict):
        """Notifies admin of a system failure (Logic only)."""
        text = (
            f"🚨 **System Incident Detected**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Component: `{incident['component']}`\n"
            f"Error: `{incident['error']}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 _System failure logged and ready for review._"
        )
        # Note: Keyboard building moved to dispatcher level
        await bot.send_message(chat_id, text, parse_mode="Markdown")

    def mark_as_notified(self, task_id: str) -> None:
        self.task_repo.mark_notified(task_id)
