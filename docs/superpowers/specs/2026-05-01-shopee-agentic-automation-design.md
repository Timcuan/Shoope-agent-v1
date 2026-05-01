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
- Shipping document and print scope: generate, download, archive, batch, and print-ready shipping documents, labels, AWB/resi, packing lists, and picklists with audit and operator controls.
- Reporting scope: automatic Excel output for daily, weekly, monthly, order, finance, inventory, chat, and escalation recaps.
- Shopee audit workbook scope: the recap engine must understand and fill the uploaded workbook shape from `/Users/aaa/Downloads/auditshopeedef.xlsx` with high precision.
- Product intelligence scope: the agent must know product catalog details, variants, stock, pricing, policies, FAQ, product constraints, and approved selling points before it interacts with customers.
- Customer dynamics scope: the agent must model conversation state, customer mood, urgency, risk, purchase context, and escalation triggers.
- Telegram UX scope: Telegram must work as a proper control room with concise menus, action cards, inline approvals, health monitoring, exports, and safe operator workflows.
- Engine quality scope: the system must include audit, tuning, backtesting, simulation, and safety gates. The goal is production-grade reliability, not unbounded autonomy.
- Operator replacement scope: the bot should cover the routine Seller Center checks that force operators to open Shopee repeatedly, while keeping high-risk changes supervised from Telegram.
- Telegram scalability scope: the bot must stay usable as features grow, using role-aware routing, pagination, deduped alerts, digesting, search, and task state instead of dumping every event into chat.
- Database correctness scope: database design must minimize missed, duplicated, stale, or unreconciled records through constraints, idempotency keys, indexes, watermarks, audits, and repair workflows.

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

Additional seller-center replacement use cases:

| Area | Telegram-supervised automation |
| --- | --- |
| Daily agenda | Morning briefing of pending orders, labels, chats, returns, stock risks, settlement risks, and account health issues. |
| Exception inbox | One queue for orders, chats, returns, finance, stock, labels, and sync problems that need attention. |
| Search and lookup | `/find <order/customer/SKU>` returns order timeline, customer context, product facts, and latest actions. |
| Fulfillment SLA | Alerts for order aging, label not printed, pickup/dropoff risk, delayed shipment, and courier tracking stagnation. |
| Packing supervision | Batch picklist, packing checklist, item count validation, fragile/high-value flags, and skipped-order reasons. |
| Product listing hygiene | Detect stale stock, missing SKU mapping, missing dimensions/weight, incomplete product knowledge, inactive products, and price anomalies. |
| Promotion supervision | Monitor seller vouchers, discounts, bundles, add-on deals, top picks, follow prizes, and promo expiry if API permission exists. |
| Price and margin guard | Warn when promo, fee, shipping, or settlement creates weak or negative estimated margin. |
| Chat quality control | Review auto-sent replies, unresolved chats, sentiment deterioration, slow response risk, and repeated questions. |
| Customer memory | Show buyer order history, risk markers, conversation mode, unresolved promises, and last operator decision. |
| Return/dispute desk | Evidence checklist, case timeline, recommended response draft, deadline alert, and approval workflow. |
| Review/rating watch | If review/rating API or export is available, summarize low ratings, product issues, and reply recommendations. Otherwise track only manually imported review data. |
| Account health | Monitor shop performance, penalties, late shipment risk, cancellation risk, and service quality signals where available. |
| Reconciliation center | Show sync drift, missing settlement, missing document, duplicate webhook, failed action, and replay options. |
| Knowledge maintenance | Ask operators to fill missing product facts or FAQ answers directly from Telegram when automation is blocked. |

These features should be implemented as supervised work queues first. Automation can be enabled later per workflow after simulator, audit, and policy gates pass.

Logistics capability sequence:

```text
Get channel/address/parameter
-> Ship/order arrangement if policy allows
-> Create shipping document task
-> Poll shipping document result
-> Download shipping document
-> Archive document
-> Send/print/queue document
-> Track shipment and reconcile status
```

`ship order`, `batch ship order`, address updates, channel updates, and cancellation-adjacent actions are high-impact logistics actions. They must stay behind policy gates and operator approval until the store's fulfillment rules are proven.

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
        +--> Operations Supervisor Agent
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

### Shopee Audit Workbook Engine

The uploaded example workbook `auditshopeedef.xlsx` defines a specific monthly audit format. The recap engine must support this format as a named report template, not as a one-off export.

Observed template structure:

- sheets: `jan`, `feb`, `mar`, `apr`, `may`, `jun`, `jul`, `aug`, `sep`, `oct`, `nov`, `dec`.
- each month sheet uses columns `A:L`.
- row 1 contains merged section headers:
  - `A1:A2`: `NO`.
  - `B1:D1`: `STATUS PESANAN`.
  - `E1:F1`: `DETAIL PESANAN`.
  - `G1:I1`: `BIAYA`.
  - `J1:L1`: `LAIN-LAIN`.
- row 2 contains field headers:
  - `B`: `TERIMA`.
  - `C`: `KIRIM`.
  - `D`: `SELESAI`.
  - `E`: `ORDER`.
  - `F`: `NO PESANAN`.
  - `G`: `PESANAN`.
  - `H`: `ADMIN`.
  - `I`: `JUMLAH`.
  - `J`: `DANA DITERIMA`.
  - `K`: `SELISIH`.
  - `L`: `KETERANGAN`.
- rows `3:202` are transaction rows.
- row `203` is the total row.
- normal transaction formulas:
  - `Hn = Gn * admin_rate`.
  - `In = Gn - Hn`.
  - `Kn = Jn - In`.
- total row formulas:
  - `G203 = SUM(G3:G202)`.
  - `H203 = G203 * total_admin_rate`.
  - `I203 = G203 - H203`.
  - `J203 = SUM(J3:J202)`.
  - `K203 = J203 - I203`.
  - `L203 = I203 - J203`.

The example has a rate mismatch: transaction rows use `7.5%`, while the total admin row uses `8%`. The engine must not silently normalize this. It should store both rates in `report_templates`, surface the mismatch in a template audit warning, and allow the configured report version to either preserve the example exactly or use a corrected rate consistently.

Column semantics:

| Column | Meaning | Source mapping |
| --- | --- | --- |
| `A` | Sequential row number. | Generated per month. |
| `B` | Date/time order was received or accepted. | Shopee order create/pay/ready timestamp, selected by config. |
| `C` | Date/time order was shipped. | Shipment/logistics timestamp. |
| `D` | Date/time order was completed. | Completed status timestamp. |
| `E` | Order description or item summary. | Collapsed order item names, SKU summary, or configured order label. |
| `F` | Shopee order number. | `order_sn`. |
| `G` | Gross order amount. | Order total before admin deduction, from authoritative order/finance field. |
| `H` | Admin fee. | Formula from configured admin rate unless authoritative fee field is mapped. |
| `I` | Expected amount after admin. | Formula. |
| `J` | Actual funds received. | Escrow/settlement/payout amount when available. |
| `K` | Difference between actual and expected. | Formula. |
| `L` | Notes. | Generated anomaly note, manual note, or reconciliation reason. |

Precision requirements:

- Preserve workbook layout: sheet names, merged headers, row heights, column widths, borders, fills, freeze panes, and number formats.
- Preserve formulas unless the report version explicitly switches to value-only mode.
- Write dates as real Excel dates, not strings, when source granularity allows it.
- Write currency/amounts as numbers, not formatted text.
- Keep formulas auditable and visible to operators.
- Leave blank cells blank when no source field exists.
- Add notes in `KETERANGAN` for partial data, missing settlement, stale sync, manual override, rate mismatch, or reconciliation drift.
- Generate row count dynamically if a month has more than 200 transactions. If the template must remain fixed at 200 rows, overflow rows must go to an `overflow_<month>` sheet and trigger a Telegram warning.
- Store one export metadata record per generated workbook, including template name, template version, source date range, source event watermark, formula mode, checksum, and warnings.

Recommended internal template id:

```text
shopee_monthly_audit_v1
```

The engine should support two output modes:

- `template_exact`: preserve the uploaded workbook's formulas and rates exactly, including the 7.5% row rate and 8% total rate.
- `policy_corrected`: use configured policy rates consistently and record the difference from the original template.

The default for production should be `policy_corrected` after the operator confirms the correct admin fee policy. Until then, generated audit workbooks should run in `template_exact` and show a warning.

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

It also owns the print-ready document lifecycle:

- fetch shipping parameters.
- validate logistics channel and package number.
- create shipping document task.
- poll result until ready or failed.
- download AWB/resi/label document.
- archive the file with checksum and metadata.
- create print job or Telegram document delivery.
- reconcile tracking number and shipment status after document generation.

### Print and Document Agent

Print and Document Agent prepares operational documents for packing and handoff. It works with Logistics Agent but has its own queue so printing/export work never blocks order ingestion.

Document types:

- Shopee shipping label / AWB / resi.
- packing slip.
- picklist by batch.
- batch label bundle.
- return/dispute evidence bundle.
- order detail PDF for manual handling.

Print outputs:

- Telegram document attachment.
- local archive file.
- print queue record for a configured printer.
- batch PDF bundle grouped by courier, pickup/dropoff mode, or warehouse area.

The first implementation should generate and deliver print-ready files. Direct OS/printer printing should be optional because VPS printers vary. If direct printing is enabled later, it must be explicitly configured and audited.

Batch print rules:

- group by logistics channel, pickup/dropoff mode, and document type.
- sort by order received time or SKU location.
- enforce max batch size.
- skip orders with missing product knowledge, custom request flags, or unresolved risk.
- show a Telegram confirmation card before batch actions that change Shopee state.
- allow document-only batch download without changing Shopee order state.

Document archive metadata:

- `document_id`.
- `order_sn`.
- `package_number`.
- `document_type`.
- `source_action_id`.
- `file_path`.
- `mime_type`.
- `checksum`.
- `generated_at`.
- `printed_at`.
- `print_status`.
- `shopee_request_id`.
- `template_version`.
- `operator_id` when manually triggered.

### Finance Agent

Finance Agent creates operational ledger records from order and settlement data. It stores estimated fees, final escrow values, commissions, service fees, shipping fees, and settlement deltas.

It must not hardcode seller fee formulas as final truth. API-provided values are authoritative when available. Internal formulas are only estimates until final data arrives.

### Inventory Agent

Inventory Agent maintains product and stock cache, reserved stock, released stock, sold stock, and low-stock alerts. It avoids reading live product APIs on every chat or order path unless a refresh is explicitly needed.

### Product Knowledge Agent

Product Knowledge Agent keeps product facts usable for automation. It syncs Shopee product data, normalizes variants, maps SKUs to human names, tracks freshness, builds product aliases, and flags incomplete product knowledge.

It must prevent the Chat Agent from making unsafe product claims. A response about product availability, compatibility, warranty, bundle contents, or shipping constraint is allowed only when the required facts are present and fresh enough.

### Operations Supervisor Agent

Operations Supervisor Agent turns many small Seller Center checks into one Telegram-supervised operating queue. Its job is not to replace every Shopee screen, but to make the daily decisions visible and actionable without opening Shopee unless a case truly needs manual inspection.

Responsibilities:

- build the daily agenda.
- maintain the exception inbox.
- rank operational issues by urgency and business impact.
- detect orders close to SLA breach.
- detect missing label, missing pickup/dropoff action, or stale tracking.
- detect stock, SKU, product knowledge, and listing hygiene gaps.
- monitor promotion and voucher state when API permission allows it.
- monitor account health and penalty signals when API permission allows it.
- summarize return/dispute deadlines and missing evidence.
- create operator tasks from unresolved anomalies.
- close tasks automatically when reconciliation proves the issue is resolved.

It should emit `OperatorTask` records:

```text
OperatorTask
- task_id
- category: order | chat | logistics | inventory | finance | product | promo | return | account_health | sync
- subject_id
- severity: P0 | P1 | P2 | P3
- title
- summary
- recommended_action
- evidence_refs
- due_at
- status: open | acknowledged | waiting | resolved | dismissed
- assigned_role
- action_buttons
```

The task queue becomes the Telegram home screen for daily operations.

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
| `shipping_documents` | AWB/resi/label/packing document metadata, file path, checksum, and readiness status. |
| `print_jobs` | Print queue records, batch grouping, target printer, attempts, and status. |
| `packing_batches` | Batch definitions for picklist, labels, packing slips, and courier handoff. |
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
| `report_templates` | Named Excel template schemas, column mappings, formula rules, style anchors, and versioned assumptions. |
| `report_template_audits` | Template inconsistencies, rate mismatches, missing mappings, overflow warnings, and validation results. |
| `work_queue` | Background jobs, leases, priorities, attempts, and recovery state. |
| `alerts` | Open, acknowledged, snoozed, and resolved operator alerts. |
| `telegram_callbacks` | Opaque callback ids, expiry, action binding, and execution status. |
| `automation_versions` | Policy, prompt, product knowledge, report query, and simulator scenario versions. |
| `operator_feedback` | Corrections, overrides, false auto-reply tags, and tuning notes. |
| `operator_tasks` | Daily agenda and exception inbox tasks with severity, due time, status, and action buttons. |
| `sla_watch` | Order, chat, return, label, pickup/dropoff, and settlement deadlines. |
| `promotion_state` | Voucher, discount, bundle, add-on, top-pick, and follow-prize snapshots where permission allows. |
| `listing_health` | Product listing gaps, stale facts, price anomalies, stock sync issues, and missing attributes. |
| `customer_memory` | Buyer context, unresolved promises, sentiment trajectory, and operator notes. |
| `reconciliation_runs` | Sync run metadata, source watermarks, drift counts, repair actions, and status. |
| `data_quality_checks` | Check definitions, latest result, severity, affected rows, and repair hints. |
| `entity_versions` | Latest version/hash per order, product, shipment, settlement, conversation, and return case. |
| `outbox` | Durable external side-effect requests before Shopee, Telegram, file, or print execution. |
| `inbox_offsets` | Last processed webhook/polling/chat/update offsets and cursors by source. |
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
| Generate shipping document for eligible order | Auto-generate if logistics data is complete and risk is low. |
| Download existing shipping document | Auto-download and archive if document is ready. |
| Print or send label document | Auto-send to Telegram or queue print if configured. |
| Batch document-only export | Approval optional, based on operator setting. |
| Ship order or batch ship order | Approval required until fulfillment policy is proven. |
| Address/channel update | Owner approval required. |

Forbidden LLM behavior:

- Promise refund, cashback, compensation, or cancellation approval.
- Blame buyer, courier, or Shopee explicitly.
- Invent order, tracking, stock, or policy facts.
- Respond outside approved policy context.
- Continue automation when confidence is low or policy conflicts exist.

## Telegram Control Plane

Telegram is the only operator surface in the initial design.

The bot should feel like an operations console, not a chat script. It should minimize typing, show the right action at the right time, and hide noisy raw data unless an operator asks for details.

Supported interactions:

- order alerts.
- generated shipping document notifications.
- print-ready resi/AWB/label notifications.
- batch packing and print controls.
- medium-risk approval cards.
- high-risk escalation cards.
- daily summary.
- Excel report generation and delivery.
- health checks.
- dead-letter and replay commands.
- pause and resume automation.
- edit, approve, reject, or escalate chat drafts.

### Telegram UX Principles

- Every important alert must answer: what happened, why it matters, what the bot recommends, and what buttons are available.
- Operators should use buttons for frequent actions and commands for navigation or power-user workflows.
- Message cards must be short by default and expose details through `Detail`, `Evidence`, `History`, or `Export` buttons.
- High-risk actions require an explicit confirmation step.
- Callback buttons must be idempotent. Double taps, retries, or delayed Telegram updates must not execute an action twice.
- Every callback query must be acknowledged quickly so Telegram clients do not show a stuck loading state.
- The bot must support quiet hours, severity routing, and digest mode to avoid operator fatigue.

### Telegram Information Architecture

Primary command groups:

```text
/start
/menu
/health
/agenda
/inbox
/find
/orders
/chats
/inventory
/finance
/returns
/products
/promos
/customers
/reports
/exports
/alerts
/settings
/pause
/resume
```

The main menu should show role-aware sections:

```text
Control Room
[Agenda] [Inbox] [Health]
[Orders] [Chats] [Labels]
[Inventory] [Finance] [Returns]
[Products] [Promos] [Customers]
[Reports] [Exports] [Settings]
```

View-specific menus:

- Orders: `New`, `Ready to Ship`, `Label Issues`, `Delayed`, `Search`.
- Chats: `Pending Approval`, `Escalated`, `Human Only`, `Auto-Sent`, `Review Mistakes`.
- Inventory: `Low Stock`, `Stale Product Data`, `SKU Mapping Issues`, `Product Knowledge Gaps`.
- Finance: `Today`, `This Week`, `Settlement Mismatch`, `Export`.
- Returns: `New`, `Needs Evidence`, `Needs Decision`, `Disputed`.
- Products: `Listing Gaps`, `Price Anomalies`, `Inactive`, `Knowledge Missing`, `Sync Stale`.
- Promos: `Active`, `Ending Soon`, `Weak Margin`, `Voucher Questions`, `Needs Approval`.
- Customers: `Search`, `Sensitive`, `Repeat Complaint`, `Promises`, `Human Only`.
- Inbox: `P0`, `P1`, `P2`, `Waiting`, `Snoozed`, `Resolved Today`.
- Reports: `Daily`, `Weekly`, `Monthly`, `Custom Range`.

### Telegram Scalability Rules

As the feature set grows, Telegram must not become noisy or hard to navigate.

Rules:

- Use menus for discovery, search for direct access, and inbox queues for work.
- Paginate every list over 10 items.
- Collapse repeated alerts into one task with count, latest timestamp, and affected subjects.
- Route P0/P1 immediately; digest P2/P3 unless the operator opens the related queue.
- Use stable task ids so every message card maps to one record in `operator_tasks`.
- Edit existing Telegram messages for state changes when possible instead of sending new messages for every update.
- Expire stale buttons and replace them with `Refresh` or `Open latest task`.
- Provide `Details`, `Evidence`, `History`, and `Export` buttons instead of placing long raw payloads in chat.
- Keep every action reversible or auditable. If not reversible, require confirmation.
- Keep long-running exports and batch jobs asynchronous. Telegram should acknowledge the request, then send completion or failure later.

List UX:

```text
Inbox P1 (page 1/3)
1. Label missing - order 250501ABC - due 38m
2. Chat approval - buyer sensitive - due 12m
3. Finance mismatch - order 250501XYZ

[Open 1] [Open 2] [Open 3]
[Next] [Filter] [Export]
```

Search UX:

```text
/find black l
Products: 3
Orders: 5
Chats: 2
Tasks: 1

[Product ABC-BLACK-L] [Orders] [Chats] [Tasks]
```

Telegram throughput guardrails:

- configurable max immediate alerts per minute.
- configurable max digest size.
- per-role notification preferences.
- task ownership and assignment to avoid two operators handling the same case blindly.
- command cooldowns for expensive exports or broad searches.

### Telegram Card Patterns

Order card:

```text
Order Ready for Label
Order: 250501ABC
Buyer: masked / Shopee id
Items: 2 SKU, 3 qty
Risk: Low
Recommendation: Generate shipping document

[Generate Label] [Hold] [Details]
[Items] [Buyer History] [Open in Shopee]
```

Chat approval card:

```text
Chat Needs Approval
Customer mood: mildly frustrated
Intent: delayed shipment question
Risk: Medium
Confidence: 0.82
Recommended reply: "Maaf ya kak, paketnya..."

[Send] [Edit] [Escalate]
[Order Context] [Policy] [History]
```

Finance anomaly card:

```text
Finance Mismatch
Order: 250501ABC
Expected: Rp 184.000
Actual: Rp 171.500
Delta: Rp 12.500
Reason guess: shipping/fee difference

[Mark Reviewed] [Export Evidence] [Details]
```

Product knowledge gap card:

```text
Product Knowledge Gap
SKU: ABC-BLACK-L
Missing: warranty policy, material, care instruction
Impact: Chat auto-reply disabled for product-specific questions

[Add Note] [Import FAQ] [Snooze]
```

Daily agenda card:

```text
Daily Agenda
Orders to pack: 18
Labels ready: 14
Label issues: 2
Chats waiting: 5
Returns/disputes: 1
Low stock critical: 3
Finance anomalies: 2

[Open Inbox] [Create Packing Batch] [Export Today]
[Health] [Snooze P3]
```

Exception inbox card:

```text
P1 Exception
Type: Fulfillment SLA
Order: 250501ABC
Issue: paid order has no label after 6h
Recommended: generate label or hold order

[Generate Label] [Hold] [Details]
[Customer Context] [Snooze 1h]
```

Product hygiene card:

```text
Product Listing Issue
SKU: ABC-BLACK-L
Issue: stock stale for 18h + missing weight
Impact: auto stock reply and label eligibility blocked

[Refresh Product] [Add Weight] [Snooze]
```

Promo supervision card:

```text
Promo Margin Warning
Voucher: MAYSALE10
SKU: ABC-BLACK-L
Estimated margin after voucher: 4.2%
Threshold: 8%

[Keep] [Pause/End if API allows] [Details]
```

### Telegram Roles and Permissions

Roles:

- `owner`: all actions, settings, replay, pause/resume, export, approval.
- `operator`: approvals, escalations, summaries, exports, order/chat handling.
- `viewer`: health, summaries, and read-only reports.

Sensitive commands:

- `/pause`, `/resume`, `/replay`, high-risk approvals, return/dispute recommendations, and settings changes require owner or configured operator permission.
- Replays and high-impact actions require confirmation cards.

### Notification Tuning

Alerts should use severity:

- `P0`: auth failure, event processor stopped, database write failure, repeated Shopee action failure. Immediate alert.
- `P1`: high-risk chat, return/dispute, finance anomaly, repeated label failure. Immediate alert.
- `P2`: medium-risk chat approval, low-stock critical, stale product knowledge blocking replies. Batched unless urgent.
- `P3`: normal order summaries, successful exports, routine sync results. Digest only.

The bot should support:

- quiet hours for non-urgent alerts.
- digest mode for P2/P3.
- per-role routing.
- duplicate alert suppression.
- alert state transitions: `open`, `acknowledged`, `snoozed`, `resolved`.

### Telegram Monitoring UX

`/health` should show:

- service status.
- Shopee auth status and token expiry window.
- webhook/polling freshness.
- scheduler status.
- queue backlog.
- dead-letter count.
- last successful sync per domain.
- latest export status.
- product knowledge freshness.
- auto-action pause state.

`/health deep` should include slow queries, API error rates, retry backlog, and failed action samples.

`/alerts` should show open alerts grouped by severity, with buttons to acknowledge, snooze, resolve, or export evidence.

### Telegram Feature Load Testing

The bot must be tested with realistic busy-day simulations:

- hundreds of order events.
- dozens of chat approvals.
- mixed label, finance, stock, and sync exceptions.
- repeated duplicate alerts.
- large export requests.
- multiple operators pressing buttons.

Pass criteria:

- no duplicate side effects.
- no unreadable message flood.
- callback acknowledgement stays within target.
- inbox remains navigable through pagination and filters.
- task state is correct after concurrent operator actions.

### Telegram Report UX

`/reports` should open a menu:

```text
Reports
[Today] [This Week] [This Month]
[Finance] [Inventory] [Chats]
[Custom Range] [Schedule]
```

Each generated report should send:

- a short Telegram summary.
- the Excel workbook as a document.
- source period.
- generated timestamp.
- checksum.
- warnings if data was partial, stale, or reconciled.

Security requirements:

- allowlist Telegram user ids and chat ids.
- role support: `owner`, `operator`, `viewer`.
- command allowlist.
- audit every command and decision.
- require explicit confirmation for replay or high-impact commands.
- verify Telegram webhook secret token if webhooks are used.
- restrict callback payloads to short opaque action ids, not raw sensitive data.
- expire approval buttons after a configured window.

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

## Database Correctness, Audit, and Tuning

The database is the system of record for local automation. The main risk is not only downtime; it is missing, duplicated, stale, or partially reconciled data that makes the bot act on the wrong state. The schema and jobs must make those failures visible and repairable.

### Write Model

Use an append-first model for external facts and a derived snapshot model for current operational state:

- `events` stores raw and normalized incoming facts.
- domain tables store current snapshots.
- `entity_versions` stores hashes and source timestamps for change detection.
- `outbox` stores side effects before execution.
- `operator_audit` stores human decisions.
- `reconciliation_runs` proves sync coverage.

All provider-originated records must include:

- `shop_id`.
- source system.
- source id.
- source updated timestamp if available.
- local received timestamp.
- correlation id.
- payload checksum or normalized hash.
- sync run id or event id.

### Constraints and Idempotency

Required uniqueness constraints:

- `events(source, shop_id, source_event_id, event_type)`.
- `orders(shop_id, order_sn)`.
- `order_items(shop_id, order_sn, item_id, model_id)`.
- `shipments(shop_id, order_sn, package_number)`.
- `shipping_documents(shop_id, order_sn, package_number, document_type)`.
- `finance_ledger(shop_id, order_sn, ledger_type, source_version)`.
- `products(shop_id, item_id)`.
- `product_variants(shop_id, item_id, model_id)`.
- `chat_messages(shop_id, conversation_id, message_id)`.
- `returns_disputes(shop_id, return_sn)`.
- `action_requests(idempotency_key)`.
- `outbox(idempotency_key)`.
- `telegram_callbacks(callback_id)`.

Every external side effect must be driven by `outbox` and marked with an idempotency key before the action executes. If the process crashes after sending but before recording success, recovery must check provider state before retrying.

### Indexing Plan

Minimum indexes:

- order lookup: `(shop_id, order_sn)`, `(shop_id, order_status, update_time)`, `(shop_id, create_time)`.
- logistics: `(shop_id, document_status, generated_at)`, `(shop_id, tracking_number)`.
- work queue: `(status, priority, lease_until)`, `(event_id)`, `(idempotency_key)`.
- tasks: `(status, severity, due_at)`, `(category, status)`, `(subject_id)`.
- chat: `(shop_id, conversation_id, created_at)`, `(risk_tier, conversation_mode)`.
- product: `(shop_id, item_id)`, `(sku)`, `(knowledge_freshness_status)`.
- finance: `(shop_id, settlement_date)`, `(shop_id, order_sn)`, `(anomaly_flag)`.
- reconciliation: `(source, status, started_at)`.

SQLite WAL is acceptable for the first deployment if write transactions remain short and report generation reads from snapshots. If lock contention, queue latency, or report load becomes visible, migrate to PostgreSQL.

### Reconciliation and No-Miss Audits

Run reconciliation as a first-class workflow, not a background afterthought.

Daily checks:

- orders in Shopee but missing locally.
- local orders absent from latest Shopee window.
- order status drift.
- shipment status drift.
- missing shipping document for eligible orders.
- missing tracking number after label generation.
- finance ledger missing for completed orders.
- settlement mismatch over threshold.
- stale product stock or price.
- product knowledge gaps blocking customer replies.
- chat message gaps if Chat API is available.
- Telegram callback without completed action or expiry.
- outbox records stuck in pending/running state.
- work queue leases expired without recovery.

Each check writes to `data_quality_checks` and creates or updates `operator_tasks` for actionable issues.

Watermark rules:

- store per-source cursors in `inbox_offsets`.
- store polling windows and result counts in `reconciliation_runs`.
- use overlapping polling windows to avoid missing delayed provider updates.
- dedupe overlap by source id and checksum.
- never advance a cursor until fetched data is written and committed.

### Database Health Tuning

Operational settings for SQLite phase:

- WAL mode enabled.
- foreign keys enabled.
- busy timeout configured.
- short write transactions.
- separate report snapshot reads from hot write paths.
- scheduled `PRAGMA integrity_check`.
- scheduled `ANALYZE`.
- controlled `VACUUM` only during maintenance windows.
- backup through SQLite online backup or safe snapshot, not raw copy during active writes unless using a proven method.

Database health metrics:

- write latency.
- read latency for key queries.
- queue lease recovery count.
- SQLite busy/locked count.
- WAL size.
- database size.
- slow query samples.
- index usage review.
- reconciliation drift count.
- data quality check failure count.

### Repair Workflows

Repair paths:

- replay event by id.
- replay reconciliation window.
- rebuild domain snapshot from event log.
- refetch one order/product/return/conversation.
- regenerate shipping document metadata from archive.
- rebuild Excel export from saved source watermark.
- mark issue as manually resolved with operator audit.

Every repair must produce an audit record with before/after counts and affected ids.

## Engine Design and Tuning

The engine must be strong enough to handle event ingestion, product knowledge, chat decisions, Excel reports, and Telegram control without becoming fragile. It should use explicit pipelines, bounded concurrency, and measurable quality gates.

### Execution Engine

Use a database-backed work queue inside the modular monolith for phase one. Each unit of work should have:

- `work_id`.
- `event_id`.
- `action_type`.
- `idempotency_key`.
- `priority`.
- `attempt_count`.
- `lease_until`.
- `status`.
- `last_error`.
- `created_at`, `started_at`, `finished_at`.

Worker pools:

- `ingest`: normalize and store events.
- `router`: dispatch events to agents.
- `actions`: execute Shopee, Telegram, and file side effects.
- `sync`: polling and reconciliation.
- `reports`: Excel generation and scheduled recaps.
- `llm`: classification, summaries, and drafts.

Queue priorities:

1. Safety-critical alerts and auth failures.
2. High-risk customer escalations.
3. Order/logistics actions.
4. Medium-risk approvals.
5. Reconciliation.
6. Reports and exports.
7. Low-priority knowledge refresh.

### State and Concurrency Rules

- Use idempotency keys for every external action.
- Use leases for queued work so crashed workers can recover.
- Use per-order and per-conversation locks to avoid conflicting actions.
- Do not run two customer replies for the same conversation at once.
- Do not generate two labels for the same order/action key.
- Do not block event ingestion while reports or LLM calls run.
- Store every agent decision before executing side effects.

### Agent Orchestration

Agents should run as deterministic pipelines where possible:

```text
Context Build -> Rule Checks -> LLM Assist if needed -> Policy Gate -> Action Request -> Audit
```

LLM output is advisory unless the policy marks the action as low-risk and auto-send eligible. Rule checks and policy gates always win over LLM suggestions.

### Tuning Loops

The system should improve through measured feedback:

- operator override tracking.
- false auto-reply incident tagging.
- approval latency tracking.
- escalation reason analysis.
- product knowledge gap count.
- stale product fact count.
- settlement mismatch patterns.
- repeated Shopee API error clustering.

Tuning artifacts:

- policy matrix version.
- prompt version.
- product knowledge version.
- report query version.
- simulator scenario version.

Every autonomous decision should record the versions it used. This makes later audits possible.

### Audit and Optimization Workflow

Run scheduled audits:

- daily safety audit: auto-sent chats, high-risk detections, failed actions.
- daily data audit: stale products, missing SKU mappings, sync drift, partial reports.
- weekly policy audit: overrides, escalations, false positives, false negatives.
- weekly finance audit: settlement mismatches and unresolved anomalies.
- weekly performance audit: queue latency, API error rates, report generation time, slow DB queries.

Optimization rules:

- optimize noisy alerts before adding more alert types.
- improve product knowledge before expanding auto-reply scope.
- improve simulator coverage before enabling new auto-actions.
- tune thresholds from operator corrections, not intuition alone.
- keep high-risk actions human-gated even if model confidence is high.

### Quality Gates

Before enabling an automation in production:

- simulator scenario passes.
- idempotency test passes.
- policy matrix test passes.
- audit fields are populated.
- Telegram approval/fallback path works.
- failure mode is defined.
- rollback or pause path exists.

No agent is considered production-ready until it has a replayable test set and an operator override path.

### Performance Targets

Initial targets:

- Telegram callback acknowledgement: under 2 seconds.
- Event ingestion acknowledgement: under 1 second after signature validation and event write.
- Low-risk chat decision: under 10 seconds if no API outage.
- Label generation action: under 30 seconds excluding Shopee-side delay.
- Daily Excel report generation: under 60 seconds for one shop's normal daily volume.
- Health command response: under 3 seconds from local state.

These are tuning targets, not hard guarantees. The system should alert when it misses them repeatedly.

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
- shipping document download success and failure.
- label/print queue backlog.
- print job success and failure.
- average time from eligible order to print-ready document.
- orders skipped from batch print by reason.
- open operator task count by severity.
- average exception resolution time.
- fulfillment SLA risk count.
- chat SLA risk count.
- return/dispute deadline risk count.
- product listing hygiene gap count.
- promotion margin warning count.
- account health warning count.
- data quality check failure count.
- reconciliation drift count by domain.
- inbox cursor lag by source.
- outbox stuck count.
- expired queue lease recovery count.
- SQLite busy/locked count.
- slow query count.
- backup success/failure and restore test age.
- Telegram callback acknowledgement latency.
- queue backlog and age by worker pool.
- report generation duration.
- product knowledge freshness and gap count.
- operator override rate by policy version.
- auto-action error rate by action type.

Telegram commands:

- `/health`: service, database, Shopee auth, scheduler, dead-letter count, and last sync.
- `/agenda`: show the daily operating agenda and top recommended actions.
- `/inbox`: show open exceptions grouped by severity and category.
- `/find <query>`: search order, order number, SKU, product alias, customer, or task.
- `/orders risk`: show orders close to SLA breach, missing label, or blocked fulfillment.
- `/products gaps`: show product knowledge and listing hygiene gaps.
- `/promos`: show active promos, ending promos, and margin warnings when data is available.
- `/customers sensitive`: show conversations/customers in sensitive or human-only mode.
- `/db health`: show database size, WAL size, lock count, slow queries, backup status, and integrity check status.
- `/sync audit`: show reconciliation coverage, drift count, cursor lag, and latest repair actions.
- `/repair <subject>`: owner-only guided repair for refetch/replay/rebuild actions.
- `/summary today`: orders, labels, chat automation, escalations, finance anomalies.
- `/export orders today`: create and send an order workbook.
- `/export finance month`: create and send a finance workbook.
- `/export inventory`: create and send an inventory workbook.
- `/export chats`: create and send a chat automation workbook.
- `/export audit month <month>`: create a workbook in the `auditshopeedef.xlsx` monthly audit shape.
- `/export audit year`: create all month sheets in the Shopee monthly audit shape.
- `/labels ready`: show ready-to-print shipping documents.
- `/labels batch`: create a batch label bundle.
- `/print queue`: show pending, printed, and failed print jobs.
- `/packing today`: create picklist and packing batch for today's eligible orders.
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
- Shopee audit workbook template fill tests.
- Shopee audit workbook formula and style preservation tests.
- Shopee audit workbook row overflow tests.
- report template rate mismatch warning tests.
- shipping document lifecycle tests.
- print job idempotency tests.
- batch label grouping tests.
- document archive checksum tests.
- print queue failure and retry tests.
- operations inbox ranking tests.
- daily agenda generation tests.
- SLA watch tests.
- product listing hygiene tests.
- promotion margin warning tests.
- `/find` lookup tests across order, SKU, product alias, customer, and task.
- database uniqueness and foreign key tests.
- outbox idempotency recovery tests.
- reconciliation watermark tests.
- overlapping polling dedupe tests.
- data quality check tests.
- backup and restore smoke tests.
- SQLite WAL/integrity check verification.
- key query index plan tests.
- product knowledge freshness and fallback tests.
- customer dynamics state transition tests.
- Telegram menu and callback idempotency tests.
- alert severity routing tests.
- work queue lease and retry tests.
- per-order and per-conversation lock tests.
- audit/version stamping tests.
- failure injection for duplicate webhook, API timeout, token expiry, database retry, and LLM timeout.

Simulator scenarios:

- new paid order.
- order ready for shipping document.
- shipping document task pending then ready.
- shipping document task failed.
- batch label generation with mixed couriers.
- duplicate print request.
- order skipped from print batch due to custom request.
- daily agenda with mixed order, chat, finance, and stock tasks.
- SLA breach approaching.
- product listing missing weight or stale stock.
- promo margin below threshold.
- account health penalty alert.
- missed webhook repaired by overlapping polling.
- duplicate provider update deduped by checksum.
- outbox crash after provider send.
- stale cursor blocked from advancing.
- database backup and restore smoke scenario.
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
- Telegram menu, action card, callback idempotency, roles, and alert severity.
- Database-backed work queue with leases, priorities, and retry handling.
- Database correctness layer with constraints, outbox, inbox offsets, reconciliation runs, and data quality checks.
- Order, logistics, and finance skeleton agents.
- Operations Supervisor Agent with agenda, inbox, SLA watch, and `/find` lookup in simulator mode.
- Reporting Agent with daily summary and Excel writer.
- Shopee monthly audit workbook template adapter for `auditshopeedef.xlsx`.
- Product Knowledge Base schema and import/sync skeleton.
- Shipping document action in dry-run/simulator mode.
- Print and Document Agent with archive, batch bundle, and Telegram delivery in simulator mode.
- Test harness and simulator fixtures.

### Phase 2: Shopee Production Integration

- Real signed Shopee client.
- Token refresh persistence.
- Real order detail and order list sync.
- Real logistics document generation.
- Real shipping document download and archive.
- Print-ready label/AWB/resi bundle delivery through Telegram.
- Product catalog and variant sync.
- Account health sync where API permission allows it.
- Promotion state sync where API permission allows it.
- Listing health checks from product catalog data.
- First production Excel reports from real order, item, finance, and inventory data.
- First production Shopee monthly audit workbook from real order and settlement data.
- Reconciliation jobs.
- `/db health`, `/sync audit`, and owner-only repair commands.
- Dead-letter replay.
- Daily Telegram summaries.
- Production audit jobs for safety, data freshness, and queue health.

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
- Prompt, policy, and threshold tuning loop.
- Customer memory and unresolved promise tracking.

### Phase 4: Returns, Disputes, Inventory, and Learning Loop

- Return/dispute triage.
- Inventory cache and stock movement alerts.
- Product knowledge quality scoring.
- Promotion and listing optimization recommendations.
- Account health and SLA trend reports.
- Advanced Excel recaps for weekly/monthly operations.
- Finance anomaly tuning.
- Operator correction feedback.
- Risk threshold tuning.
- Migration path to PostgreSQL if volume requires it.
- Performance optimization based on real queue, API, report, and operator latency data.
- PostgreSQL migration readiness review if SQLite contention or report load exceeds thresholds.

## Out of Scope for Initial Build

- Web dashboard.
- Full auto-ship workflow.
- Direct physical printer integration before printer target and VPS environment are explicitly configured.
- Final automated refund, dispute, or compensation decisions.
- Autonomous promo creation, deletion, or price changes before policy and margin gates are proven.
- Review/rating automation unless an official API/export/manual import source is available.
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
- The `auditshopeedef.xlsx` report shape should be treated as a versioned business template. Do not hardcode column positions without a template schema and validation test.
- Direct printing should be an optional adapter. The core system must first produce archived, print-ready documents reliably.
- Seller Center replacement should prioritize visibility and supervised actions first. Do not add autonomous write actions until the read/alert/approval loop is reliable.
- No cursor, watermark, or offset should advance until its source data and derived state are committed or safely queued for processing.
- Database tuning must be evidence-driven from lock counts, query latency, drift counts, and backup/restore tests.
- Product knowledge must be treated as a safety dependency for customer-facing answers.
- "Perfect" should mean audited, measured, recoverable, and continuously tuned. It must not mean fully autonomous decisions for high-risk cases.

## Acceptance Criteria

The design is ready for implementation planning when:

- all event sources produce normalized events.
- all agent actions pass through Policy Engine and Action Executor.
- low, medium, and high risk paths are explicit.
- Telegram can show action reason, evidence, approval buttons, and audit status.
- Telegram can request and receive Excel recap files.
- the system can generate a Shopee monthly audit workbook matching `auditshopeedef.xlsx` layout, formulas, and column semantics.
- report generation flags the observed admin-rate mismatch instead of silently hiding it.
- the system can generate, download, archive, and deliver print-ready resi/AWB/label documents.
- print jobs and batch labels are idempotent, auditable, and recoverable.
- the agent can answer product questions only when product knowledge is present and fresh.
- the agent can detect customer mood, topic shifts, and escalation risk.
- Telegram control flows are usable through menus and inline action cards.
- Telegram provides an agenda, exception inbox, and cross-entity search so routine Seller Center checks are centralized.
- every automation has audit/version records, quality gates, and a pause or fallback path.
- queue workers can recover leased work without duplicate external side effects.
- database constraints and reconciliation jobs catch duplicate, missing, stale, and drifted records.
- backup and restore smoke tests pass before production operation.
- simulator can replay core workflows without Shopee credentials.
- real Shopee integration can be added behind gateway interfaces.
- tests cover idempotency, policy decisions, replay, and provider failure paths.
