import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Primary NVIDIA NIM settings
    nvidia_api_key: str = (
        os.getenv("NVIDIA_API_KEY")
        or os.getenv("NIM_API_KEY")
        or os.getenv("NEBIUS_API_KEY", "")
    )
    nvidia_base_url: str = (
        os.getenv("NVIDIA_BASE_URL")
        or os.getenv("NIM_BASE_URL")
        or "https://integrate.api.nvidia.com/v1"
    )
    nvidia_model: str = (
        os.getenv("NVIDIA_MODEL")
        or os.getenv("NIM_MODEL")
        or "nvidia/llama-3.1-nemotron-70b-instruct"
    )
    provider: str = os.getenv("FLAKEFORGE_PROVIDER", "nvidia_nim")
    host: str = os.getenv("FLAKEFORGE_HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", os.getenv("FLAKEFORGE_PORT", "8000")))
    debug: bool = os.getenv("FLAKEFORGE_DEBUG", "False").lower() in ("true", "1")
    max_search_seeds: int = 50
    stress_seed_count: int = 1000
    timeout_seconds: float = 4.0

    # Backward compatibility aliases
    @property
    def nebius_api_key(self) -> str:
        return self.nvidia_api_key

    @property
    def nebius_base_url(self) -> str:
        return self.nvidia_base_url

    @property
    def nebius_model(self) -> str:
        return self.nvidia_model

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()