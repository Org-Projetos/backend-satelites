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

    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
