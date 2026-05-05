from shopee_agent.contracts.operations import OperatorTask, TaskStatus
from shopee_agent.persistence.repositories import OperatorTaskData, OperatorTaskRepository, ActivityLogRecord


class OperationsSupervisorAgent:
    def __init__(self, task_repo: OperatorTaskRepository, session=None) -> None:
        self.task_repo = task_repo
        self.session = session

    def create_task(self, task: OperatorTask) -> None:
        data = OperatorTaskData(
            task_id=task.task_id,
            category=task.category,
            subject_id=task.subject_id,
            shop_id=task.shop_id,
            severity=task.severity.value,
            title=task.title,
            summary=task.summary,
            status=task.status.value,
            due_at=task.due_at,
        )
        self.task_repo.upsert_task(data)
        self.log_activity(
            shop_id=task.shop_id,
            activity_type="TASK_CREATED",
            message=f"Tugas baru dibuat: {task.title}",
            severity=task.severity.value.lower()
        )

    def log_activity(self, shop_id: str, activity_type: str, message: str, severity: str = "info") -> None:
        """Central method to log significant events to the DB for dashboard visibility."""
        if not self.session:
            return
        
        log = ActivityLogRecord(
            shop_id=shop_id,
            activity_type=activity_type,
            message=message,
            severity=severity
        )
        self.session.add(log)
        self.session.flush()

    def update_task_status(self, task_id: str, new_status: TaskStatus) -> bool:
        data = self.task_repo.get_task(task_id)
        if not data:
            return False
        
        data.status = new_status.value
        self.task_repo.upsert_task(data)
        
        self.log_activity(
            shop_id=data.shop_id,
            activity_type="TASK_UPDATED",
            message=f"Status tugas '{data.title}' diubah ke {new_status.value}",
            severity="info"
        )
        return True

    def get_agenda(self) -> list[OperatorTaskData]:
        # Return the most critical tasks first
        return self.task_repo.get_open_tasks(limit=5, offset=0)

    def get_inbox_page(self, page: int = 1, per_page: int = 5) -> list[OperatorTaskData]:
        offset = (page - 1) * per_page
        return self.task_repo.get_open_tasks(limit=per_page, offset=offset)

    def find_tasks_by_subject(self, subject_id: str) -> list[OperatorTaskData]:
        # Simple local search skeleton for /find
        # Production would use a more robust search index across multiple tables
        all_tasks = self.task_repo.get_open_tasks(limit=100)
        return [t for t in all_tasks if subject_id.lower() in t.subject_id.lower() or subject_id.lower() in t.title.lower()]
