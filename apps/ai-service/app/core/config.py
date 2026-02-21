from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration de l'application AI Service."""

    # API
    API_V1_PREFIX: str = "/api/v1"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Supabase (accès direct si besoin)
    DATABASE_URL: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
