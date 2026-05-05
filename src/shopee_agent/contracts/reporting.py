from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class AuditTransaction:
    """One row in the Shopee Audit Workbook (auditshopeedef format)."""
    row_no: int
    received_at: date | None       # B: TERIMA
    shipped_at: date | None        # C: KIRIM
    completed_at: date | None      # D: SELESAI
    order_label: str               # E: ORDER
    order_sn: str                  # F: NO PESANAN
    order_amount: float            # G: PESANAN (total order value)
    biaya_admin: float = 0.0       # H: Marketplace commission fee
    biaya_layanan: float = 0.0     # I: Service fees (Xtra Cashback/Ongkir)
    admin_rate: float = 0.02       # Fallback percentage if fees are missing
    dana_diterima: float = 0.0     # J: DANA DITERIMA (actual funds received from Shopee)
    keterangan: str = ""           # L: KETERANGAN


@dataclass
class ReportRequest:
    shop_id: str
    year: int
    month: int
    admin_rate: float = 0.02 # default for estimate
    creator: str = "operator"
    transactions: list[AuditTransaction] = field(default_factory=list)


@dataclass
class ReportResult:
    export_id: str
    file_path: str
    checksum: str
    report_type: str
    period_start: datetime
    period_end: datetime
    row_count: int
    total_revenue: float = 0.0
    total_received: float = 0.0
