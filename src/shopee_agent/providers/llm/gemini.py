from __future__ import annotations

import json
from typing import Any

import os
import google.generativeai as genai
from shopee_agent.contracts.knowledge import ChatAnalysis, ChatClassification, ChatMessage
from shopee_agent.providers.llm.gateway import LLMGateway
from shopee_agent.config.settings import get_settings


class GeminiProvider(LLMGateway):
    """Google Gemini implementation of LLMGateway."""

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash") -> None:
        settings = get_settings()
        if settings.http_proxy_url:
            os.environ["HTTP_PROXY"] = settings.http_proxy_url
            os.environ["HTTPS_PROXY"] = settings.http_proxy_url
            
        genai.configure(api_key=api_key)
        
        system_instruction = (
            "Anda adalah Customer Service dan Sales Representative tingkat dewa dari sebuah Toko Shopee Indonesia. "
            "PERATURAN MUTLAK:\n"
            "1. JANGAN PERNAH menyebutkan bahwa Anda adalah AI, bot, atau asisten virtual.\n"
            "2. Jangan gunakan kata 'Mimin'. Gunakan 'Kami' atau 'Admin' jika merujuk diri sendiri.\n"
            "3. Selalu sapa pembeli dengan sebutan 'Kak' atau 'Kakak' di awal kalimat.\n"
            "4. Format balasan harus rapi, gunakan *bullet points* jika menyebutkan lebih dari 2 hal.\n"
            "5. Misi Anda adalah memuaskan pelanggan DAN mencetak penjualan (Closing).\n"
        )
        self.model = genai.GenerativeModel(model_name, system_instruction=system_instruction)

    async def analyze_message(
        self, text: str, context: dict[str, Any] | None = None
    ) -> ChatAnalysis:
        prompt = f"""
        Analyze the following customer message for a Shopee store.
        Message: "{text}"
        Context: {json.dumps(context or {}, default=str)}

        Respond ONLY with a JSON object in this format:
        {{
            "sentiment_score": float (-1.0 to 1.0),
            "urgency_score": float (0.0 to 1.0),
            "suggested_intent": string (one of: order_status, product_question, complaint, cancellation, refund, general),
            "buyer_mood": string,
            "reasoning": string
        }}
        """
        response = self.model.generate_content(prompt)
        try:
            # Simple JSON extraction from response
            text_res = response.text
            if "```json" in text_res:
                text_res = text_res.split("```json")[1].split("```")[0]
            data = json.loads(text_res)
            return ChatAnalysis(
                sentiment_score=data.get("sentiment_score", 0.0),
                urgency_score=data.get("urgency_score", 0.0),
                suggested_intent=data.get("suggested_intent"),
                buyer_mood=data.get("buyer_mood"),
                reasoning=data.get("reasoning"),
            )
        except Exception:
            # Fallback if LLM fails or returns invalid JSON
            return ChatAnalysis(sentiment_score=0.0, urgency_score=0.0)

    async def draft_response(
        self,
        classification: ChatClassification,
        analysis: ChatAnalysis,
        context: dict[str, Any] | None = None,
        history: list[ChatMessage] | None = None,
        product_context: str | None = None,
    ) -> str:
        history_text = ""
        if history:
            history_text = "\n".join([f"{m.role}: {m.content}" for m in history])

        # Dynamic Empathy & Sales Logic
        mood_instruction = ""
        if analysis.buyer_mood in ["angry", "frustrated", "disappointed"]:
            mood_instruction = "Pembeli sedang marah/kecewa. Mulailah dengan permohonan maaf yang tulus dan sangat berempati. Berikan solusi langsung. JANGAN gunakan emoji berlebihan (cukup 🙏)."
        elif classification.intent in ["product_question", "general"] and analysis.buyer_mood in ["curious", "interested"]:
            mood_instruction = "Pembeli tertarik pada produk. Terapkan taktik *Upselling* atau FOMO (Fear Of Missing Out) secara halus, misalnya: 'Stok kita menipis Kak, yuk diamankan sekarang sebelum kehabisan!'. Gunakan emoji ceria."
        elif classification.intent == "order_status":
            mood_instruction = "Pembeli menanyakan status pesanan. Berikan jawaban yang menenangkan dan pastikan pesanan mereka aman di tangan kurir. Gunakan emoji paket 📦."
        else:
            mood_instruction = "Balas dengan ramah, profesional, dan gunakan emoji yang sesuai."

        product_block = ""
        if product_context:
            product_block = f"\n{product_context}\n"

        prompt = f"""\
Riwayat Percakapan (History):
{history_text}
{product_block}
Detail Analisis AI Internal:
- Intent Pembeli: {classification.intent}
- Suasana Hati Pembeli: {analysis.buyer_mood}
- Konteks Pesanan/Produk: {json.dumps(context or {}, default=str)}

Instruksi Khusus Situasi Ini:
{mood_instruction}

Berdasarkan data di atas, tuliskan balasan yang nyambung dengan history, padat, sangat manusiawi, dan profesional dalam Bahasa Indonesia.
PENTING: Jika ada DATA PRODUK RESMI di atas, HANYA gunakan data tersebut untuk menjawab pertanyaan produk. JANGAN mengarang informasi yang tidak ada.
"""
        response = self.model.generate_content(prompt)
        return response.text.strip()

    async def summarize_session(self, messages: list[dict[str, str]]) -> str:
        prompt = f"Summarize the following chat history in one or two sentences:\n{json.dumps(messages)}"
        response = self.model.generate_content(prompt)
        return response.text.strip()

    async def generate_response(self, prompt: str) -> str:
        """Freeform prompt for internal agent reasoning (not customer-facing)."""
        response = self.model.generate_content(prompt)
        return response.text.strip()
