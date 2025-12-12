from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "PAT Permission System"
    app_version: str = "1.0.0"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
