# 🚀 Shopee Agent v1.4.0 (Hardened Edition)

**Executive-Grade autonomous Shopee management ecosystem with Vision Intelligence and Financial Compliance.**

Shopee Agent is a production-grade orchestration engine designed for high-volume Shopee sellers. It provides full system autonomy, strict financial reconciliation, and AI-driven risk management—all wrapped in a premium glassmorphic executive dashboard.

---

## ✨ Key Features (Hardened)

- **👁️ Vision Intelligence**: Automated visual analysis of buyer evidence photos in disputes using Gemini Vision.
- **🛡️ Autonomous Dispute Defense**: "God-Tier" triage combining weight analysis, logistics status, and visual damage detection.
- **🚨 SLA Watchdog**: Proactive monitoring of shipping deadlines with P0/P1 alerts to prevent Shopee penalties.
- **⚖️ Financial Integrity**: Full Shopee API v2 Escrow compliance with standardized 14-column monthly GSheets audit reports.
- **🔒 AI Safety Guardrails**: Outbound chat filtering for PII (Phone numbers) and off-platform transaction detection.
- **📈 Premium Executive Dashboard**: High-fidelity glassmorphic UI with live activity feeds and animated KPI tracking.
- **🏪 Multi-Shop Orchestration**: Unified management of multiple shops with strict data isolation.
- **📦 Logistics Perfection**: Arrange shipments (`/ship`) and download Waybill PDFs (`/label`) directly from Telegram.
- **🔥 Institutional Resilience**: Worker watchdogs, auto-token repair, and persistent event outbox.

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
