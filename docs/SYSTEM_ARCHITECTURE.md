# System Architecture - Shopee Intelligence Engine

![Intelligence Sovereign Architecture](/Users/aaa/.gemini/antigravity/brain/36c0ec50-89c5-444b-b248-a91de409dd32/shopee_intelligence_architecture_3d_1777959438110.png)

Shopee Intelligence Engine adalah sistem otomasi modular yang dirancang untuk menangani operasional e-commerce skala besar menggunakan kombinasi aturan deterministik dan kecerdasan LLM (Large Language Model).

## 1. High-Level Architecture (Elite Agentic Flow)

Sistem menggunakan pola **Event-Driven Agentic Architecture** dengan lapisan orkestrasi yang cerdas:

```mermaid
graph TB
    subgraph "External Ecosystem"
        SAPI[Shopee API v2]
        LLM[Gemini 2.5 Flash]
        GCloud[Google Cloud / Sheets]
    end

    subgraph "Sovereign Intelligence Engine"
        direction TB
        subgraph "Interface Layer"
            Bot[Telegram Elite Assistant]
            Web[Executive Dashboard]
        end

        subgraph "Orchestration Layer"
            Supervisor[Operations Supervisor]
            Engine[Decision Engine v3.0]
            Resilient[Resilient LLM Gateway]
        end

        subgraph "Autonomous Agents"
            Order[Order Agent]
            Chat[Chat Agent]
            Finance[Finance Agent]
            Dispute[Dispute Agent]
            KB[Knowledge Agent]
        end
    end

    subgraph "Persistence & Security"
        DB[(SQLite WAL Mode)]
        Outbox[Event Outbox]
        Vault[Env Secret Vault]
    end

    %% Connections
    SAPI <--> Supervisor
    LLM <--> Resilient
    Resilient <--> Chat & Dispute & KB
    Supervisor <--> Engine
    Engine <--> Order & Chat & Finance & Dispute
    Order & Chat & Finance & Dispute <--> DB
    Bot <--> Supervisor
    Finance --> GCloud
    Supervisor --> Outbox
    
    %% Styling
    style LLM fill:#6e40c9,color:#fff
    style Resilient fill:#6e40c9,color:#fff
    style Supervisor fill:#238636,color:#fff
    style Engine fill:#238636,color:#fff
    style Bot fill:#1f6feb,color:#fff
    style DB fill:#d29922,color:#000
```

## 2. Core Components (Agent Layers)

### 🧩 Domain Agents
- **Order Agent**: Mengelola siklus hidup pesanan dan pemantauan SLA.
- **Logistics Agent**: Menangani pelacakan dan dokumen pengiriman (PDF Waybill).
- **Finance Agent**: Rekonsiliasi penyelesaian dana dan deteksi anomali margin.
- **Inventory Agent**: Sinkronisasi stok dan identifikasi produk yang tidak aktif.
- **Chat Agent**: Klasifikasi niat pembeli dan pembuatan draf balasan (LLM-assisted).
- **Dispute Agent**: Triase pengembalian dana dan perangkuman bukti foto (Vision AI).
- **Product Knowledge Agent**: Mengelola Basis Pengetahuan Produk lokal (KB) yang bisa dipelajari.

### 🧠 Intelligence Layers
1. **Deterministic Filter**: Klasifikasi berbasis kata kunci untuk keandalan 100% pada kasus umum.
2. **LLM Reasoning (Gemini)**: Analisis mendalam terhadap mood pembeli, isi foto, dan pembuatan respon natural.
3. **Resilient Wrapper**: Mekanisme retry otomatis dan failover antar provider AI untuk menjamin bot tidak pernah "bisu".

### 💎 Living UX Layer (Telegram)
- **Typing Management**: Sinkronisasi status "mengetik" dengan durasi pemrosesan AI.
- **Global Error Boundary**: Pembungkus try-except pada setiap handler untuk mencegah crash total.
- **Human-In-The-Loop (HITL)**: Antarmuka persetujuan (Inbox) untuk tugas-tugas berisiko tinggi.

## 3. Alur Data (Lifecycle)
1. **Ingest**: Data ditarik dari Shopee setiap 3 menit (Polling/Sync).
2. **Analyze**: Agen mengevaluasi data terhadap kebijakan lokal dan wawasan AI.
3. **Decision**: Agen menghasilkan `Decision` (Otomasi, Draf, atau Eskalasi).
4. **Task**: Jika intervensi manusia dibutuhkan, `OperatorTask` dibuat di Inbox Telegram.
5. **Action**: Panggilan API Shopee hanya dilakukan setelah persetujuan manusia atau tingkat kepercayaan AI >95%.

## 4. Multi-Shop Orchestration
- Setiap data diisolasi secara ketat menggunakan `shop_id`.
- Token akses dikelola secara otomatis (auto-refresh) per toko.
- Mendukung agregasi data global (Dashboard) untuk melihat performa seluruh jaringan toko dalam satu layar.

---
*Arsitektur ini dioptimalkan untuk skalabilitas dan ketahanan produksi (v3.0.0).*
