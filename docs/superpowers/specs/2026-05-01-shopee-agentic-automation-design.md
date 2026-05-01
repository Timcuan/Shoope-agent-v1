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
- Reporting scope: automatic Excel output for daily, weekly, monthly, order, finance, inventory, chat, and escalation recaps.
- Product intelligence scope: the agent must know product catalog details, variants, stock, pricing, policies, FAQ, product constraints, and approved selling points before it interacts with customers.
- Customer dynamics scope: the agent must model conversation state, customer mood, urgency, risk, purchase context, and escalation triggers.

## Shopee API Capability Map

Shopee Open Platform should be used for seller operations only. The official API is suitable for the shop's own orders, products, logistics, finance/payment-related records, returns, shop/account data, push events, and eligible chat workflows. It is not a reliable source for competitor intelligence or marketplace-wide analytics.

The implementation should maximize these use cases:

| API area | What the bot can do | Automation use case |
| --- | --- | --- |
| Authorization and Public APIs | Generate authorization links, receive authorization codes, store shop ids, refresh access tokens. | Keep the integration alive and alert the operator before auth failure blocks operations. |
| Shop APIs | Read shop identity, profile, settings, and operational metadata. | Bind events to the right shop and enrich Telegram summaries. |
| Order APIs | Pull order list, order detail, invoice/order metadata, remarks, cancellation-related data where permission allows. | Detect new orders, update status, build packing context, reconcile missed webhook events, and feed finance reports. |
| Logistics APIs | Read logistics channels, shipping parameters, tracking information, and generate shipping documents where available. | Auto-generate shipping documents for eligible orders, detect shipping blockers, and notify operators. |
| Product APIs | Read and update product data, categories, attributes, brands, price, stock, variants, and product metadata where permission allows. | Build product knowledge, answer product questions safely, detect low stock, and prevent wrong variant promises. |
| Returns and Refund APIs | Read return/refund requests and details; perform sensitive actions only after approval. | Triage cases, summarize evidence, recommend action, and route high-risk cases to Telegram. |
| Payment/Finance APIs | Read order income, payout, wallet, escrow, and settlement-related records where permission allows. | Build ledger, settlement recap, margin estimates, anomaly alerts, and Excel finance reports. |
| Push Mechanism | Receive configured platform notifications. | Trigger event-driven order, logistics, chat, return, and sync workflows. |
| Chat APIs | If the app is whitelisted and policy permits, read chat context and send messages. | Auto-send low-risk replies, draft/approve medium-risk replies, and freeze high-risk conversations. |
| Account Health APIs | Read performance, penalty, or account health signals where available. | Alert late shipment risk, operational penalty risk, and service quality issues. |
| Media APIs | Upload supported images or files where needed. | Support product/chat evidence workflows and shipping/return evidence if allowed. |
| Promotion APIs | Read or manage vouchers, discounts, bundle deals, add-on deals, top picks, and follow prizes where permission allows. | Let the agent answer promo questions from real promo state and recommend safe promo references. |

Every capability must be gated by app permission, region, seller account type, rate limits, and Shopee policy. If an API is unavailable, the system falls back to simulator, manual import, or Telegram approval flows.

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
        +--> Reporting Agent
        +--> Product Knowledge Agent
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
- Excel writer for `.xlsx` reports generated from local database snapshots.
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

### Reporting and Excel Writer

Reporting converts local operational data into clear recaps. It must write `.xlsx` files automatically and attach or link them through Telegram when requested or scheduled.

Reports should come from local database snapshots, not live scattered API calls. This keeps reports reproducible and prevents partial exports when Shopee API calls fail.

Initial report types:

- daily operations recap.
- daily finance recap.
- weekly sales and settlement recap.
- monthly P&L-ready export.
- order fulfillment backlog.
- inventory and low-stock recap.
- chat automation recap.
- escalation and operator workload recap.
- finance anomaly report.
- product knowledge freshness report.

Excel files should include multiple sheets when useful, such as `summary`, `orders`, `items`, `finance`, `inventory`, `chats`, `escalations`, and `anomalies`. Each generated file must be recorded in an `exports` table with report type, time range, file path, checksum, creator, and source query version.

### Product Knowledge Base

Product Knowledge Base is the factual layer used by Chat Agent, Inventory Agent, Reporting Agent, and Telegram summaries. It combines Shopee product data with local seller knowledge.

It should store:

- Shopee item id, model id, SKU, name, brand, category, attributes, variation options, and images.
- price, promo price, stock, reserved stock, sold count if available, and sync timestamp.
- weight, dimensions, shipping constraints, fragile flags, bundle rules, and compatibility notes.
- approved selling points, forbidden claims, product limitations, warranty policy, return policy, and care instructions.
- aliases and customer-language synonyms for each product and variant.
- FAQ entries tied to products, variants, and policies.

The agent must answer product questions from this knowledge base. If the product, variant, stock, or policy is stale or missing, it must ask a clarifying question or escalate instead of guessing.

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

### Product Knowledge Agent

Product Knowledge Agent keeps product facts usable for automation. It syncs Shopee product data, normalizes variants, maps SKUs to human names, tracks freshness, builds product aliases, and flags incomplete product knowledge.

It must prevent the Chat Agent from making unsafe product claims. A response about product availability, compatibility, warranty, bundle contents, or shipping constraint is allowed only when the required facts are present and fresh enough.

### Chat Agent

Chat Agent classifies intent, sentiment, risk, urgency, and confidence. It retrieves relevant order, tracking, product, FAQ, and policy context. It proposes either a template response, LLM-assisted draft, approval request, or escalation.

Moderate automation rules:

- Low-risk status, tracking, stock, and policy questions may auto-send.
- Mild complaints may auto-send only when policy allows and context is clear.
- Medium-risk drafts require Telegram approval.
- High-risk conversations freeze automation and escalate.

The Chat Agent must understand online customer dynamics. It tracks whether a customer is browsing, comparing, negotiating, anxious about delivery, mildly frustrated, angry, abusive, asking for exception handling, or moving toward dispute/refund. It must detect topic shifts inside one conversation, such as status question to complaint to refund request.

Customer dynamics signals:

- intent and intent shift.
- sentiment and frustration trend.
- urgency.
- buyer stage: pre-sale, paid waiting shipment, shipped, delivered, after-sales.
- order value and risk.
- repeated question count.
- response time sensitivity.
- refund, cancellation, compensation, or dispute keywords.
- abusive, threat, legal, or platform escalation signals.
- mismatch between customer claim and order data.

The agent should use these signals to choose between auto-reply, clarification, approval, escalation, and `human_only` mode.

### Reporting Agent

Reporting Agent builds scheduled and on-demand recaps from local data. It prepares Telegram summaries and `.xlsx` files.

It should support:

- `/summary today`.
- `/summary week`.
- `/export orders today`.
- `/export finance month`.
- `/export inventory`.
- `/export chats`.
- automatic daily close report.
- automatic weekly management report.

Reports must be clear enough for decision making, not raw data dumps. The first sheet should be an executive summary with totals, deltas, anomalies, and recommended operator actions.

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
| `product_knowledge` | Local product facts, approved claims, constraints, aliases, and FAQ links. |
| `product_faqs` | Product-specific question and answer records used for safe replies. |
| `customers` | Buyer mapping, order history, and risk markers. |
| `conversations` | Conversation mode, latest intent, temperature, and operator state. |
| `chat_messages` | Inbound and outbound messages, intent, confidence, reply mode, and audit state. |
| `returns_disputes` | Case reason, evidence, recommendation, and decision state. |
| `action_requests` | Pending, approved, rejected, and executed action payloads. |
| `exports` | Generated report metadata, file paths, checksums, and source query versions. |
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
- `product_knowledge_freshness`.
- `reporting_period`.

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
| Product compatibility, warranty, fragile item, sizing, bundle, or limitation question | Auto-send only from approved product knowledge; otherwise clarify or escalate. |
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
- Excel report generation and delivery.
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
- `/export orders today`: create and send an order workbook.
- `/export finance month`: create and send a finance workbook.
- `/export inventory`: create and send an inventory workbook.
- `/export chats`: create and send a chat automation workbook.
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
- Excel report generation tests.
- product knowledge freshness and fallback tests.
- customer dynamics state transition tests.
- failure injection for duplicate webhook, API timeout, token expiry, database retry, and LLM timeout.

Simulator scenarios:

- new paid order.
- order ready for shipping document.
- duplicate webhook.
- out-of-order order status update.
- missed webhook repaired by polling.
- mild complaint.
- customer topic shift from status question to refund request.
- stale product stock question.
- product compatibility question with missing knowledge.
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
- Reporting Agent with daily summary and Excel writer.
- Product Knowledge Base schema and import/sync skeleton.
- Shipping document action in dry-run/simulator mode.
- Test harness and simulator fixtures.

### Phase 2: Shopee Production Integration

- Real signed Shopee client.
- Token refresh persistence.
- Real order detail and order list sync.
- Real logistics document generation.
- Product catalog and variant sync.
- First production Excel reports from real order, item, finance, and inventory data.
- Reconciliation jobs.
- Dead-letter replay.
- Daily Telegram summaries.

### Phase 3: Customer Chat Automation

- Chat event ingestion if API access allows it.
- Chat classifier and policy matrix.
- FAQ and policy retrieval.
- Product-aware response retrieval.
- Customer dynamics state machine.
- Low-risk auto-send.
- Medium-risk Telegram approval.
- Conversation state machine.
- Override feedback tracking.

### Phase 4: Returns, Disputes, Inventory, and Learning Loop

- Return/dispute triage.
- Inventory cache and stock movement alerts.
- Product knowledge quality scoring.
- Advanced Excel recaps for weekly/monthly operations.
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
- Competitor scraping, marketplace-wide analytics, or unofficial Shopee private APIs.

## Open Implementation Notes

- Shopee chat API capabilities and automation policy must be verified during implementation. If automated chat sending is unavailable or not allowed, the same Chat Agent will run in draft-and-approve mode.
- The first database implementation should keep SQL portable and avoid SQLite-specific behavior outside the repository layer.
- The simulator should remain part of the permanent test suite, not a temporary scaffold.
- The system should start in conservative mode, then enable specific auto-actions after policy tests and simulator replay pass.
- Excel exports should be generated from local snapshots and should not block core event processing.
- Product knowledge must be treated as a safety dependency for customer-facing answers.

## Acceptance Criteria

The design is ready for implementation planning when:

- all event sources produce normalized events.
- all agent actions pass through Policy Engine and Action Executor.
- low, medium, and high risk paths are explicit.
- Telegram can show action reason, evidence, approval buttons, and audit status.
- Telegram can request and receive Excel recap files.
- the agent can answer product questions only when product knowledge is present and fresh.
- the agent can detect customer mood, topic shifts, and escalation risk.
- simulator can replay core workflows without Shopee credentials.
- real Shopee integration can be added behind gateway interfaces.
- tests cover idempotency, policy decisions, replay, and provider failure paths.
