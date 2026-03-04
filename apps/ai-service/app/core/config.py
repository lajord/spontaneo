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

    # OVH AI Endpoints
    OVH_AI_ENDPOINTS_ACCESS_TOKEN: str = ""
    OVH_AI_BASE_URL: str = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
    OVH_AI_MODEL: str = "Qwen2.5-VL-72B-Instruct"

    # Google Places API
    GOOGLE_PLACE_API: str = ""

    # OpenAI API
    CHATGPT_API: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Google Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"

    # Perplexity API
    PERPLEXITY_API_KEY: str = ""
    PERPLEXITY_BASE_URL: str = "https://api.perplexity.ai"
    PERPLEXITY_MODEL: str = "sonar-pro"

    # Nominatim (géocodage OpenStreetMap)
    NOMINATIM_USER_AGENT: str = "spontaneo/1.0"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
