import logging
from typing import Any
from datetime import datetime
from sqlalchemy import select, func
from shopee_agent.persistence.models import ReviewRecord
from shopee_agent.providers.llm.gateway import LLMGateway

logger = logging.getLogger("shopee_agent.review")

class ReviewAgent:
    """Manages product reviews and automates professional responses."""
    
    def __init__(self, session, llm: LLMGateway | None = None):
        self.session = session
        self.llm = llm

    def sync_reviews(self, shop_id: str, raw_reviews: list[dict]):
        """Upsert reviews fetched from Shopee."""
        for r in raw_reviews:
            review_id = str(r.get("item_comment_id"))
            record = self.session.scalar(
                select(ReviewRecord).where(ReviewRecord.review_id == review_id)
            )
            
            if not record:
                record = ReviewRecord(
                    review_id=review_id,
                    order_sn=r.get("order_sn", ""),
                    shop_id=shop_id,
                    rating_star=r.get("rating_star", 5),
                    comment=r.get("comment", ""),
                    created_at=datetime.fromtimestamp(r.get("create_time", 0))
                )
                self.session.add(record)
        self.session.commit()

    async def draft_all_pending(self, shop_id: str) -> int:
        """Generate AI replies for all pending reviews."""
        if not self.llm:
            return 0
            
        stmt = select(ReviewRecord).where(
            ReviewRecord.shop_id == shop_id,
            ReviewRecord.status == "pending",
            ReviewRecord.reply_comment == None
        )
        pending = self.session.scalars(stmt).all()
        
        count = 0
        for rev in pending:
            prompt = (
                f"Tulis balasan profesional untuk ulasan pembeli Shopee berikut:\n"
                f"Rating: {rev.rating_star} Bintang\n"
                f"Komentar: \"{rev.comment}\"\n\n"
                f"Aturan:\n"
                f"1. Jika rating 5, ucapkan terima kasih dan ajak belanja lagi.\n"
                f"2. Jika rating rendah (<4), minta maaf dan tanya kendalanya.\n"
                f"3. Balas dalam Bahasa Indonesia yang ramah.\n"
                f"4. Jangan gunakan template kaku."
            )
            try:
                reply = await self.llm.generate_response(prompt)
                rev.reply_comment = reply.strip()
                count += 1
            except Exception as e:
                logger.error(f"Failed to draft review reply: {e}")
                
        self.session.commit()
        return count

    def get_pending_replies(self, shop_id: str):
        return self.session.scalars(
            select(ReviewRecord).where(
                ReviewRecord.shop_id == shop_id,
                ReviewRecord.status == "pending",
                ReviewRecord.reply_comment != None
            )
        ).all()
