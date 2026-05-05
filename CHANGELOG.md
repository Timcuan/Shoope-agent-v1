# CHANGELOG - Shopee Agent

All notable changes to the Shopee Agent project are documented here.

## [v1.1.0] - 2026-05-05 (Enterprise Autonomy & Intelligence)

### Autonomous Auditing & Finance
- **Google Sheets Cloud Sync**: Real-time audit synchronization to Google Sheets for team collaboration.
- **Enhanced Audit Workbook**: Re-architected Excel exports with 14 sheets (12 monthly, 1 Summary KPI, 1 Activity Log).
- **Financial Formulas**: Integrated dynamic Excel/GSheet formulas for margin calculation and reconciliation status.

### System Resilience (God-Tier)
- **Worker Watchdog**: Automated recovery for stalled background worker threads.
- **Auto-Token Repair**: Real-time token refresh and retry logic for expired Shopee sessions.
- **Database Hardening**: Implemented pool pre-ping and connection recycling for 24/7 stability.

### Proactive Intelligence
- **Business Intelligence (BI) Agent**: Automated daily performance snapshots with strategic AI insights.
- **Proactive Inventory Alerts**: Real-time notifications for low-stock items detected by background workers.
- **Dispute Evidence Agent**: Autonomous evidence gathering (logistics history & parcel weight) to defend against fraud.

### Premium Experience
- **Interactive Audit Flow**: Refactored `/rekap` with inline month/year selectors and visual progress updates.
- **AI Chat Intelligence**: Enhanced classification cards with sentiment analysis and risk indicators.
- **Clean Architecture**: Decoupled notification providers to ensure future scalability.

## [v1.0.0] - 2026-05-04 (Final Perfection)

### Phase 17: AI-Powered Customer Support
- Integrated Shopee Chat API (`get_chat_list`, `send_message`).
- Added AI-suggested draft replies using `ChatAgent` (LLM-powered).
- Implemented `/chats` command for unified conversation management.

### Phase 16: Proactive Alerts & Background Sync
- Implemented background synchronization loop (periodic every 30 minutes).
- Added `NotificationAgent` for proactive push alerts on critical tasks (P0/P1).
- Added `is_notified` flag to database for alert tracking.

### Phase 15: Premium UX & Flow Optimization
- Added Persistent Main Menu (Reply Keyboard) for no-typing navigation.
- Implemented Contextual Guidance (Post-sync buttons).
- Registered all commands with Telegram Bot API for native UI integration.

### Phase 14: System Robustness & Resilience
- Wrapped all Telegram callbacks in global error handling (try-except).
- Implemented real-world logistics logic (Ship Order & Print Label).
- Refactored session management to prevent connection leaks.

### Phase 13: Logistics Perfection
- Integrated Shipping Document API (Waybill PDF).
- Implemented `/ship` and `/label` commands.
- Added logistics action buttons to task notifications.

### Phase 12: Analytics & Performance Dashboard
- Added `AnalyticsAgent` for KPI visualization.
- Implemented `/dashboard` command with Revenue, Growth, and Dispute Rate metrics.

### Phase 11: Multi-Shop Token Automation
- Implemented Auto-Token Refresh logic (refreshes if < 15 mins left).
- Enforced shop isolation in all API gateways.

### Phase 10: Multi-Shop Orchestration (Foundation)
- Migrated database schema to support `shop_id` isolation.
- Refactored all repositories to require `shop_id` for queries.

### Phase 9 - 1: Initial Development
- Core API Integration (Order, Return, Inventory).
- Operations Supervisor (Task Management).
- LLM Integration (Gemini) for Dispute analysis.
- Reporting Engine (Excel Audit Logs).
- Initial Telegram Bot UI.
