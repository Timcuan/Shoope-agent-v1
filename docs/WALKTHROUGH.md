# Project Walkthrough - Shopee Intelligence Engine

Dokumen ini memberikan panduan lengkap mengenai cara kerja sistem dan bagaimana berinteraksi dengan asisten pintar Anda.

## 1. Persiapan Cepat (Setup)
1.  Pastikan file `.env` telah terisi (gunakan `make setup`).
2.  Jalankan sistem menggunakan `make start` atau `docker-compose up -d`.
3.  Buka bot Telegram Anda dan tekan `/start`.

## 2. Navigasi Operator (Telegram UI)

### 📊 Dashboard & Monitoring
-   **`/dashboard`**: Ringkasan performa bisnis. Gunakan tombol inline untuk melihat statistik Harian, Mingguan, atau Bulanan.
-   **`/diagnose`**: Pengecekan kesehatan sistem secara menyeluruh (Database, LLM, API Shopee, dan Token).
-   **`/sync`**: Sinkronisasi manual untuk menarik data terbaru dari seluruh toko secara paralel.

### 📥 Manajemen Tugas (Inbox)
-   **`/inbox`**: Pusat kendali tugas. Setiap pesanan baru, komplain, atau stok rendah akan muncul di sini sebagai kartu tugas.
-   **`/agenda`**: Ringkasan tugas yang memiliki tenggat waktu (SLA) paling mendesak hari ini.
-   **`/find [keyword]`**: Mencari tugas atau pesanan berdasarkan nomor pesanan atau nama pembeli.

### 🤖 Fitur Cerdas (AI Capabilities)
-   **Analisis Foto**: Kirimkan foto paket atau produk, AI akan otomatis menganalisis kondisi dan memberikan saran teknis.
-   **Pesan Suara**: Kirimkan pesan suara untuk memberikan perintah cepat (seperti mengecek stok atau laporan).
-   **`/chat [pesan]`**: Simulasi analisis pesan pembeli. AI akan mengklasifikasikan niat pembeli dan menyiapkan draf balasan yang ramah.
-   **`/ask [pertanyaan]`**: Bertanya langsung pada AI mengenai pengetahuan produk atau kebijakan toko.

### 📦 Logistik & Stok
-   **`/packing`**: Melihat antrean pesanan yang siap dikemas. Anda bisa langsung mengatur pengiriman (`/ship`) dan mengunduh label PDF (`/label`) dari sini.
-   **`/stok`**: Cek ketersediaan barang di seluruh gudang.
-   **`/boost`**: Pantau status otomatisasi "Naikkan Produk" untuk meningkatkan visibilitas toko.

### 💰 Keuangan & Audit
-   **`/rekap`**: Pilih bulan dan tahun, sistem akan menyusun laporan Excel profesional dengan rincian margin per pesanan.
-   **`/finance`**: Pantau dana yang akan masuk (Escrow) dan status penyelesaian transaksi.

## 3. Alur Kerja Otomasi (Workflow)
Sistem bekerja dengan prinsip **Human-In-The-Loop (HITL)**:
1.  **Deteksi**: Bot memantau pesanan dan chat secara real-time (setiap 3 menit).
2.  **Klasifikasi**: AI menentukan apakah tugas tersebut berisiko rendah, sedang, atau tinggi.
3.  **Aksi**: 
    -   *Risiko Rendah*: Dibalas otomatis (opsional).
    -   *Risiko Sedang*: Dibuatkan draf balasan ➡️ Masuk ke `/inbox` untuk disetujui operator.
    -   *Risiko Tinggi*: Peringatan P0 dikirim ke admin ➡️ Memerlukan intervensi manusia segera.
4.  **Learning**: Jika AI ragu, tekan tombol "Ajarkan AI" agar sistem menjadi lebih pintar di masa depan.

## 4. Struktur Folder Utama
-   `src/shopee_agent/app/`: Otak sistem (Agent logic: Chat, Analytics, Logistics, dll).
-   `src/shopee_agent/providers/`: Integrasi eksternal (Shopee API v2, Gemini LLM).
-   `src/shopee_agent/persistence/`: Basis data (SQLite Models & Repositories).
-   `src/shopee_agent/entrypoints/telegram/`: Antarmuka Bot dan Handler pesan.

---
*Panduan ini mutakhir per versi 3.0.0 (Intelligence Sovereign).*
