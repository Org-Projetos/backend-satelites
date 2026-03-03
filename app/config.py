from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Credenciais CDSE
    cdse_client_id: str = ""
    cdse_client_secret: str = ""

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
