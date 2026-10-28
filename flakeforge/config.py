import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    nebius_api_key: str = os.getenv("NEBIUS_API_KEY", "")
    nebius_base_url: str = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
    nebius_model: str = os.getenv("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    provider: str = os.getenv("FLAKEFORGE_PROVIDER", "nebius")
    host: str = os.getenv("FLAKEFORGE_HOST", "0.0.0.0")
    port: int = int(os.getenv("FLAKEFORGE_PORT", "8000"))
    debug: bool = os.getenv("FLAKEFORGE_DEBUG", "False").lower() in ("true", "1")
    max_search_seeds: int = 50
    stress_seed_count: int = 1000
    timeout_seconds: float = 4.0

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
