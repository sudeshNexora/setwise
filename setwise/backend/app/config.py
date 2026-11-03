from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./setwise.db"  # overridden by .env (MySQL)
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    upload_dir: str = "./storage/uploads"
    export_dir: str = "./storage/exports"

    # --- AI question generation (Google Gemini) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    ai_max_attempts: int = 3
    ai_max_source_chars: int = 24000   # how much study material goes into one prompt


settings = Settings()
