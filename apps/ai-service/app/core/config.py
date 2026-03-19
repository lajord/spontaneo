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

    # Firecrawl API
    FIRECRAWL_API_KEY: str = ""

    # Perplexity API
    PERPLEXITY_API_KEY: str = ""
    PERPLEXITY_BASE_URL: str = "https://api.perplexity.ai"
    PERPLEXITY_MODEL: str = "sonar-pro"

    # Modeles IA — valeurs par defaut (overrides par AppConfig en DB)
    MODEL_ENRICHISSEMENT: str = "spark-1-mini"
    MODEL_ENRICHISSEMENT_2: str = "sonar-pro"
    MODEL_CREATION_MAIL: str = "gpt-5"
    MODEL_CREATION_LM: str = "gpt-5"
    MODEL_KEYWORDS: str = "gpt-5"
    MODEL_CV_READER: str = "Qwen2.5-VL-72B-Instruct"
    MODEL_RANKING: str = "gemini-2.5-flash"
    MODEL_FILTER: str = "sonar-pro"

    # NeverBounce (validation emails)
    NEVER_BOUNCE_API: str = ""

    # Apollo.io
    APOLLO_API_KEY: str = ""

    # Apify (Google Maps Scraper)
    APIFY_API_KEY: str = ""

    # Database (pour lire AppConfig)
    DATABASE_URL: str = ""

    # Nominatim (géocodage OpenStreetMap)
    NOMINATIM_USER_AGENT: str = "spontaneo/1.0"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
