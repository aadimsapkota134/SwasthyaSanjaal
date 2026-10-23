"""Runtime configuration for SwasthyaSanjaal backend.

Values are resolved from the environment and optional .env file.
Core Architecture Decision:
- Primary Cloud Model: gemma4:31b-cloud via Ollama Cloud API
- Offline Edge Fallback: gemma4:e2b-it-qat via local Ollama
- Input modalities: Vision OCR (prescriptions & reports), Digital PDFs, Speech/ASR transcripts, and Text.
"""

from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for SwasthyaSanjaal."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    port: int = 8000
    model_backend: str = "cloud"  # "cloud", "local", or "auto"

    # Primary Cloud Model: gemma4:31b-cloud (Ollama)
    ollama_cloud_url: str = "https://ollama.com"
    model_name: str = "gemma4:31b-cloud"
    gemma_cloud_model: str = "gemma4:31b-cloud"
    ollama_api_key: str = ""

    # Local Ollama URL (offline edge fallback model for rural clinics & FCHVs)
    ollama_url: str = "http://localhost:11434"
    local_gemma_model: str = "gemma4:e2b-it-qat"

    # Database & Data asset paths
    db_path: str = "./data/swasthyasanjaal.db"
    lexicon_path: str = "./data/nepali_clinical_lexicon.json"
    benchmark_path: str = "./data/nepclinbench.json"
    upload_dir: str = "./uploads"

    # Confidence threshold below which human confirmation is required
    uncertainty_threshold: float = 0.85

    # Security / session settings
    session_secret_key: str = ""
    session_cookie_name: str = "swasthya_session"
    session_cookie_domain: str | None = None
    session_cookie_path: str = "/"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_ttl_seconds: int = 3600
    bcrypt_cost: int = 12
    max_failed_login_attempts: int = 5
    failed_login_lockout_seconds: int = 900

    # Allowed CORS Origins
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """True when running with secure cookies (HTTPS) enabled."""
        return self.session_cookie_secure

    @property
    def resolved_backend(self) -> str:
        """Determines active model backend based on key presence and explicit setting."""
        choice = self.model_backend.strip().lower()
        if choice in {"cloud", "local"}:
            return choice
        return "cloud" if self.ollama_api_key.strip() else "local"

    @property
    def model_base_url(self) -> str:
        if self.resolved_backend == "cloud":
            return self.ollama_cloud_url.rstrip("/")
        return self.ollama_url.rstrip("/")

    @property
    def active_model_name(self) -> str:
        return self.model_name or self.gemma_cloud_model

    @property
    def fallback_model_name(self) -> str:
        return self.local_gemma_model or "gemma4:e2b-it-qat"

    @property
    def model_headers(self) -> dict[str, str]:
        key = self.ollama_api_key.strip()
        if self.resolved_backend == "cloud" and key:
            return {"Authorization": f"Bearer {key}"}
        return {}

    def validate_security(self) -> list[str]:
        """Validate security-critical settings.

        Returns a list of error messages. Empty list means all checks pass.
        """
        errors: list[str] = []
        if self.is_production and not self.session_secret_key:
            errors.append(
                "SESSION_SECRET_KEY must be set when running with secure cookies "
                "(production). Generate one with: python -c 'import secrets; "
                "print(secrets.token_urlsafe(32))'"
            )
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
