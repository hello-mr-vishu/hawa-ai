from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_api_key: str = ""
    google_genai_use_vertexai: int = 0
    llm_model: str = "gemini-2.5-flash-lite"
    max_tokens_per_session: int = 50000
    overpass_timeout: int = 25
    geocode_radius_default: int = 3000
    app_version: str = "1.0.0"
    session_db_path: str = "travel_agent/.adk/session.db"
    geocode_cache_ttl: float = 86400.0
    overpass_cache_ttl: float = 3600.0
    overpass_max_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
