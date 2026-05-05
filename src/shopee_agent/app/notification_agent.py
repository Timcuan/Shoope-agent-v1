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

    async def dispatch_pending_alerts(self, bot, chat_id: str) -> None:
        """Fetch pending alerts and dispatch them to Telegram without spamming."""
        alerts = self.get_urgent_alerts()
        if not alerts:
            return

        # Anti-Spam Aggregation
        if len(alerts) > 3:
            # Batch summary instead of individual messages
            high_pri = sum(1 for a in alerts if a.severity in ["P0", "P1", "HIGH"])
            text = (
                f"⚠️ **Multiple Alerts Detected ({len(alerts)})**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🔴 High Priority: `{high_pri}`\n"
                f"🟠 Standard Tasks: `{len(alerts) - high_pri}`\n"
                f"━━━━━━━━━━━━━━━\n"
                f"Banyak tugas menumpuk. Gunakan `/inbox` untuk melihat dan menyelesaikan."
            )
            await bot.send_message(chat_id, text, parse_mode="Markdown")
            for alert in alerts:
                self.mark_as_notified(alert.task_id)
            return

        # Normal Dispatch
        for alert in alerts:
            msg = self.format_alert_message(alert)
            from shopee_agent.entrypoints.telegram.keyboards import get_task_keyboard
            kb = get_task_keyboard(alert.task_id, alert.status)
            await bot.send_message(chat_id, msg, reply_markup=kb, parse_mode="Markdown")
            self.mark_as_notified(alert.task_id)
