from datetime import UTC, datetime, timedelta

from shopee_agent.app.queue import OutboxQueue
from shopee_agent.config.settings import Settings
from shopee_agent.persistence.session import make_session_factory


from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.contracts.operations import OperatorTask, TaskSeverity
from shopee_agent.persistence.repositories import OperatorTaskRepository

def run_once() -> bool:
    settings = Settings()
    factory = make_session_factory(settings.database_url)
    with factory() as session:
        queue = OutboxQueue(session)
        action = queue.claim_next(now=datetime.now(UTC), lease_for=timedelta(seconds=30))
        if action is None:
            return False
            
        # Execute Action
        if action.action_type == "create_operator_task":
            supervisor = OperationsSupervisorAgent(OperatorTaskRepository(session))
            task_data = action.payload
            reason = task_data.get("reason", "unknown")
            event_type = task_data.get("event_type", "unknown")
            
            supervisor.create_task(OperatorTask(
                task_id=f"evt_{action.subject_id}",
                category="system",
                subject_id=action.subject_id,
                severity=TaskSeverity.P2,
                title=f"Unhandled Event: {event_type}",
                summary=f"Event {action.subject_id} needs human review. Reason: {reason}",
            ))
            
        queue.mark_done(action.outbox_id)
        session.commit()
        return True
