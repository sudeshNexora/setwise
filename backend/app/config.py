from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./setwise.db"  # overridden by .env
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    upload_dir: str = "./storage/uploads"
    export_dir: str = "./storage/exports"

    class Config:
        env_file = ".env"


settings = Settings()
