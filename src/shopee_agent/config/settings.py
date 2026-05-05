from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./data/shopee_agent.db"
    archive_dir: str = "./data/archive"
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    admin_chat_id: str = ""
    shopee_partner_id: str = ""
    shopee_partner_key: str = ""
    shopee_base_url: str = "https://partner.shopeemobile.com"
    llm_provider: str = "gemini" # gemini, openrouter
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    api_secret_key: str = ""
    http_proxy_url: str = ""
    printnode_api_key: str = ""
    printnode_printer_id: str = ""
    google_service_account: str = ""
    google_admin_email: str = ""

from functools import lru_cache

@lru_cache()
def get_settings() -> Settings:
    return Settings()
