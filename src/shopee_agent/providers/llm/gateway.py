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
        """Analyze message sentiment, urgency, and intent."""
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
        """Draft a natural language response based on classification and context."""
        pass

    @abstractmethod
    async def summarize_session(self, messages: list[dict[str, str]]) -> str:
        """Generate a concise summary of a chat history."""
        pass

    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        """Generate a freeform text response for a given prompt."""
        pass
