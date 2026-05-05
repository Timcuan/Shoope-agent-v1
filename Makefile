.PHONY: setup start stop logs restart clean url

setup:
	@./setup.sh

start:
	@echo "Memulai semua servis Shopee Agent di latar belakang..."
	@docker-compose up -d --build
	@echo "Servis berjalan! Gunakan 'make logs' untuk melihat aktivitas."

stop:
	@echo "Menghentikan semua servis Shopee Agent..."
	@docker-compose down

restart: stop start

logs:
	@docker-compose logs -f

clean:
	@echo "Membersihkan container dan volume data..."
	@docker-compose down -v
	@rm -rf data/
	@echo "Sistem bersih."

url:
	@echo "Mengekstrak Cloudflare URL..."
	@docker-compose logs cloudflare-tunnel | grep -o 'https://[^[:space:]]*\.trycloudflare\.com' | tail -n 1

