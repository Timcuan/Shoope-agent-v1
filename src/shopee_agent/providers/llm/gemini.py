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

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro") -> None:
        settings = get_settings()
        if settings.http_proxy_url:
            os.environ["HTTP_PROXY"] = settings.http_proxy_url
            os.environ["HTTPS_PROXY"] = settings.http_proxy_url
            
        genai.configure(api_key=api_key)
        
        # High-End Executive Personality Instruction
        system_instruction = (
            "Anda adalah 'Shopee Intelligence Elite Agent'—perpaduan antara Customer Service Senior, "
            "Pakar Logistik, dan Sales Manager papan atas. Anda cerdas, taktis, sangat manusiawi, "
            "namun tetap patuh pada aturan platform Shopee.\n\n"
            "KEPRIBADIAN:\n"
            "- Profesional, solutif, dan penuh empati (Terutama untuk komplain).\n"
            "- Persuasif namun tidak memaksa (Untuk closing penjualan).\n"
            "- Berbasis Data: Jangan mengarang informasi produk/resi jika tidak ada di konteks.\n\n"
            "GAYA BAHASA:\n"
            "- Selalu sapa 'Kak' di awal.\n"
            "- Gunakan Bahasa Indonesia yang natural (Semi-formal), bukan bahasa kaku robot.\n"
            "- Gunakan emoji secara strategis (1-2 per pesan), jangan berlebihan.\n"
            "- JANGAN PERNAH menyebutkan identitas AI/Bot."
        )
        
        self.config = {
            "temperature": 0.35, # Lower for consistency
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
        }
        
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction,
            generation_config=self.config
        )

    async def analyze_message(
        self, text: str, context: dict[str, Any] | None = None
    ) -> ChatAnalysis:
        prompt = f"""
        [DEEP ANALYSIS MODE - EXECUTIVE LEVEL]
        Analyze this Shopee customer message with high precision.
        Message: "{text}"
        Context: {json.dumps(context or {}, default=str)}

        Your task is to extract the core intent and emotional state for business decision making.
        
        Respond ONLY with a valid JSON object:
        {{
            "sentiment_score": float (-1.0 to 1.0),
            "urgency_score": float (0.0 to 1.0),
            "suggested_intent": "order_status" | "product_question" | "complaint" | "cancellation" | "refund" | "general",
            "buyer_mood": "angry" | "neutral" | "happy" | "confused" | "interested",
            "reasoning": "Brief explanation of your classification"
        }}
        """
        try:
            # Use specific generation config for classification (zero temp)
            response = self.model.generate_content(prompt, generation_config={"temperature": 0})
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
            history_text = "\n".join([f"{'Buyer' if m.is_buyer else 'Agent'}: {m.content}" for m in history[-5:]])

        # Advanced Strategy Selection
        strategy = "GENERAL_POLITE"
        if analysis.sentiment_score < -0.6 or classification.intent in ["complaint", "refund"]:
            strategy = "CRISIS_MANAGEMENT_EMPATHY"
        elif classification.intent == "product_question" and analysis.urgency_score > 0.4:
            strategy = "SALES_CONVERSION_URGENCY"
        
        prompt = f"""\
[STRATEGY: {strategy}]
History:
{history_text}

Product Knowledge:
{product_context or "No specific product info provided."}

Context Data (Order/User):
{json.dumps(context or {}, default=str)}

Buyer Intent: {classification.intent}
Buyer Mood: {analysis.buyer_mood}

TASK: Draft a high-conversion, empathetic response. 
- If complaint: Acknowledge, apologize, and state clear next steps.
- If product query: Answer using facts AND invite them to checkout.
- If order status: Provide shipping info precisely.

Draft the response now:
"""
        response = self.model.generate_content(prompt)
        return response.text.strip()

    async def summarize_session(self, messages: list[dict[str, str]]) -> str:
        prompt = f"Summarize this Shopee business interaction for an internal audit report:\n{json.dumps(messages)}"
        response = self.model.generate_content(prompt)
        return response.text.strip()

    async def generate_response(self, prompt: str) -> str:
        """Freeform reasoning for internal agents."""
        response = self.model.generate_content(prompt)
        return response.text.strip()
