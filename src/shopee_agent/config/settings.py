from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./data/shopee_agent.db"
    archive_dir: str = "./data/archive"
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    shopee_partner_id: str = ""
    shopee_partner_key: str = ""
    shopee_base_url: str = "https://partner.shopeemobile.com"
    llm_provider: str = "disabled"
