from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Credenciais CDSE
    cdse_client_id: str = "sh-5ec0af89-a3cf-4a8e-8061-13297f73eb84"  # TEMPORÁRIO - para testes
    cdse_client_secret: str = "vbJi7vwMuVifsH7sZaBLxCPzEzztB0dm"  # TEMPORÁRIO - para testes

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

    # OpenAI API (para análise via GPT-4o Vision)
    openai_api_key: str = "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"  # TEMPORÁRIO - para testes

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
    database_url: str = "postgresql://agro:agro_secret@localhost:5432/agro"

    # ── Autenticação JWT ──────────────────────────────────────────────────────
    secret_key: str = "change-this-secret-in-production"
    access_token_expire_minutes: int = 60

    # Usuário administrador padrão (pode ser sobrescrito pelo .env)
    admin_username: str = "admin"
    admin_password: str = "agro2024"

    # ── MinIO (Object Storage) ────────────────────────────────────────────────
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_secret"
    minio_bucket: str = "agro-images"


@lru_cache
def get_settings() -> Settings:
    return Settings()
