from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from shopee_agent.contracts.knowledge import ChatAnalysis, ChatClassification, ChatMessage


class LLMGateway(ABC):
    """Abstract interface for Large Language Model providers."""

    @abstractmethod
    async def analyze_message(
        self, text: str, context: dict[str, Any] | None = None
    ) -> ChatAnalysis:
        pass

    @abstractmethod
    async def draft_response(
        self,
        classification: ChatClassification,
        analysis: ChatAnalysis,
        context: dict[str, Any] | None = None,
        history: list[ChatMessage] | None = None,
        product_context: str | None = None,
    ) -> str:
        pass

    @abstractmethod
    async def summarize_session(self, messages: list[dict[str, str]]) -> str:
        pass

    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        pass

import asyncio
import logging
import random

logger = logging.getLogger("shopee_agent.llm.resilience")

class ResilientLLM(LLMGateway):
    """A resilient wrapper that provides retries and fallbacks for LLM operations."""

    def __init__(self, primary: LLMGateway, fallback: LLMGateway | None = None, max_retries: int = 3):
        self.primary = primary
        self.fallback = fallback
        self.max_retries = max_retries

    async def _execute_with_retry(self, method_name: str, *args, **kwargs):
        last_error = None
        for attempt in range(self.max_retries):
            try:
                method = getattr(self.primary, method_name)
                return await method(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM Primary Attempt {attempt+1} failed: {e}. Retrying...")
                await asyncio.sleep(random.uniform(1.0, 3.0) * (attempt + 1))
        
        if self.fallback:
            logger.error(f"LLM Primary failed all retries. Switching to Fallback. Error: {last_error}")
            try:
                method = getattr(self.fallback, method_name)
                return await method(*args, **kwargs)
            except Exception as e:
                logger.error(f"LLM Fallback also failed: {e}")
                raise e
        
        raise last_error

    async def analyze_message(self, text: str, context: dict[str, Any] | None = None) -> ChatAnalysis:
        return await self._execute_with_retry("analyze_message", text, context)

    async def draft_response(self, *args, **kwargs) -> str:
        return await self._execute_with_retry("draft_response", *args, **kwargs)

    async def summarize_session(self, messages: list[dict[str, str]]) -> str:
        return await self._execute_with_retry("summarize_session", messages)

    async def generate_response(self, prompt: str) -> str:
        return await self._execute_with_retry("generate_response", prompt)
