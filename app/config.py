from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Credenciais CDSE
    cdse_client_id: str = Field(..., min_length=1)
    cdse_client_secret: str = Field(..., min_length=1)

    # URLs CDSE
    token_url: str = (
        "https://identity.dataspace.copernicus.eu"
        "/auth/realms/CDSE/protocol/openid-connect/token"
    )
    stac_url: str = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
    process_url: str = "https://sh.dataspace.copernicus.eu/api/v1/process"

    # Cache de token
    token_renewal_margin_seconds: int = 120

    # Heurística hasData
    has_data_threshold_bytes: int = 1500

    # Anthropic Claude API (para análise multimodal)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_api_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_version: str = "2023-06-01"

    # CORS
    cors_origins: list[str] = ["*"]

    # Domínios permitidos para thumbnail (SSRF protection)
    allowed_thumbnail_domains: list[str] = ["dataspace.copernicus.eu"]

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_default: str = "60/minute"

    # Cache de imagens em memória
    image_cache_enabled: bool = True
    image_cache_ttl_seconds: int = 86400  # 24 horas
    image_cache_max_size: int = 200       # máximo de entradas

    # Tiler CBERS-4A
    cbers4a_stac_url: str = "https://stac.scitekno.com.br/v100/search"
    cbers4a_collection: str = "CBERS4A_MUX_L4_DN"
    cbers4a_time_window_days: int = 15

    debug: bool = False

    # ── Banco de dados ────────────────────────────────────────────────────────
    database_url: str = Field(..., min_length=1)

    # ── Autenticação JWT ──────────────────────────────────────────────────────
    secret_key: str = Field(..., min_length=1)
    access_token_expire_minutes: int = 60

    # Usuário administrador padrão
    admin_username: str = "admin"
    admin_password: str = Field(..., min_length=1)

    # ── MinIO (Object Storage) ────────────────────────────────────────────────
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = Field(..., min_length=1)
    minio_secret_key: str = Field(..., min_length=1)
    minio_bucket: str = "agro-images"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_aliases(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
