import logging
from pathlib import Path

logger = logging.getLogger("shopee_agent.vision")

class VisionAgent:
    """Analyzes images sent to the bot (e.g., proof of packing, technical verification)."""
    
    def __init__(self, llm_gateway):
        self.llm = llm_gateway

    async def analyze_image(self, image_path: str, prompt: str = "Apa yang ada di foto ini? Jika ini produk kandang ayam, jelaskan kondisinya.") -> str:
        """Uses Gemini Vision to interpret the image."""
        try:
            # We assume the LLM gateway supports vision-enabled models (like gemini-1.5-flash)
            # In this implementation, we delegate to the gateway's specialized method.
            response = await self.llm.analyze_media(
                file_path=image_path,
                prompt=prompt
            )
            return response
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return "❌ Gagal menganalisis gambar. Pastikan format didukung."
