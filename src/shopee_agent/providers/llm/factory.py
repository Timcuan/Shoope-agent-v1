from shopee_agent.config.settings import Settings
from shopee_agent.providers.llm.gateway import LLMGateway, ResilientLLM
from shopee_agent.providers.llm.gemini import GeminiProvider
from shopee_agent.providers.llm.openrouter import OpenRouterProvider

def create_llm_provider(settings: Settings) -> LLMGateway | None:
    """Factory to create a resilient LLM provider with fallback support."""
    
    primary = None
    fallback = None
    
    # 1. Initialize Primary
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        primary = GeminiProvider(api_key=settings.gemini_api_key, model_name=settings.llm_model)
    elif settings.llm_provider == "openrouter" and settings.openrouter_api_key:
        primary = OpenRouterProvider(api_key=settings.openrouter_api_key, model_name=settings.llm_model)
    
    # 2. Initialize Fallback (The other one)
    if settings.llm_provider == "gemini" and settings.openrouter_api_key:
        # If Gemini is primary, OpenRouter is fallback
        fallback = OpenRouterProvider(api_key=settings.openrouter_api_key, model_name="google/gemini-2.0-flash-exp:free")
    elif settings.llm_provider == "openrouter" and settings.gemini_api_key:
        # If OpenRouter is primary, Gemini is fallback
        fallback = GeminiProvider(api_key=settings.gemini_api_key, model_name="gemini-1.5-flash")
        
    if not primary:
        return None
        
    return ResilientLLM(primary=primary, fallback=fallback)
