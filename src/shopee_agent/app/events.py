from dataclasses import dataclass

from shopee_agent.app.decisions import DecisionEngine
from shopee_agent.app.workflows import WorkflowEngine
from shopee_agent.contracts.decisions import Decision
from shopee_agent.contracts.events import EventEnvelope
from shopee_agent.persistence.repositories import (
    DecisionRepository, EventRepository, InsertEventResult, WorkflowRepository
)


from shopee_agent.app.queue import OutboxQueue

@dataclass(frozen=True)
class IngestResult:
    event: InsertEventResult
    decision: Decision


class EventIngestService:
    def __init__(
        self,
        event_repo: EventRepository,
        decision_engine: DecisionEngine,
        decision_repo: DecisionRepository,
        workflow_engine: WorkflowEngine,
        workflow_repo: WorkflowRepository,
        outbox_queue: OutboxQueue | None = None,
    ) -> None:
        self.event_repo = event_repo
        self.decision_engine = decision_engine
        self.decision_repo = decision_repo
        self.workflow_engine = workflow_engine
        self.workflow_repo = workflow_repo
        self.outbox_queue = outbox_queue

    def ingest(self, event: EventEnvelope) -> IngestResult:
        # 1. Save Event
        res = self.event_repo.insert_if_new(event)
        
        # 2. Make Decision & Save
        decision = self.decision_engine.decide(event)
        self.decision_repo.save_decision(decision)
        
        # 3. Start Workflow & Save
        workflow = self.workflow_engine.start_for_event(event)
        self.workflow_repo.upsert_workflow(workflow)
        
        # 4. Enqueue Action
        if self.outbox_queue and decision.action_request:
            self.outbox_queue.enqueue(decision.action_request)
        
        return IngestResult(event=res, decision=decision)
