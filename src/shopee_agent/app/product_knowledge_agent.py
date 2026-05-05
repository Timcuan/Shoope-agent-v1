from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from shopee_agent.contracts.knowledge import FAQEntry, ProductFact, ProductVariant
from shopee_agent.persistence.repositories import ProductKnowledgeRepository

logger = logging.getLogger("shopee_agent.knowledge")


class ProductKnowledgeAgent:
    """
    Manages the full product knowledge base for AI-assisted customer service.
    Ensures the AI has accurate, up-to-date product data before responding to buyers.
    """

    def __init__(self, pk_repo: ProductKnowledgeRepository) -> None:
        self.pk_repo = pk_repo

    def upsert_product_from_api(self, shop_id: str, raw_item: dict) -> None:
        """
        Parse a full Shopee API item response and upsert into the knowledge base.
        Handles: name, category, price range, variants/models, weight,
                 condition, description, and spec attributes.
        Preserves operator-curated FAQ, aliases, selling_points, forbidden_claims.
        """
        item_id = str(raw_item.get("item_id", raw_item.get("id", "")))
        name = raw_item.get("item_name", raw_item.get("name", "Unknown"))
        category = str(raw_item.get("category_id", ""))

        # --- Parse price range ---
        price_info = raw_item.get("price_info", [])
        prices = [p.get("current_price", 0) for p in price_info if p.get("current_price")]
        price_min = min(prices) if prices else raw_item.get("price", 0.0)
        price_max = max(prices) if prices else raw_item.get("price", price_min)

        # --- Parse variants/models ---
        variants: list[ProductVariant] = []
        models = raw_item.get("models", [])
        for m in models:
            model_name = " / ".join(
                v.get("name", "") for v in m.get("tier_index", [])
            ) or m.get("model_name", "Default")
            tier_price = m.get("price_info", {}).get("current_price", 0)
            variants.append(ProductVariant(
                model_id=str(m.get("model_id", "")),
                name=model_name,
                price=float(tier_price) if tier_price else 0.0,
                stock=m.get("stock_info", {}).get("current_stock", 0),
                sku=m.get("model_sku", ""),
            ))

        # --- Parse physical attributes ---
        weight_gram = raw_item.get("weight", 0)
        condition = "USED" if raw_item.get("condition") == "USED" else "NEW"
        description = raw_item.get("description", "")

        # --- Parse spec attributes ---
        spec_json: dict = {}
        for attr in raw_item.get("attributes", []):
            attr_name = attr.get("attribute_name", "")
            attr_val = attr.get("attribute_value_list", [{}])[0].get("display_value_name", "")
            if attr_name and attr_val:
                spec_json[attr_name] = attr_val

        # --- Preserve operator-curated fields ---
        existing = self.pk_repo.get_pk(shop_id, item_id)
        faq = existing.faq if existing else []
        aliases = existing.aliases if existing else []
        selling_points = existing.selling_points if existing else []
        forbidden_claims = existing.forbidden_claims if existing else []

        fact = ProductFact(
            item_id=item_id,
            shop_id=shop_id,
            name=name,
            category=category,
            price_min=price_min,
            price_max=price_max,
            variants=variants,
            weight_gram=weight_gram,
            condition=condition,
            description=description,
            spec_json=spec_json,
            selling_points=selling_points,
            forbidden_claims=forbidden_claims,
            faq=faq,
            aliases=aliases,
        )
        self.pk_repo.upsert_pk(fact)
        logger.info(f"[KB] Upserted product {item_id} ({name}) — {len(variants)} variants")

    def enrich_from_inventory(self, shop_id: str, item_id: str, inventory_items: list) -> None:
        """
        Sync live stock counts per variant from the Inventory repository into ProductFact.
        Call after every inventory sync to keep stock data fresh.
        """
        fact = self.pk_repo.get_pk(shop_id, item_id)
        if not fact:
            return

        inventory_map = {str(i.model_id): i.stock for i in inventory_items}
        for v in fact.variants:
            if v.model_id in inventory_map:
                v.stock = inventory_map[v.model_id]

        self.pk_repo.upsert_pk(fact)

    def add_faq(self, shop_id: str, item_id: str, question: str, answer: str) -> None:
        """Add an operator-approved FAQ entry to a product."""
        fact = self.pk_repo.get_pk(shop_id, item_id)
        if not fact:
            raise ValueError(f"Product {item_id} not found in knowledge base")
        if not any(f.question == question for f in fact.faq):
            fact.faq.append(FAQEntry(question=question, answer=answer))
            self.pk_repo.upsert_pk(fact)

    def add_selling_point(self, shop_id: str, item_id: str, point: str) -> None:
        """Add an operator-approved selling point (used by AI for upselling)."""
        fact = self.pk_repo.get_pk(shop_id, item_id)
        if not fact:
            raise ValueError(f"Product {item_id} not found in knowledge base")
        if point not in fact.selling_points:
            fact.selling_points.append(point)
            self.pk_repo.upsert_pk(fact)

    def add_forbidden_claim(self, shop_id: str, item_id: str, claim: str) -> None:
        """Add a claim the AI MUST NOT make about this product."""
        fact = self.pk_repo.get_pk(shop_id, item_id)
        if not fact:
            raise ValueError(f"Product {item_id} not found in knowledge base")
        if claim not in fact.forbidden_claims:
            fact.forbidden_claims.append(claim)
            self.pk_repo.upsert_pk(fact)

    def lookup(self, shop_id: str, query: str) -> ProductFact | None:
        """Find a product by name, alias, or ID via keyword matching."""
        from sqlalchemy import select
        from shopee_agent.persistence.models import ProductKnowledgeRecord

        query_lower = query.lower()
        records = self.pk_repo.session.scalars(
            select(ProductKnowledgeRecord).where(ProductKnowledgeRecord.shop_id == shop_id)
        ).all()

        for r in records:
            if query_lower in r.name.lower():
                return self.pk_repo.get_pk(shop_id, r.item_id)
            aliases = json.loads(r.aliases_json)
            if any(query_lower in a.lower() for a in aliases):
                return self.pk_repo.get_pk(shop_id, r.item_id)
            if query_lower == r.item_id.lower():
                return self.pk_repo.get_pk(shop_id, r.item_id)

        return None

    def build_context_for_ai(self, fact: ProductFact) -> str:
        """
        Format a ProductFact into a rich, structured text block
        ready to be injected into a Gemini AI prompt.
        Includes anti-hallucination guardrails.
        """
        lines = [
            f"=== DATA PRODUK RESMI DARI SISTEM ===",
            f"Nama: {fact.name}",
            f"Kondisi: {fact.condition}",
        ]

        # Price
        if fact.price_min and fact.price_max:
            if fact.price_min == fact.price_max:
                lines.append(f"Harga: Rp {fact.price_min:,.0f}")
            else:
                lines.append(f"Harga: Rp {fact.price_min:,.0f} – Rp {fact.price_max:,.0f}")

        # Weight
        if fact.weight_gram:
            lines.append(f"Berat: {fact.weight_gram} gram")

        # Variants
        if fact.variants:
            lines.append("Variasi yang Tersedia:")
            for v in fact.variants:
                stock_label = "Ready ✅" if v.stock > 0 else "Habis ❌"
                price_str = f" | Rp {v.price:,.0f}" if v.price else ""
                lines.append(f"  - {v.name}{price_str} | Stok: {stock_label} ({v.stock} pcs)")
        else:
            lines.append("Variasi: Tidak ada variasi (single item)")

        # Spec
        if fact.spec_json:
            lines.append("Spesifikasi:")
            for k, v in fact.spec_json.items():
                lines.append(f"  - {k}: {v}")

        # Description (truncate to 500 chars to avoid token overflow)
        if fact.description:
            desc = fact.description[:500].replace("\n", " ")
            if len(fact.description) > 500:
                desc += "..."
            lines.append(f"Deskripsi Singkat: {desc}")

        # Selling points
        if fact.selling_points:
            lines.append("Keunggulan Produk (gunakan untuk upselling):")
            for sp in fact.selling_points:
                lines.append(f"  ✅ {sp}")

        # FAQ
        if fact.faq:
            lines.append("FAQ yang Sudah Disetujui:")
            for f in fact.faq:
                lines.append(f"  Q: {f.question}")
                lines.append(f"  A: {f.answer}")

        # Forbidden claims — critical anti-hallucination rules
        if fact.forbidden_claims:
            lines.append("⛔ LARANGAN KERAS (JANGAN PERNAH SEBUTKAN):")
            for fc in fact.forbidden_claims:
                lines.append(f"  ❌ {fc}")

        lines.append(
            "\n[INSTRUKSI AI]: Gunakan HANYA data di atas untuk menjawab pertanyaan tentang produk ini. "
            "Jika pembeli menanyakan sesuatu yang TIDAK ada di data di atas, "
            "JANGAN mengarang jawaban. Katakan: 'Untuk info lebih lanjut, silakan hubungi kami langsung Kak.'"
        )

        return "\n".join(lines)

    def get_stale_items(self, shop_id: str, threshold_hours: int = 24) -> list[str]:
        """Return item_ids that haven't been refreshed in the knowledge base recently."""
        from sqlalchemy import select
        from shopee_agent.persistence.models import ProductKnowledgeRecord

        threshold_dt = datetime.now(UTC) - timedelta(hours=threshold_hours)
        ids = self.pk_repo.session.scalars(
            select(ProductKnowledgeRecord.item_id).where(
                ProductKnowledgeRecord.shop_id == shop_id,
                ProductKnowledgeRecord.freshness_at < threshold_dt
            )
        ).all()
        return list(ids)

    async def generate_promo_caption(self, shop_id: str, item_id: str, llm_gateway) -> str:
        """Generates a high-converting social media caption for a product."""
        fact = self.pk_repo.get_pk(shop_id, item_id)
        if not fact:
            return "❌ Produk tidak ditemukan dalam database."
            
        prompt = (
            f"Buatlah caption promosi Instagram/TikTok yang menarik untuk produk berikut:\n"
            f"Nama: {fact.name}\n"
            f"Deskripsi: {fact.description[:500]}\n"
            f"Selling Points: {fact.selling_points}\n\n"
            f"Gunakan emoji, bahasa yang santai tapi meyakinkan, dan berikan call-to-action ke Shopee."
        )
        
        caption = await llm_gateway.generate_response(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="Anda adalah ahli social media marketing yang spesialis menjual produk peternakan dan kandang ayam berkualitas tinggi."
        )
        return caption
