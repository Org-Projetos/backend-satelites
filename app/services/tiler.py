"""
Tiler para fontes sem Process API — CBERS-4A MUX.

Fluxo:
  1. Busca a melhor cena no catálogo STAC (stac.scitekno.com.br).
  2. Lê apenas a janela da bbox nos COG via rio-tiler (sem baixar cena inteira).
  3. Aplica band math NumPy (truecolor / falsecolor / ndvi).
  4. Retorna PNG bytes.
"""

import io
from datetime import datetime, timedelta
from typing import Optional

import httpx
import numpy as np
from PIL import Image

from app.cache import image_cache
from app.config import get_settings
from app.services.process_api import compute_dimensions

# Mapeamento de visualType → assets CBERS-4A MUX
# B5=Azul, B6=Verde, B7=Vermelho, B8=NIR
CBERS4A_BANDS: dict[str, list[str]] = {
    "truecolor": ["B7", "B6", "B5"],   # R, G, B
    "falsecolor": ["B8", "B7", "B6"],  # NIR, R, G → exibido como R, G, B
    "ndvi": ["B8", "B7"],              # NIR, R
}

SUPPORTED_VISUAL_TYPES = set(CBERS4A_BANDS.keys())


async def _search_cbers4a(
    bbox: list[float],
    from_dt: str,
    to_dt: str,
) -> Optional[dict]:
    """
    Consulta o catálogo STAC do CBERS-4A e retorna a cena com menor cobertura de nuvens
    que cobre a bbox no intervalo de datas informado.

    Retorna None se nenhuma cena for encontrada.
    """
    settings = get_settings()
    body = {
        "collections": [settings.cbers4a_collection],
        "bbox": bbox,
        "datetime": f"{from_dt}/{to_dt}",
        "limit": 10,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.cbers4a_stac_url,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        return None

    # Escolhe cena com menor cobertura de nuvens
    return min(
        features,
        key=lambda f: f.get("properties", {}).get("eo:cloud_cover", 100),
    )


def _truecolor(data: np.ndarray) -> np.ndarray:
    """data: (3, h, w) int — R, G, B. Retorna (h, w, 3) uint8."""
    rgb = np.clip(data.astype(np.float32) / 10000.0 * 2.5, 0.0, 1.0)
    return (rgb * 255).astype(np.uint8).transpose(1, 2, 0)


def _falsecolor(data: np.ndarray) -> np.ndarray:
    """data: (3, h, w) int — NIR, R, G. Retorna (h, w, 3) uint8."""
    rgb = np.clip(data.astype(np.float32) / 10000.0 * 2.5, 0.0, 1.0)
    return (rgb * 255).astype(np.uint8).transpose(1, 2, 0)


def _colorize_ndvi(ndvi: np.ndarray) -> np.ndarray:
    """Coloriza NDVI (-1..1) com rampa marrom → amarelo → verde. Retorna (h, w, 3) uint8."""
    t = np.clip((ndvi + 0.2) / 1.2, 0.0, 1.0)  # normaliza -0.2..1.0 → 0..1
    r = ((1.0 - t) * 160.0).astype(np.uint8)
    g = (t * 180.0).astype(np.uint8)
    b = ((1.0 - t) * 60.0).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


def _ndvi(data: np.ndarray) -> np.ndarray:
    """data: (2, h, w) int — NIR, R. Retorna (h, w, 3) uint8 colorizado."""
    nir = data[0].astype(np.float32)
    red = data[1].astype(np.float32)
    ndvi_val = (nir - red) / (nir + red + 1e-8)
    return _colorize_ndvi(ndvi_val)


def _apply_band_math(visual_type: str, data: np.ndarray) -> np.ndarray:
    """Despacha para a função de band math correta. Retorna (h, w, 3) uint8."""
    if visual_type == "truecolor":
        return _truecolor(data)
    if visual_type == "falsecolor":
        return _falsecolor(data)
    if visual_type == "ndvi":
        return _ndvi(data)
    raise ValueError(f"visualType '{visual_type}' não suportado para CBERS-4A")


def _to_png(rgb: np.ndarray) -> bytes:
    """Converte array (h, w, 3) uint8 para bytes PNG."""
    img = Image.fromarray(rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def render_cbers4a(
    bbox: list[float],
    date: str,
    visual_type: str,
    resolution: str,
) -> bytes:
    """
    Renderiza CBERS-4A MUX para a bbox e data informadas.

    - Busca a cena STAC com menor cobertura de nuvens dentro da janela ±cbers4a_time_window_days.
    - Lê os bands COG com rio-tiler (STACReader).
    - Aplica band math NumPy.
    - Retorna PNG bytes.

    Levanta ValueError se nenhuma cena for encontrada ou se visual_type não for suportado.
    """
    if visual_type not in SUPPORTED_VISUAL_TYPES:
        raise ValueError(
            f"visualType '{visual_type}' não suportado para CBERS-4A. "
            f"Opções: {sorted(SUPPORTED_VISUAL_TYPES)}"
        )

    settings = get_settings()

    if settings.image_cache_enabled:
        cache_key = image_cache.make_key(
            type="cbers4a",
            visual=visual_type,
            resolution=resolution,
            date=date,
            bbox=",".join(str(round(x, 6)) for x in bbox),
        )
        cached = image_cache.get(cache_key)
        if cached is not None:
            return cached

    date_obj = datetime.fromisoformat(date.replace("Z", ""))
    delta = timedelta(days=settings.cbers4a_time_window_days)
    from_dt = (date_obj - delta).strftime("%Y-%m-%dT00:00:00Z")
    to_dt = (date_obj + delta).strftime("%Y-%m-%dT23:59:59Z")

    scene = await _search_cbers4a(bbox, from_dt, to_dt)
    if scene is None:
        raise ValueError(
            f"Nenhuma cena CBERS-4A MUX encontrada para bbox={bbox} "
            f"na janela {from_dt} / {to_dt}"
        )

    assets = CBERS4A_BANDS[visual_type]
    width, height = compute_dimensions(bbox, resolution)

    # Importação lazy para não falhar se rio-tiler não estiver instalado
    from rio_tiler.io import STACReader  # type: ignore[import-untyped]

    with STACReader(None, item=scene) as stac:
        img = stac.part(
            bbox,
            assets=assets,
            width=width,
            height=height,
        )
        data = img.as_masked().data  # shape: (bands, h, w)

    rgb = _apply_band_math(visual_type, data)
    result = _to_png(rgb)

    if settings.image_cache_enabled:
        image_cache.set(cache_key, result)

    return result
