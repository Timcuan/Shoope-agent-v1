import logging
from pathlib import Path
import json
import asyncio
from datetime import datetime

logger = logging.getLogger("shopee_agent.logistics")

class InstructionGenerator:
    """
    Specialized Generator for Chicken Coop (Kandang Ayam) logistics.
    Focuses on materials, component dimensions, and quantity verification.
    """
    
    _lock = asyncio.Lock() # Class-level lock for file safety

    def __init__(self, output_dir: str = "./data/instructions") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_instruction_file(self, order_data: dict, product_facts: list = None) -> Path:
        """
        Creates a technical packing slip for coop assembly components.
        """
        async with self._lock:
            order_sn = order_data.get("order_sn", "UNKNOWN")
        buyer_note = order_data.get("message_to_seller", "-")
        items = order_data.get("item_list", [])
        buyer_name = order_data.get("recipient_address", {}).get("name", "Customer")
        
        content = [
            "  🏗️ KANDANG AYAM - PACKING  ",
            "===========================",
            f"ORDER: {order_sn}",
            f"BUYER: {buyer_name}",
            f"TGL  : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "===========================",
            "",
            "DAFTAR KOMPONEN & SPEK:",
            "-----------------------"
        ]
        
        # Map facts by item_id for easy lookup
        fact_map = {str(f.item_id): f for f in (product_facts or []) if f}
        
        for i, item in enumerate(items, 1):
            item_id = str(item.get("item_id", ""))
            name = item.get("item_name", "Unknown Item")
            qty = item.get("model_quantity_purchased", 1)
            var = item.get("model_name", "")
            
            content.append(f"#{i} [{qty}x] {name}")
            if var: content.append(f"   Varian: {var}")
            
            # Pull technical specs from Knowledge Base
            fact = fact_map.get(item_id)
            if fact:
                specs = fact.spec_json or {}
                bahan = specs.get("Bahan", specs.get("Material", "Kayu/Bambu"))
                dimensi = specs.get("Dimensi", specs.get("Ukuran", "-"))
                
                content.append(f"   🧵 Bahan  : {bahan}")
                content.append(f"   📏 Dimensi: {dimensi}")
            else:
                content.append("   ⚠️ Spek teknis tidak ditemukan di KB")
            
            content.append("")
            
        content.append("-----------------------")
        content.append("CHECKLIST KELENGKAPAN:")
        content.append(" [ ] Panel Utama")
        content.append(" [ ] Atap / Kawat Mesh")
        content.append(" [ ] Baut / Engsel (Set)")
        content.append(" [ ] Panduan Perakitan")
        content.append("-----------------------")
        content.append("")
        content.append("CATATAN KHUSUS:")
        content.append(f"\"{buyer_note}\"")
        content.append("")
        content.append("===========================")
        content.append("  SIAP KIRIM - TELITI YA!  ")
        content.append("===========================")
        
        file_path = self.output_dir / f"instruction_{order_sn}.txt"
        file_path.write_text("\n".join(content))
        return file_path
