# 🚀 Shopee Intelligence Engine v2.6.5 (Living Elite Edition)

[![Status: Production-Ready](https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg)]()
[![Build: Passed](https://img.shields.io/badge/Build-Passed-blue.svg)]()
[![Security: Hardened](https://img.shields.io/badge/Security-Hardened-orange.svg)]()
[![LLM: Gemini Multimodal](https://img.shields.io/badge/AI-Gemini%20Vision%20%2F%20Voice-purple.svg)]()

**Shopee Intelligence Engine** adalah ekosistem manajemen toko Shopee otonom kelas perusahaan yang menggabungkan Kecerdasan Buatan (Vision & Voice), Kepatuhan Finansial yang ketat, dan pengalaman pengguna Telegram yang ramah (Elite Personal Assistant).

---

## ✨ Fitur Unggulan (Elite Experience)

### 🤖 Kecerdasan Multimodal & Otonom
- **👁️ Vision AI Analysis**: Analisis otomatis foto bukti sengketa dan kondisi stok menggunakan Gemini Vision.
- **🎤 Voice Command Routing**: Kontrol operasional toko menggunakan pesan suara (Voice-to-Command).
- **🧠 Interactive KB Learning**: Fitur "Ajarkan AI" yang memungkinkan operator memperbarui basis pengetahuan produk langsung dari Telegram.
- **🛡️ Autonomous Dispute Defense**: Pertahanan otomatis terhadap klaim pembeli berdasarkan data berat paket, sejarah logistik, dan analisis visual.

### 💼 Operasional & Finansial (Zero-Error)
- **⚖️ Financial Reconciliation**: Audit otomatis sesuai standar Shopee API v2 dengan output Excel 14-kolom yang mendetail.
- **📈 Executive Dashboard**: Visualisasi KPI (Omzet, Pertumbuhan, Rate Komplain) secara real-time dengan UI premium.
- **📦 Logistics Orchestration**: Cetak label pengiriman (PDF) dan atur penjemputan (`/ship`) secara instan.
- **🚀 Product Booster**: Otomasi "Naikkan Produk" untuk 5 produk terlaris setiap 4 jam untuk traffic maksimal.

### 💎 User Experience (Living Assistant)
- **🇮🇩 Full Indonesian Localization**: Seluruh antarmuka menggunakan bahasa Indonesia yang natural dan ramah bagi operator non-teknis.
- **⚡ Zero-Hang Architecture**: Penggunaan *typing indicators* dan penanganan error global memastikan bot selalu responsif dan stabil.
- **📥 Task-Oriented Inbox**: Manajemen tugas berbasis prioritas (🔴 Sangat Mendesak, 📊 Menunggu) untuk memastikan tidak ada pesanan yang terlewat.

---

## 🛠️ Tech Stack & Architecture

Sistem ini dibangun dengan arsitektur **Agentic Micro-Services** yang modular:

- **Core**: Python 3.10+ (Asynchronous using `aiogram` & `asyncio`)
- **Intelligence**: Google Gemini (1.5 Flash/Pro) for Vision, Voice, and Reasoning.
- **Database**: SQLite (WAL Mode) with SQLAlchemy ORM for institutional resilience.
- **Infrastructure**: Docker & Docker Compose for rapid deployment and isolation.
- **Connectivity**: Shopee API v2 (Global Compliance) with auto-token repair mechanism.

---

## 🚀 Instalasi & Setup Cepat (1-Click)

Kami merancang sistem ini agar dapat dijalankan dalam hitungan menit tanpa konfigurasi teknis yang rumit.

### Prasyarat
- Docker & Docker Compose terinstal di komputer Anda.
- Token Telegram Bot (dari [@BotFather](https://t.me/botfather)).

### Langkah-langkah
1. **Clone & Setup**:
   ```bash
   git clone https://github.com/Timcuan/Shoope-agent-v1.git
   cd Shoope-agent-v1
   make setup
   ```
   *Perintah di atas akan mengecek ketergantungan sistem dan membuat file `.env` secara interaktif.*

2. **Jalankan Sistem**:
   ```bash
   make start
   ```

3. **Cek Status**:
   ```bash
   make logs
   ```

---

## 📱 Panduan Perintah Telegram (User Guide)

Gunakan perintah-perintah berikut untuk mengontrol asisten Anda:

| Perintah | Fungsi |
| :--- | :--- |
| `/start` | Memulai sesi dan menampilkan menu utama interaktif. |
| `/inbox` | Melihat tugas mendesak hari ini (Pesanan baru, Komplain, Stok rendah). |
| `/dashboard` | Menampilkan ringkasan performa toko (Omzet & Pertumbuhan). |
| `/rekap` | Mengunduh laporan keuangan bulanan dalam format Excel/GSheets. |
| `/chat` | Menganalisis pesan pembeli dan membuat draf balasan cerdas. |
| `/diagnose` | Pengecekan mandiri kesehatan sistem (DB, LLM, API Shopee). |
| `/sync` | Memicu sinkronisasi manual data toko di latar belakang. |

---

## 📄 Dokumentasi & Changelog
- [CHANGELOG.md](CHANGELOG.md): Sejarah lengkap pembaruan fitur.
- [docs/walkthrough.md](docs/walkthrough.md): Panduan mendalam fitur-fitur agen.
- [docs/api_compliance.md](docs/api_compliance.md): Detail implementasi kepatuhan API Shopee v2.

---
*Developed with ❤️ by Antigravity AI for Elite Shopee Sellers.*
*Copyright © 2026 Timcuan. All rights reserved.*
