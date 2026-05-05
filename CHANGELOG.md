# CHANGELOG - Shopee Agent

All notable changes to the Shopee Agent project are documented here.

## [v2.6.5] - 2026-05-05 (Living Elite Assistant)

### UX & Humanization (Elite Feel)
- **Typing Indicators**: Integrated `ChatAction.TYPING` across all high-latency handlers (AI Analysis, Reporting, Sync) to eliminate the "frozen bot" feel.
- **Friendly Indonesian Localization**: Full UI translation to natural Indonesian. Replaced technical jargon (e.g., "SLA Alert" -> "Peringatan SLA", "Order" -> "Pesanan").
- **Humanized Labeling**: Replaced "P0/P1" terminology with intuitive status icons (🔴 Sangat Mendesak, 📊 Menunggu).
- **Batch Notifications**: Implemented notification aggregation in `NotificationAgent` to prevent chat flooding during high-volume events.

### Stability & Production Hardening
- **Zero-Hang Architecture**: Wrapped all Telegram handlers (Command, Message, Callback) in robust `try-except` blocks with graceful user-facing error messages.
- **Security Audit**: Removed all hardcoded Shopee Partner IDs and Keys from `callbacks.py`. Now strictly environment-driven.
- **Session Safety**: Fixed critical `NameError` and `SessionLocal` scoping issues in `/chat` and `/diagnose` handlers.
- **Voice & Vision Resilience**: Added deep error handling to Multimodal handlers (Photo/Voice). Fixed `NameError` in voice command routing.
- **Near Real-time Sync**: Optimized `background_sync_task` interval from 30 minutes to 3 minutes for enterprise responsiveness.

### Intelligence & KB Features
- **Interactive KB Learning**: Implemented "Ajarkan AI" (KB Learn) capability. Users can now directly update the Product Knowledge Base from the Telegram UI when AI detects a gap.
- **Context-Aware Vision**: Improved Vision AI prompts for better logistics and stock analysis from photos.

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

## [v1.0.0] - 2026-05-04 (Final Perfection)

### Phase 17: AI-Powered Customer Support
- Integrated Shopee Chat API (`get_chat_list`, `send_message`).
- Added AI-suggested draft replies using `ChatAgent` (LLM-powered).
- Implemented `/chats` command for unified conversation management.

### Phase 16: Proactive Alerts & Background Sync
- Implemented background synchronization loop (periodic every 30 minutes).
- Added `NotificationAgent` for proactive push alerts on critical tasks (P0/P1).

### Phase 15: Premium UX & Flow Optimization
- Added Persistent Main Menu (Reply Keyboard) for no-typing navigation.
- Registered all commands with Telegram Bot API for native UI integration.

### Phase 14: System Robustness & Resilience
- Wrapped all Telegram callbacks in global error handling (try-except).
- Implemented real-world logistics logic (Ship Order & Print Label).

### Phase 13: Logistics Perfection
- Integrated Shipping Document API (Waybill PDF).
- Implemented `/ship` and `/label` commands.

### Phase 12: Analytics & Performance Dashboard
- Added `AnalyticsAgent` for KPI visualization.
- Implemented `/dashboard` command.

### Phase 11: Multi-Shop Token Automation
- Implemented Auto-Token Refresh logic.

### Phase 10: Multi-Shop Orchestration (Foundation)
- Migrated database schema to support `shop_id` isolation.

### Phase 9 - 1: Initial Development
- Core API Integration (Order, Return, Inventory).
- Operations Supervisor (Task Management).
- LLM Integration (Gemini) for Dispute analysis.
- Reporting Engine (Excel Audit Logs).
- Initial Telegram Bot UI.
