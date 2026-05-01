# Shopee Agentic Automation Design

Date: 2026-05-01
Status: Draft for user review
Source blueprint: `/Users/aaa/Downloads/shopee-agentic-blueprint.md`

## Purpose

Build a staged agentic operating system for Shopee shop operations. The system automates repetitive work across orders, shipping documents, finance tracking, inventory alerts, customer chat triage, and operator escalation. It keeps irreversible, reputational, or financially sensitive decisions under human control.

The target is a VPS-hosted service with Telegram as the only operator interface. No web dashboard is included in the initial design.

## Confirmed Decisions

- Product direction: full operating system built in phases.
- Integration mode: hybrid Shopee API plus simulator.
- Deployment target: VPS.
- Operator interface: Telegram only.
- Chat automation level: moderate.
- Chat action mode: auto-send for low-risk, approval for medium-risk.
- Backend stack: Python FastAPI, because it matches the blueprint and keeps agent, scheduler, Telegram bot, and database work straightforward on a VPS.
- Database path: portable design, start with SQLite WAL, migrate to PostgreSQL when needed.
- LLM path: provider-agnostic adapter.
- Logistics scope: auto-generate shipping documents for eligible orders; do not auto-ship full workflows in phase one.

## Recommended Architecture

Use a modular monolith service in the first production version. One backend runs the API ingress, event router, specialist agents, scheduler, Telegram bot, persistence layer, and action executor. Modules have clear boundaries so high-volume parts can later move into separate workers without redesigning the system.

This is the best fit because the first target is one VPS and Telegram-only operation. A distributed worker architecture would add queue and deployment complexity before the system needs it.

High-level flow:

```text
Shopee Webhook / Polling / Simulator
        |
        v
Ingress + Signature Verification
        |
        v
Normalized Event Log
        |
        v
Event Router
        |
        +--> Order Agent
        +--> Logistics Agent
        +--> Finance Agent
        +--> Inventory Agent
        +--> Chat Agent
        +--> Return/Dispute Agent
        +--> Sync/Recovery Agent
        |
        v
Policy Engine + Human Gate
        |
        +--> Safe Auto Action
        +--> Telegram Approval
        +--> Telegram Escalation
```

The system processes events first and performs actions second. Every webhook, polling result, simulator event, and Telegram command becomes a normalized event with a correlation id. Agents consume those events idempotently. This makes replay, audit, drift repair, and incident analysis possible.

## Runtime Shape

The initial runtime should use:

- FastAPI for webhook ingress and internal API surfaces.
- Async HTTP client for Shopee calls.
- SQLite WAL for the first deployment.
- Repository interfaces that keep the schema portable to PostgreSQL.
- Telegram bot as the control plane.
- Scheduler for reconciliation, token refresh, daily summaries, and retry processing.
- Local archive folder for shipping documents, raw payload evidence, and exports.
- Docker Compose or systemd. Docker Compose is preferred if dependency isolation matters; systemd is preferred if the VPS should remain minimal.

The design should keep Shopee, LLM, Telegram, and database access behind interfaces. Business agents must not call provider SDKs directly.

## Core Modules

### Ingress

Ingress receives Shopee webhooks, simulator events, polling results, and Telegram commands. It verifies signatures where applicable, normalizes payloads, rate limits public routes, assigns event ids, and writes dead-letter records for invalid payloads.

Ingress must not contain heavy business logic.

### Event Store

Event Store is the append-first audit layer. It stores raw payloads, normalized event type, source, checksum, status, retry count, and correlation id. It provides deduplication and replay support.

### Event Router

Event Router maps normalized events to one or more specialist agents. A single order event can trigger order state updates, stock reservation, finance ledger updates, label eligibility checks, and Telegram notifications.

### Policy Engine

Policy Engine decides whether a proposed action can run automatically, needs approval, must be escalated, or must be rejected. It evaluates risk tier, confidence, action type, shop policy, conversation mode, and operator override state.

Policy rules must live in readable configuration or typed rule definitions, not inside prompts.

### Action Executor

Action Executor is the only module allowed to perform side effects. It sends Shopee API calls, sends Telegram messages, sends chat replies, generates shipping documents, writes evidence files, and records action results.

Agents return decisions and action requests. They do not execute provider calls directly.

### Shopee Gateway

Shopee Gateway exposes a stable interface over Shopee real API calls and simulator behavior. It handles signed requests, token refresh, order APIs, logistics APIs, product APIs, settlement data, and chat APIs if available.

The simulator must implement the same interface so workflows can be tested without live credentials.

### LLM Gateway

LLM Gateway exposes provider-agnostic structured operations:

- classify chat intent.
- score sentiment and risk.
- summarize customer context.
- draft safe responses.
- summarize return or dispute evidence.

The first implementation can use Gemini, OpenAI, or another provider through the same interface. The rest of the system must not depend on a provider-specific SDK or prompt format.

## Specialist Agents

### Order Agent

Order Agent owns local order lifecycle state. It upserts orders, parses items, tracks status transitions, computes derived fields, links buyers, and triggers finance, inventory, logistics, and notification workflows.

It treats Shopee order detail as the source of truth, while local state remains the operational cache and audit surface.

### Logistics Agent

Logistics Agent handles shipping document readiness and generation. In phase one, it may auto-generate shipping documents for eligible orders. It must not auto-ship full workflows.

Eligibility checks include order status, payment/shipment completeness, SKU validity, absence of custom request flags, and absence of high-risk order markers.

### Finance Agent

Finance Agent creates operational ledger records from order and settlement data. It stores estimated fees, final escrow values, commissions, service fees, shipping fees, and settlement deltas.

It must not hardcode seller fee formulas as final truth. API-provided values are authoritative when available. Internal formulas are only estimates until final data arrives.

### Inventory Agent

Inventory Agent maintains product and stock cache, reserved stock, released stock, sold stock, and low-stock alerts. It avoids reading live product APIs on every chat or order path unless a refresh is explicitly needed.

### Chat Agent

Chat Agent classifies intent, sentiment, risk, urgency, and confidence. It retrieves relevant order, tracking, product, FAQ, and policy context. It proposes either a template response, LLM-assisted draft, approval request, or escalation.

Moderate automation rules:

- Low-risk status, tracking, stock, and policy questions may auto-send.
- Mild complaints may auto-send only when policy allows and context is clear.
- Medium-risk drafts require Telegram approval.
- High-risk conversations freeze automation and escalate.

### Return and Dispute Agent

Return and Dispute Agent triages sensitive cases. It summarizes evidence, computes risk, and recommends next steps. It does not make final accept, reject, refund, or compensation decisions in phase one.

### Sync and Recovery Agent

Sync and Recovery Agent protects data integrity. It runs scheduled reconciliation, detects state drift, refreshes tokens, replays recoverable dead-letter events, and alerts operators when recovery fails.

## Decision Contract

Each agent returns a structured decision:

```text
Decision
- agent_name
- subject_type: order | chat | return | finance | inventory | system
- subject_id
- risk_tier: low | medium | high
- confidence
- recommended_action
- reason_codes
- requires_human
- action_payload
- audit_summary
```

This contract keeps Telegram approvals explainable. Operators should see why the system wants to act, what evidence it used, and what risk tier it assigned.

## Data Model

Core tables:

| Table | Purpose |
| --- | --- |
| `events` | Raw and normalized event log for idempotency, replay, and audit. |
| `orders` | Local source of operational order state. |
| `order_items` | Item and variation details for analytics, stock, and customer context. |
| `shipments` | Logistics channel, tracking number, document status, and label evidence. |
| `finance_ledger` | Estimated and final fees, escrow, settlement, and anomaly flags. |
| `products` | Product, SKU, price, and stock cache. |
| `stock_movements` | Reserved, released, sold, and manual stock changes. |
| `customers` | Buyer mapping, order history, and risk markers. |
| `conversations` | Conversation mode, latest intent, temperature, and operator state. |
| `chat_messages` | Inbound and outbound messages, intent, confidence, reply mode, and audit state. |
| `returns_disputes` | Case reason, evidence, recommendation, and decision state. |
| `action_requests` | Pending, approved, rejected, and executed action payloads. |
| `tokens` | Token state, expiry, refresh status, and shop binding. |
| `sync_state` | Polling cursors, last successful sync, and drift markers. |
| `operator_audit` | Telegram approvals, overrides, and manual commands. |

Derived fields:

- `order_risk_score`.
- `customer_temperature`.
- `agent_confidence`.
- `requires_human`.
- `financial_delta`.
- `conversation_mode`.

## Event Processing Flow

```text
1. Event arrives from webhook, polling, simulator, or Telegram.
2. Ingress validates and normalizes the payload.
3. Event Store deduplicates by source event id, shop id, event type, and checksum.
4. Router dispatches the event to relevant agents.
5. Agents read local state and provider context if needed.
6. Agents emit structured decisions.
7. Policy Engine evaluates risk, confidence, action type, and shop rules.
8. Action Request is created.
9. Action Executor performs allowed side effects.
10. State tables are upserted and audit logs are written.
```

All writes to operational state should be upserts or idempotent inserts. Event arrival order must not be trusted.

## Chat State Machine

Conversations use a state machine:

```text
normal -> sensitive -> frozen -> human_only
```

- `normal`: status, tracking, stock, and policy questions can be answered automatically if confidence is high.
- `sensitive`: mild complaint or delay context; safe template or approval flow.
- `frozen`: return, dispute, threat, abusive tone, refund demand, or compensation request; no autonomous answer except safe acknowledgement if configured.
- `human_only`: operator has taken over; the agent may summarize and draft but does not send.

The system can move to a stricter mode automatically. Returning to a less strict mode should require clear rules or operator action.

## Policy Rules

Policies should use explicit rule records:

```text
PolicyRule
- name
- subject_type
- intent_or_action_type
- min_confidence
- max_risk_tier
- allowed_modes
- auto_execute_allowed
- approval_required
- forbidden_if
- telegram_template
```

Initial policy:

| Scenario | Default behavior |
| --- | --- |
| Order status question | Auto-send if context is known and confidence is high. |
| Tracking question | Auto-send if tracking data exists. |
| Product stock or variation question | Auto-send from product cache if fresh. |
| Store policy question | Auto-send from approved FAQ or policy text. |
| Mild complaint | Auto-send safe template only when no refund, cancel, threat, or dispute signal exists. |
| Price negotiation | Approval or safe template, depending on configured policy. |
| Custom order request | Acknowledge only if configured, then escalate. |
| Cancel request | Escalate. |
| Return or refund request | Escalate. |
| Hard complaint, threat, abusive tone, legal/platform escalation | Freeze and escalate. |
| Finance mismatch | Escalate with evidence. |

Forbidden LLM behavior:

- Promise refund, cashback, compensation, or cancellation approval.
- Blame buyer, courier, or Shopee explicitly.
- Invent order, tracking, stock, or policy facts.
- Respond outside approved policy context.
- Continue automation when confidence is low or policy conflicts exist.

## Telegram Control Plane

Telegram is the only operator surface in the initial design.

Supported interactions:

- order alerts.
- generated shipping document notifications.
- medium-risk approval cards.
- high-risk escalation cards.
- daily summary.
- health checks.
- dead-letter and replay commands.
- pause and resume automation.
- edit, approve, reject, or escalate chat drafts.

Security requirements:

- allowlist Telegram user ids and chat ids.
- role support: `owner`, `operator`, `viewer`.
- command allowlist.
- audit every command and decision.
- require explicit confirmation for replay or high-impact commands.

## Reliability

Reliability requirements:

- dedupe all external events.
- use upserts for local state.
- retry timeouts and 5xx errors with exponential backoff and jitter.
- do not blindly retry 4xx policy or auth errors.
- persist dead-letter records with enough context for replay.
- run scheduled reconciliation for orders, shipments, product cache, finance settlement, and token health.
- refresh tokens before expiry and write token updates atomically.
- freeze Shopee side effects if token refresh fails repeatedly.
- fall back to templates or escalation when LLM calls fail.

Webhook processing must be fast. Long-running work should move to internal queued execution, even if the first implementation uses a database-backed work queue inside the monolith.

## Security

Security requirements:

- store secrets in environment variables or a VPS secret mechanism, not source code.
- verify Shopee webhook signatures before parsing business events.
- separate public webhook routes from Telegram/operator command handlers.
- avoid logging tokens, signatures, or unnecessary sensitive buyer data.
- restrict archive and evidence file permissions.
- back up the database and evidence files.
- encrypt backups where practical.
- record every autonomous action and human override.

## Observability

Since there is no web dashboard, observability uses structured logs, Telegram commands, and summaries.

Minimum metrics:

- webhook ingest success and failure.
- event processing latency.
- Shopee API error rate.
- token refresh failures.
- dead-letter count.
- order sync drift count.
- auto-reply rate.
- approval and escalation rate.
- operator override rate.
- false or corrected auto-reply count.
- finance mismatch count.
- shipping document generation success and failure.

Telegram commands:

- `/health`: service, database, Shopee auth, scheduler, dead-letter count, and last sync.
- `/summary today`: orders, labels, chat automation, escalations, finance anomalies.
- `/pause`: pause autonomous side effects.
- `/resume`: resume autonomous side effects.
- `/replay <event_id>`: replay an event when authorized.

## Testing Strategy

Required tests:

- event normalization tests.
- idempotency and replay tests.
- policy matrix tests.
- fake Shopee gateway tests.
- token refresh tests.
- Telegram permission and command tests.
- action executor dry-run tests.
- reconciliation drift tests.
- LLM structured output contract tests with mocked providers.
- failure injection for duplicate webhook, API timeout, token expiry, database retry, and LLM timeout.

Simulator scenarios:

- new paid order.
- order ready for shipping document.
- duplicate webhook.
- out-of-order order status update.
- missed webhook repaired by polling.
- mild complaint.
- refund demand.
- hard complaint.
- finance settlement mismatch.
- token refresh failure.

## Phased Delivery

### Phase 1: Core Operating System

- Project scaffold.
- Database schema and migrations.
- Event store and idempotency.
- Shopee gateway interface with simulator implementation.
- Token manager interface.
- Ingress routes.
- Event router.
- Telegram bot with health, alerts, and approvals.
- Order, logistics, and finance skeleton agents.
- Shipping document action in dry-run/simulator mode.
- Test harness and simulator fixtures.

### Phase 2: Shopee Production Integration

- Real signed Shopee client.
- Token refresh persistence.
- Real order detail and order list sync.
- Real logistics document generation.
- Reconciliation jobs.
- Dead-letter replay.
- Daily Telegram summaries.

### Phase 3: Customer Chat Automation

- Chat event ingestion if API access allows it.
- Chat classifier and policy matrix.
- FAQ and policy retrieval.
- Low-risk auto-send.
- Medium-risk Telegram approval.
- Conversation state machine.
- Override feedback tracking.

### Phase 4: Returns, Disputes, Inventory, and Learning Loop

- Return/dispute triage.
- Inventory cache and stock movement alerts.
- Finance anomaly tuning.
- Operator correction feedback.
- Risk threshold tuning.
- Migration path to PostgreSQL if volume requires it.

## Out of Scope for Initial Build

- Web dashboard.
- Full auto-ship workflow.
- Final automated refund, dispute, or compensation decisions.
- Hardcoded Shopee fee formulas as authoritative finance logic.
- Multi-shop scale-out architecture.
- Autonomous response to high-risk customer messages.

## Open Implementation Notes

- Shopee chat API capabilities and automation policy must be verified during implementation. If automated chat sending is unavailable or not allowed, the same Chat Agent will run in draft-and-approve mode.
- The first database implementation should keep SQL portable and avoid SQLite-specific behavior outside the repository layer.
- The simulator should remain part of the permanent test suite, not a temporary scaffold.
- The system should start in conservative mode, then enable specific auto-actions after policy tests and simulator replay pass.

## Acceptance Criteria

The design is ready for implementation planning when:

- all event sources produce normalized events.
- all agent actions pass through Policy Engine and Action Executor.
- low, medium, and high risk paths are explicit.
- Telegram can show action reason, evidence, approval buttons, and audit status.
- simulator can replay core workflows without Shopee credentials.
- real Shopee integration can be added behind gateway interfaces.
- tests cover idempotency, policy decisions, replay, and provider failure paths.
