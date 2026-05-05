# Project Walkthrough - Shopee Agent

This document provides a guide on how the system works and how to interact with it.

## 1. Setup
1. Configure `.env` with `TELEGRAM_BOT_TOKEN` and `GEMINI_API_KEY`.
2. Run migrations: `alembic upgrade head`.
3. Start the bot: `python src/shopee_agent/entrypoints/telegram/main.py`.

## 2. Operator Commands (Telegram)

### Monitoring & Operations
- `/health`: System and shop connectivity status.
- `/shops`: List all managed Shopee accounts.
- `/sync`: Global synchronization of orders, disputes, and inventory across all shops.
- `/agenda`: View the most critical tasks for today.
- `/inbox`: Browse the full queue of pending approvals and alerts.

### Customer Service
- `/chat [text]`: Test the classification and drafting logic for a buyer message.
- `/ask [query]`: Ask the LLM about product facts or shop policies.
- `/returns`: View and triage active return/refund disputes.

### Reporting
- `/report [year] [month]`: Generate a comprehensive Excel audit workbook.

## 3. Automation Workflow
1. **Low Risk**: (e.g., status check) -> Auto-replied if confidence is high.
2. **Medium Risk**: (e.g., stock question, simple complaint) -> Drafted by LLM -> Sent to `/inbox` for operator approval.
3. **High Risk**: (e.g., refund request, SLA breach) -> Escalated immediately to operator with evidence.

## 4. Key Files
- `src/shopee_agent/app/`: Core agent logic.
- `src/shopee_agent/providers/`: External integrations (Shopee API, Gemini LLM).
- `src/shopee_agent/persistence/`: Database models and repositories.
- `src/shopee_agent/entrypoints/telegram/`: Bot interface and message handlers.
