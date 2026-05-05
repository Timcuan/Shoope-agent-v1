from datetime import datetime, UTC

import pytest

from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.contracts.operations import OperatorTask, TaskSeverity, TaskStatus
from shopee_agent.persistence.repositories import OperatorTaskRepository


def test_operations_supervisor_task_lifecycle(db_session) -> None:
    repo = OperatorTaskRepository(db_session)
    supervisor = OperationsSupervisorAgent(repo)

    # 1. Create a task
    task = OperatorTask(
        task_id="task_1",
        category="order",
        subject_id="250501XYZ",
        severity=TaskSeverity.P0,
        title="Late Shipment Risk",
        summary="Order is close to SLA breach",
        due_at=datetime.now(UTC),
    )
    supervisor.create_task(task)

    # 2. Verify it appears in agenda and inbox
    agenda = supervisor.get_agenda()
    assert len(agenda) == 1
    assert agenda[0].task_id == "task_1"
    assert agenda[0].status == "open"

    inbox = supervisor.get_inbox_page()
    assert len(inbox) == 1

    # 3. Update status
    success = supervisor.update_task_status("task_1", TaskStatus.ACKNOWLEDGED)
    assert success is True

    # 4. Verify status is updated
    updated_task = repo.get_task("task_1")
    assert updated_task.status == "acknowledged"

    # 5. Resolve task and verify it is removed from agenda
    supervisor.update_task_status("task_1", TaskStatus.RESOLVED)
    agenda = supervisor.get_agenda()
    assert len(agenda) == 0


def test_operations_supervisor_ranking(db_session) -> None:
    repo = OperatorTaskRepository(db_session)
    supervisor = OperationsSupervisorAgent(repo)

    supervisor.create_task(OperatorTask(
        task_id="t1", category="general", subject_id="s1", severity=TaskSeverity.P2, title="Medium", summary=""
    ))
    supervisor.create_task(OperatorTask(
        task_id="t2", category="general", subject_id="s2", severity=TaskSeverity.P0, title="Critical", summary=""
    ))
    supervisor.create_task(OperatorTask(
        task_id="t3", category="general", subject_id="s3", severity=TaskSeverity.P1, title="High", summary=""
    ))

    agenda = supervisor.get_agenda()
    # Should be sorted by severity: P0, P1, P2
    assert agenda[0].task_id == "t2"
    assert agenda[1].task_id == "t3"
    assert agenda[2].task_id == "t1"
