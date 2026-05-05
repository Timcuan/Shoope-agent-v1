import logging

logger = logging.getLogger("shopee_agent.translation")

class TranslationAgent:
    """Handles multi-language translation for regional expansion."""
    
    def __init__(self, llm_gateway):
        self.llm = llm_gateway

    async def translate(self, text: str, target_lang: str = "Indonesian") -> str:
        """Translates text to the target language using AI."""
        if not text: return ""
        
        prompt = (
            f"Terjemahkan teks berikut ke dalam {target_lang}. "
            f"Pertahankan nada bicara yang sopan dan sesuai konteks e-commerce.\n\n"
            f"Teks: {text}"
        )
        
        translation = await self.llm.generate_response(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="Anda adalah penerjemah profesional yang ahli dalam bahasa e-commerce regional Asia Tenggara (ID, EN, MS, TH, VI)."
        )
        return translation

    async def detect_language(self, text: str) -> str:
        """Detects the language of the input text."""
        prompt = f"Deteksi bahasa dari teks ini. Kembalikan HANYA nama bahasanya saja (misal: English, Thai, Vietnamese).\n\nTeks: {text}"
        
        lang = await self.llm.generate_response(
            messages=[{"role": "user", "content": prompt}]
        )
        return lang.strip()
