"""
Serviço de renderização via Sentinel Hub Process API do CDSE.
"""

import io
import math
from datetime import datetime, timedelta

import httpx

from app.auth.cdse import cdse_auth
from app.cache import image_cache
from app.config import get_settings
from app.evalscripts import get_evalscript
from app.evalscripts.sentinel2 import CLOUD_MASK_SCL

CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

COLLECTION_MAP = {
    "sentinel2": "sentinel-2-l2a",
    "landsat": "landsat-ot-l1",
    "sentinel1": "sentinel-1-grd",
}

# Evalscript simples para hasData (RGB mínimo)
_OPTICAL_HAS_DATA = """//VERSION=3
function setup() { return { input: ["B04","B03","B02"], output: { bands: 3 } }; }
function evaluatePixel(s) { return [2.5*s.B04, 2.5*s.B03, 2.5*s.B02]; }
"""

_S1_HAS_DATA = """//VERSION=3
function setup() { return { input: ["VV"], output: { bands: 3 } }; }
function evaluatePixel(s) { var v=Math.sqrt(s.VV)*3; return [v,v,v]; }
"""


def compute_dimensions(bbox: list[float], resolution: str) -> tuple[int, int]:
    """Calcula (width, height) em pixels mantendo aspect ratio da bbox."""
    west, south, east, north = bbox
    
    print(f"📏 Calculando dimensões para bbox: {bbox}")
    print(f"📐 Resolução solicitada: {resolution}")
    
    lng_span = abs(east - west)
    lat_span = abs(north - south)
    
    print(f"📊 Largura (lng): {lng_span:.6f}°")
    print(f"📊 Altura (lat): {lat_span:.6f}°")

    if resolution == "native":
        lat_center = (south + north) / 2
        meters_per_deg_lat = 111_320
        meters_per_deg_lng = 111_320 * math.cos(math.radians(lat_center))
        width_m = lng_span * meters_per_deg_lng
        height_m = lat_span * meters_per_deg_lat
        pixel_size = 10  # 10 m/px para S2/Landsat/S1
        width = int(width_m / pixel_size)
        height = int(height_m / pixel_size)
        max_px = 2500
        if max(width, height) > max_px:
            scale = max_px / max(width, height)
            width = int(width * scale)
            height = int(height * scale)
        result = max(64, width), max(64, height)
        print(f"🖼️ Dimensões nativas: {result}")
        return result

    max_px = {"low": 512, "medium": 1024, "high": 2048}[resolution]

    if lng_span == 0 and lat_span == 0:
        result = max_px, max_px
        print(f"🖼️ Dimensões (ponto): {result}")
        return result

    if lng_span >= lat_span:
        width = max_px
        height = round(max_px * lat_span / lng_span) if lat_span > 0 else max_px
    else:
        height = max_px
        width = round(max_px * lng_span / lat_span) if lng_span > 0 else max_px

    width = max(64, min(max_px, width))
    height = max(64, min(max_px, height))
    
    result = width, height
    print(f"🖼️ Dimensões finais: {result}")
    return result


def _bounds_input(bbox: list[float]) -> dict:
    return {
        "bbox": bbox,
        "properties": {"crs": CRS84},
    }


def _png_output(width: int, height: int) -> dict:
    return {
        "width": width,
        "height": height,
        "responses": [
            {
                "identifier": "default", 
                "format": {
                    "type": "image/png",
                    "quality": 95
                }
            }
        ],
    }


async def render_optical(
    bbox: list[float],
    date: str,
    visual_type: str,
    resolution: str,
    max_cloud_cover: float,
    satellite_type: str,
) -> bytes:
    """Renderiza imagem óptica (S2 ou Landsat) via Process API."""
    settings = get_settings()

    if settings.image_cache_enabled:
        cache_key = image_cache.make_key(
            type="optical",
            satellite=satellite_type,
            visual=visual_type,
            resolution=resolution,
            date=date,
            bbox=",".join(str(round(x, 6)) for x in bbox),
        )
        cached = image_cache.get(cache_key)
        if cached is not None:
            return cached

    token = await cdse_auth.get_token(settings)

    date_obj = datetime.fromisoformat(date.replace("Z", ""))
    
    # Usar janela temporal maior (±3 dias) para garantir dados disponíveis
    from_dt = (date_obj - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z")
    to_dt = (date_obj + timedelta(days=3)).strftime("%Y-%m-%dT23:59:59Z")

    width, height = compute_dimensions(bbox, resolution)
    collection = COLLECTION_MAP[satellite_type]
    evalscript = get_evalscript(satellite_type, visual_type)

    print(f"🔧 Configurações de renderização:")
    print(f"   📐 Dimensões: {width}x{height}")
    print(f"   🗂️ Collection: {collection}")
    print(f"   ⏰ Janela temporal: {from_dt} → {to_dt}")
    print(f"   ☁️ Max cloud cover: {max_cloud_cover}%")
    print(f"   📊 Bbox: {bbox}")
    print(f"   📜 Evalscript preview: {evalscript[:200]}...")

    body = {
        "input": {
            "bounds": _bounds_input(bbox),
            "data": [
                {
                    "type": collection,
                    "dataFilter": {
                        "timeRange": {"from": from_dt, "to": to_dt},
                        "maxCloudCoverage": max_cloud_cover,  # Usar o percentual fornecido
                        "mosaickingOrder": "leastCC",  # Least Cloud Cover first
                    },
                    "processing": {
                        "upsampling": "BICUBIC", 
                        "downsampling": "BICUBIC",
                    },
                }
            ],
        },
        "output": _png_output(width, height),
        "evalscript": evalscript,
    }

    async with httpx.AsyncClient() as client:
        print(f"🌐 Fazendo requisição para Process API:")
        print(f"   📍 URL: {settings.process_url}")
        print(f"   📦 Body (dimensions): width={width}, height={height}")
        print(f"   🎨 Evalscript type: {visual_type}")
        print(f"   ⏰ Time range: {from_dt} → {to_dt}")
        print(f"   ☁️ Max cloud cover: {max_cloud_cover}%")
        
        resp = await client.post(
            settings.process_url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=90,
        )
        
        print(f"📡 Resposta da API:")
        print(f"   🔢 Status: {resp.status_code}")
        print(f"   📏 Tamanho: {len(resp.content)} bytes")
        print(f"   📋 Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        
        if len(resp.content) < 5000:  # Aumentei o limite para detectar imagens suspeitas
            print(f"⚠️ ALERTA: Imagem muito pequena!")
            print(f"   🔍 Primeiros 50 bytes: {resp.content[:50]}")
            print(f"   💭 Possível causa: Sem dados válidos na área/período")
        
        resp.raise_for_status()
        result = resp.content

    if settings.image_cache_enabled:
        image_cache.set(cache_key, result)

    return result


async def render_sentinel1(
    bbox: list[float],
    date: str,
    visual_type: str,
    resolution: str,
) -> bytes:
    """Renderiza imagem SAR Sentinel-1 via Process API."""
    settings = get_settings()

    if settings.image_cache_enabled:
        cache_key = image_cache.make_key(
            type="sentinel1",
            visual=visual_type,
            resolution=resolution,
            date=date,
            bbox=",".join(str(round(x, 6)) for x in bbox),
        )
        cached = image_cache.get(cache_key)
        if cached is not None:
            return cached

    token = await cdse_auth.get_token(settings)

    date_obj = datetime.fromisoformat(date.replace("Z", ""))
    from_dt = (date_obj - timedelta(days=6)).strftime("%Y-%m-%dT00:00:00Z")
    to_dt = (date_obj + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")

    width, height = compute_dimensions(bbox, resolution)
    evalscript = get_evalscript("sentinel1", visual_type)

    body = {
        "input": {
            "bounds": _bounds_input(bbox),
            "data": [
                {
                    "type": "sentinel-1-grd",
                    "dataFilter": {
                        "timeRange": {"from": from_dt, "to": to_dt},
                        "mosaickingOrder": "mostRecent",
                    },
                    "processing": {
                        "backCoeff": "GAMMA0_TERRAIN",
                        "orthorectify": True,
                        "demInstance": "COPERNICUS",
                    },
                }
            ],
        },
        "output": _png_output(width, height),
        "evalscript": evalscript,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.process_url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=90,
        )
        resp.raise_for_status()
        result = resp.content

    if settings.image_cache_enabled:
        image_cache.set(cache_key, result)

    return result


async def check_has_data(
    bbox: list[float],
    date: str,
    satellite_type: str,
) -> bool:
    """
    Verifica se há dados reais na bbox para a data.
    Usa um tile pequeno (64×64) e aplica heurística de tamanho de resposta.
    """
    settings = get_settings()

    try:
        token = await cdse_auth.get_token(settings)
    except Exception:
        return False

    date_obj = datetime.fromisoformat(date.replace("Z", ""))

    if satellite_type == "sentinel1":
        delta = timedelta(days=6)
        collection = "sentinel-1-grd"
        mosaicking = "mostRecent"
        processing: dict = {
            "backCoeff": "GAMMA0_TERRAIN",
            "orthorectify": True,
            "demInstance": "COPERNICUS",
        }
        evalscript = _S1_HAS_DATA
        data_filter: dict = {
            "timeRange": {
                "from": (date_obj - delta).strftime("%Y-%m-%dT00:00:00Z"),
                "to": (date_obj + delta).strftime("%Y-%m-%dT23:59:59Z"),
            },
            "mosaickingOrder": mosaicking,
        }
    else:
        delta = timedelta(days=15)
        collection = COLLECTION_MAP[satellite_type]
        mosaicking = "leastCC"
        processing = {"upsampling": "BICUBIC", "downsampling": "BICUBIC"}
        evalscript = _OPTICAL_HAS_DATA
        data_filter = {
            "timeRange": {
                "from": (date_obj - delta).strftime("%Y-%m-%dT00:00:00Z"),
                "to": (date_obj + delta).strftime("%Y-%m-%dT23:59:59Z"),
            },
            "maxCloudCoverage": 30,
            "mosaickingOrder": mosaicking,
        }

    body = {
        "input": {
            "bounds": _bounds_input(bbox),
            "data": [
                {
                    "type": collection,
                    "dataFilter": data_filter,
                    "processing": processing,
                }
            ],
        },
        "output": _png_output(64, 64),
        "evalscript": evalscript,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.process_url,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if resp.status_code != 200:
                return False
            return len(resp.content) > settings.has_data_threshold_bytes
    except Exception:
        return False


async def cloud_cover_in_bbox(
    bbox: list[float],
    date: str,
    scene_id: str,
) -> float:
    """
    Calcula a % de cobertura de nuvens (SCL bands 8 e 9) na bbox para Sentinel-2 L2A.

    Usa o evalscript CLOUD_MASK_SCL que retorna uma máscara binária:
    - 255 = pixel de nuvem (SCL 8 ou 9)
    - 0   = pixel sem nuvem

    Decodifica o PNG com Pillow e conta os pixels brancos.
    """
    from PIL import Image  # type: ignore[import-untyped]

    settings = get_settings()
    token = await cdse_auth.get_token(settings)

    date_obj = datetime.fromisoformat(date.replace("Z", ""))
    from_dt = (date_obj - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    to_dt = (date_obj + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")

    body = {
        "input": {
            "bounds": _bounds_input(bbox),
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": from_dt, "to": to_dt},
                        "maxCloudCoverage": 100,
                        "mosaickingOrder": "leastCC",
                    },
                    "processing": {"upsampling": "NEAREST", "downsampling": "NEAREST"},
                }
            ],
        },
        "output": {
            "width": 256,
            "height": 256,
            "responses": [
                {
                    "identifier": "default",
                    "format": {"type": "image/png"},
                }
            ],
        },
        "evalscript": CLOUD_MASK_SCL,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.process_url,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        resp.raise_for_status()

    img = Image.open(io.BytesIO(resp.content)).convert("L")
    pixels = list(img.getdata())
    total = len(pixels)
    cloud_pixels = sum(1 for p in pixels if p > 127)
    return round((cloud_pixels / total) * 100, 2) if total > 0 else 0.0
