import logging
import json
from datetime import datetime
from shopee_agent.contracts.reporting import ReportRequest

logger = logging.getLogger("shopee_agent.gsheets")

class GSheetsAgent:
    """Synchronizes audit data to Google Sheets for real-time collaboration."""
    
    def __init__(self, service_account_json: str | None = None, admin_email: str | None = None):
        self.creds = service_account_json
        self.admin_email = admin_email
        self.enabled = service_account_json is not None

    async def sync_audit_report(self, request: ReportRequest) -> str:
        """
        Synchronizes report data to a Google Sheet with professional formatting.
        """
        if not self.enabled:
            logger.warning("Google Sheets integration is not configured. Returning mock link.")
            return f"https://docs.google.com/spreadsheets/d/mock_{request.shop_id}_{request.year}_{request.month}/edit"

        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            # 1. Auth & Connection
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds_data = json.loads(self.creds)
            credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
            gc = gspread.authorize(credentials)
            
            # 2. Spreadsheet Setup
            title = f"SHOPEE_AUDIT_{request.shop_id}_{request.year}_{request.month:02d}"
            try:
                sh = gc.open(title)
            except gspread.SpreadsheetNotFound:
                sh = gc.create(title)
                if self.admin_email:
                    sh.share(self.admin_email, perm_type='user', role='writer')
            
            ws = sh.get_worksheet(0)
            data_sheet_name = f"Audit_{request.month:02d}_{request.year}"
            ws.update_title(data_sheet_name)
            
            # 3. Data Preparation (Audit Sheet)
            headers = [
                "NO", "TGL TERIMA", "TGL KIRIM", "TGL SELESAI", 
                "NO. PESANAN", "NAMA PRODUK", "HARGA JUAL", 
                "BIAYA KOMISI", "BIAYA LAYANAN", "TOTAL POTONGAN",
                "EST. PENDAPATAN", "DANA DITERIMA", "SELISIH", "STATUS"
            ]
            
            rows = [headers]
            for i, t in enumerate(request.transactions, start=1):
                row_idx = len(rows) + 1
                # If we have actual fees, use them. Otherwise estimate.
                admin_fee = t.biaya_admin if t.biaya_admin > 0 else f"=G{row_idx}*{request.admin_rate}"
                service_fee = t.biaya_layanan
                
                rows.append([
                    i,
                    t.received_at.strftime("%Y-%m-%d") if t.received_at else "",
                    t.shipped_at.strftime("%Y-%m-%d") if t.shipped_at else "",
                    t.completed_at.strftime("%Y-%m-%d") if t.completed_at else "",
                    t.order_sn,
                    t.order_label, # Using label as name placeholder
                    t.order_amount,
                    admin_fee,
                    service_fee,
                    f"=H{row_idx}+I{row_idx}",
                    f"=G{row_idx}-J{row_idx}",
                    t.dana_diterima,
                    f"=L{row_idx}-K{row_idx}",
                    f"=IF(ABS(M{row_idx})<100, \"✅ MATCH\", \"🚨 CHECK\")"
                ])
            
            ws.clear()
            ws.update("A1", rows, raw=False)
            
            # 4. Professional Formatting (Audit Sheet)
            ws.format("A1:N1", {
                "backgroundColor": {"red": 0.05, "green": 0.05, "blue": 0.15},
                "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
                "horizontalAlignment": "CENTER"
            })
            ws.freeze(rows=1)
            
            last_row = len(rows)
            if last_row > 1:
                ws.format(f"G2:M{last_row}", {"numberFormat": {"type": "CURRENCY", "pattern": "\"Rp\"#,##0"}})
            
            # 5. Create EXECUTIVE DASHBOARD
            try:
                db = sh.worksheet("📊 Dashboard")
            except gspread.WorksheetNotFound:
                db = sh.add_worksheet(title="📊 Dashboard", rows=20, cols=10)
            
            db.clear()
            db_rows = [
                ["RINGKASAN EKSEKUTIF BULANAN", "", "", ""],
                ["Periode", f"{request.month}/{request.year}", "Shop ID", request.shop_id],
                ["", "", "", ""],
                ["METRIK", "NILAI", "TARGET", "STATUS"],
                ["Total Volume Pesanan", f"=SUM('{data_sheet_name}'!G2:G{last_row})", "Rp 100,000,000", ""],
                ["Pendapatan Bersih (Settled)", f"=SUM('{data_sheet_name}'!L2:L{last_row})", "-", ""],
                ["Total Potensi Kerugian", f"=SUMIF('{data_sheet_name}'!M2:M{last_row}, \"<0\")", "Rp 0", ""],
                ["Akurasi Pencocokan", f"=COUNTIF('{data_sheet_name}'!N2:N{last_row}, \"*MATCH*\")/COUNTA('{data_sheet_name}'!N2:N{last_row})", "99%", ""],
                ["", "", "", ""],
                ["Terakhir Diperbarui", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Agen", "ShopeeOrchestrator v1.1.1"]
            ]
            db.update("A1", db_rows, raw=False)
            
            # Dashboard Formatting
            db.format("A1:D1", {"textFormat": {"bold": True, "fontSize": 14}, "horizontalAlignment": "CENTER"})
            db.format("A4:D4", {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}})
            db.format("B5:B7", {"numberFormat": {"type": "CURRENCY", "pattern": "\"Rp\"#,##0"}})
            db.format("B8", {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}})
            
            return sh.url
            
        except Exception as e:
            logger.error(f"GSheets Sync failed: {e}")
            # Fallback to mock to not break the flow if API fails
            return f"https://docs.google.com/spreadsheets/d/error_fallback_{request.shop_id}/edit"
