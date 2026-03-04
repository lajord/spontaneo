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

    # Google Places API
    GOOGLE_PLACE_API: str = ""

    # OpenAI API
    CHATGPT_API: str = ""

    # Google Gemini API
    GEMINI_API_KEY: str = ""

    # Perplexity API
    PERPLEXITY_API_KEY: str = ""
    PERPLEXITY_BASE_URL: str = "https://api.perplexity.ai"
    PERPLEXITY_MODEL: str = "sonar-pro"

    # Modèles IA par service
    MODEL_ENRICHISSEMENT: str = "gpt-5"
    MODEL_CREATION_MAIL: str = "gemini-3-flash-preview"
    MODEL_CREATION_LM: str = "gemini-3-flash-preview"
    MODEL_KEYWORDS: str = "gpt-4o-mini"
    MODEL_CV_READER: str = "Qwen2.5-VL-72B-Instruct"

    # Nominatim (géocodage OpenStreetMap)
    NOMINATIM_USER_AGENT: str = "spontaneo/1.0"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
