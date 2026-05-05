from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OrderData:
    order_sn: str
    shop_id: str
    status: str
    total_amount: float
    buyer_id: str | None = None
    pay_time: datetime | None = None
    ship_by_date: datetime | None = None
    data_json: str = "{}"


@dataclass
class LogisticsData:
    order_sn: str
    shop_id: str
    tracking_no: str | None = None
    logistics_channel: str | None = None
    ship_status: str = "pending"
    label_status: str = "not_generated"
    file_path: str | None = None


@dataclass
class FinanceLedgerData:
    order_sn: str
    shop_id: str
    escrow_amount: float = 0.0
    commission_fee: float = 0.0
    service_fee: float = 0.0
    shipping_fee: float = 0.0
    estimated_income: float = 0.0
    final_income: float = 0.0
    settlement_status: str = "pending"
    data_json: str = "{}"


@dataclass
class InventoryItem:
    shop_id: str
    item_id: str
    name: str
    model_id: str = ""
    sku: str | None = None
    stock: int = 0
    reserved_stock: int = 0
    price: float = 0.0
