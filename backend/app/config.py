"""Application settings, read from environment variables (or a local .env file)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- AI services ---------------------------------------------------------
    gemini_api_key: str = ""
    # Tried in order; the next model is used when one is overloaded or rate-limited.
    # 3.5 Flash localises building parts far more accurately than 2.5 Flash (tested on sample houses).
    gemini_models: str = "gemini-3.5-flash,gemini-2.5-flash,gemini-flash-latest"
    gemini_timeout_s: float = 90.0

    enable_sam: bool = True
    sam_model_id: str = "facebook/sam2.1-hiera-tiny"
    sam_threads: int = 2

    # Per-surface distances for measurement (Apache-2.0; the Base/Large variants are non-commercial).
    enable_depth: bool = True
    depth_model_id: str = "depth-anything/Depth-Anything-V2-Metric-Outdoor-Small-hf"

    # --- Storage & web ---------------------------------------------------------
    database_url: str = "sqlite:///./data/facade.db"
    cors_origins: str = "http://localhost:3000"
    # Optional regex, e.g. r"https://.*\.vercel\.app" to allow Vercel preview deployments.
    cors_origin_regex: str | None = None

    # --- Limits ----------------------------------------------------------------
    max_upload_mb: int = 12
    max_image_side: int = 1600
    analyze_limit_per_hour: int = 20  # per workspace
    analyze_ip_limit_per_hour: int = 40  # per IP, so new workspace ids cannot bypass it
    # Proxies in front of the app that append to X-Forwarded-For (1 on Modal). 0 = use the socket address
    # (uvicorn --proxy-headers already resolves it, as in the Docker image).
    trusted_proxy_hops: int = 0

    @property
    def gemini_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
