from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from shopee_agent.contracts.knowledge import ChatAnalysis, ChatClassification, ChatMessage
from shopee_agent.providers.llm.gateway import LLMGateway

logger = logging.getLogger("shopee_agent.llm.openrouter")

class OpenRouterProvider(LLMGateway):
    """OpenRouter implementation of LLMGateway (OpenAI-compatible)."""

    def __init__(self, api_key: str, model_name: str = "google/gemini-2.0-flash-exp:free") -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/Timcuan/Shoope-agent-v1",
            "X-Title": "Shopee Intelligence Engine",
            "Content-Type": "application/json"
        }

    async def _request(self, messages: list[dict], temperature: float = 0.5) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
            }
            response = await client.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def analyze_message(self, text: str, context: dict[str, Any] | None = None) -> ChatAnalysis:
        system_prompt = (
            "Analyze the following Shopee customer message. "
            "Respond ONLY with a JSON object containing: "
            "sentiment_score (-1.0 to 1.0), urgency_score (0.0 to 1.0), "
            "suggested_intent (order_status, product_question, complaint, cancellation, refund, general), "
            "buyer_mood, and reasoning."
        )
        user_prompt = f"Message: \"{text}\"\nContext: {json.dumps(context or {}, default=str)}"
        
        try:
            res_text = await self._request([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ], temperature=0.1)
            
            # Extract JSON
            import re
            match = re.search(r"\{.*\}", res_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return ChatAnalysis(
                    sentiment_score=data.get("sentiment_score", 0.0),
                    urgency_score=data.get("urgency_score", 0.0),
                    suggested_intent=data.get("suggested_intent"),
                    buyer_mood=data.get("buyer_mood"),
                    reasoning=data.get("reasoning"),
                )
        except Exception as e:
            logger.error(f"OpenRouter analysis error: {e}")
            return ChatAnalysis(sentiment_score=0.0, urgency_score=0.0)
        return ChatAnalysis(sentiment_score=0.0, urgency_score=0.0)

    async def draft_response(
        self,
        classification: ChatClassification,
        analysis: ChatAnalysis,
        context: dict[str, Any] | None = None,
        history: list[ChatMessage] | None = None,
        product_context: str | None = None,
    ) -> str:
        system_prompt = (
            "Anda adalah Shopee Intelligence Elite Agent. Ramah, profesional, dan solutif. "
            "HANYA gunakan Bahasa Indonesia natural (Kakak). "
            "Gunakan data resmi produk jika ada. Jangan mengarang informasi."
        )
        
        history_text = ""
        if history:
            history_text = "\n".join([f"{'Buyer' if m.is_buyer else 'Agent'}: {m.content}" for m in history[-5:]])

        user_prompt = f"""
History: {history_text}
Product Data: {product_context or 'None'}
Context: {json.dumps(context or {}, default=str)}
Intent: {classification.intent}
Mood: {analysis.buyer_mood}

Draft a human-like response:
"""
        return await self._request([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], temperature=0.7)

    async def summarize_session(self, messages: list[dict[str, str]]) -> str:
        prompt = f"Summarize this interaction briefly: {json.dumps(messages)}"
        return await self._request([{"role": "user", "content": prompt}])

    async def generate_response(self, prompt: str) -> str:
        return await self._request([{"role": "user", "content": prompt}])

    async def analyze_media(self, file_path: str, prompt: str) -> str:
        """Analyze an image using OpenRouter vision-enabled models."""
        import base64
        with open(file_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}
                    }
                ]
            }
        ]
        return await self._request(messages)
