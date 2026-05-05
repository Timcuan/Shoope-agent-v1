#!/usr/bin/env bash
set -e

# Shopee Agent 1-Click Setup Wizard

echo "=========================================================="
echo "    🚀 Selamat Datang di Shopee Agent Setup Wizard 🚀    "
echo "=========================================================="
echo ""

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚙️  File konfigurasi (.env) belum ditemukan."
    echo "Mari kita atur pengaturan awal Anda:"
    echo "------------------------------------------------"
    
    read -p "1. Masukkan Telegram Bot Token (dari @BotFather): " TG_TOKEN
    read -p "2. Masukkan Telegram Chat ID Anda (ID Admin): " ADMIN_ID
    read -p "3. Masukkan Shopee Partner ID (Opsional, tekan Enter untuk lewati): " SHOPEE_ID
    read -p "4. Masukkan Shopee Partner Key (Opsional, tekan Enter untuk lewati): " SHOPEE_KEY
    read -p "5. Masukkan Gemini API Key (Opsional, tekan Enter untuk lewati): " GEMINI_KEY
    read -p "6. Masukkan Model LLM (default: gemini-1.5-flash): " LLM_MODEL
    read -p "7. Masukkan OpenRouter API Key (Opsional, tekan Enter untuk lewati): " OPENROUTER_KEY
    read -p "8. Masukkan PrintNode API Key (Opsional, tekan Enter untuk lewati): " PRINTNODE_KEY
    read -p "9. Masukkan HTTP Proxy URL (Opsional, khusus VPS Luar Negeri): " HTTP_PROXY

    # Generate random API key for dashboard
    RANDOM_API_KEY=$(uuidgen || echo "secret_$(date +%s)")

    cat <<EOF > .env
APP_ENV=production
DATABASE_URL=sqlite:///./data/shopee_agent.db
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
ADMIN_CHAT_ID=${ADMIN_ID}
SHOPEE_PARTNER_ID=${SHOPEE_ID:-demo_id}
SHOPEE_PARTNER_KEY=${SHOPEE_KEY:-demo_key}
LLM_PROVIDER=gemini
LLM_MODEL=${LLM_MODEL:-gemini-1.5-flash}
GEMINI_API_KEY=${GEMINI_KEY:-demo_llm_key}
OPENROUTER_API_KEY=${OPENROUTER_KEY}
PRINTNODE_API_KEY=${PRINTNODE_KEY}
API_SECRET_KEY=${RANDOM_API_KEY}
HTTP_PROXY_URL=${HTTP_PROXY}
EOF

    echo ""
    echo "✅ File .env berhasil dibuat!"
else
    echo "✅ Konfigurasi (.env) sudah tersedia."
fi

echo ""
echo "⚙️  Menyiapkan Database..."
mkdir -p data

# Ensure virtual environment or dependencies are installed if running locally
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "🐳 Docker terdeteksi di sistem Anda."
    read -p "Apakah Anda ingin menjalankan sistem menggunakan Docker? (y/n) [default: y]: " USE_DOCKER
    USE_DOCKER=${USE_DOCKER:-y}
    
    if [[ "$USE_DOCKER" =~ ^[Yy]$ ]]; then
        echo "Menyiapkan dan membangun Container Docker..."
        docker-compose build
        echo "Menjalankan migrasi database via Docker..."
        docker-compose run --rm shopee-api alembic upgrade head
        echo "=========================================================="
        echo "🎉 Selesai! Sistem siap dijalankan."
        echo "Ketik perintah ini untuk memulai:"
        echo "👉  make start  (Untuk menyalakan sistem)"
        echo "👉  make url    (Untuk mendapatkan URL Webhook Shopee HTTPS Gratis!)"
        echo "=========================================================="
        exit 0
    fi
fi

# Fallback to local setup
echo "🐍 Menyiapkan instalasi Python lokal..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -e .
alembic upgrade head

echo "=========================================================="
echo "🎉 Selesai! Sistem siap dijalankan secara lokal."
echo "Ketik perintah ini untuk memulai layanan:"
echo "👉  ./start.sh api    (Untuk webhook server)"
echo "👉  ./start.sh bot    (Untuk bot telegram)"
echo "👉  ./start.sh worker (Untuk task worker)"
echo "Atau jalankan semuanya dengan terminal terpisah."
echo "=========================================================="
