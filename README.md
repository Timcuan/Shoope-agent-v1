# 🚀 Shopee Agent v1.1

**Telegram-Supervised Shopee Multi-Shop Orchestration Engine.**

Shopee Agent is a highly resilient, production-ready system designed to manage multiple Shopee shops autonomously. It maximizes operational efficiency by automating logistics, integrating advanced analytics, and providing a premium AI-powered chat interface—all controlled via Telegram.

---

## ✨ Key Features

- **🏪 Multi-Shop Orchestration**: Unified management of multiple shops with data isolation.
- **📈 Business Intelligence (BI)**: Daily performance snapshots and proactive low-stock alerts.
- **☁️ Cloud Audit Sync**: Automated synchronization of audit logs to Google Sheets for team collaboration.
- **🛡️ Autonomous Dispute Defense**: AI-powered evidence gathering for return cases (Logistics & Weight analysis).
- **📦 Logistics Perfection**: Arrange shipments (`/ship`) and download Waybill PDFs (`/label`) directly from Telegram.
- **💬 AI Chat Support**: Auto-triage buyer messages, detect sentiment, and translate multi-language chats.
- **📊 Advanced Analytics**: 14-sheet detailed Excel workbooks with automated profit margin formulas.
- **🔥 God-Tier Resilience**: Worker watchdogs, auto-token repair, and DB pool pre-ping.

---

## 🛠️ Architecture

The system is built on a modular "Agentic" architecture:
- **`OperationsSupervisor`**: Task lifecycle management and prioritization.
- **`LogisticsAgent`**: Waybill generation and shipment orchestration.
- **`AnalyticsAgent`**: Financial and operational KPI aggregation.
- **`NotificationAgent`**: Proactive alert dispatching logic.
- **`ChatAgent`**: LLM-powered buyer message classification and drafting.

---

## 🚀 1-Click Setup (Sangat Mudah!)

Sistem ini didesain agar sangat mudah dijalankan tanpa perlu mengonfigurasi banyak hal secara manual. Cukup gunakan satu perintah di terminal Anda:

```bash
make setup
```

**Apa yang dilakukan `make setup`?**
1. Mengecek kesiapan komputer Anda (Python/Docker).
2. Meminta Token Telegram dan API Key secara interaktif, lalu membuatkan file `.env` otomatis.
3. Menyiapkan dan melakukan migrasi basis data SQLite.
4. Menyiapkan kontainer Docker secara instan.

Setelah *setup* selesai, Anda bisa menjalankan seluruh agen dengan perintah:
```bash
make start
```

Untuk melihat status atau log agen Anda secara *real-time*:
```bash
make logs
```

Untuk menghentikan sistem:
```bash
make stop
```

---

## 🧪 Testing
The system comes with a comprehensive test suite (71+ tests) covering E2E flows, API resilience, and domain logic.
```bash
pytest
```

---

## 📄 Documentation
- [CHANGELOG.md](CHANGELOG.md): History of all development phases.
- [Walkthrough](docs/walkthrough.md): Guided tour of features.

---
*Developed by Antigravity AI for Shopee Sellers.*
