"""
Dispatcher de evalscripts por (satelliteType, visualType).
"""

from app.evalscripts import landsat, sentinel1, sentinel2

_REGISTRY: dict[tuple[str, str], str] = {
    # Sentinel-2
    ("sentinel2", "truecolor"): sentinel2.TRUECOLOR,
    ("sentinel2", "falsecolor"): sentinel2.FALSECOLOR,
    ("sentinel2", "ndvi"): sentinel2.NDVI,
    ("sentinel2", "evi"): sentinel2.EVI,
    ("sentinel2", "swir"): sentinel2.SWIR,
    ("sentinel2", "ndmi"): sentinel2.NDMI,
    ("sentinel2", "ndwi"): sentinel2.NDWI,
    # Landsat
    ("landsat", "truecolor"): landsat.TRUECOLOR,
    ("landsat", "falsecolor"): landsat.FALSECOLOR,
    ("landsat", "ndvi"): landsat.NDVI,
    ("landsat", "evi"): landsat.EVI,
    ("landsat", "swir"): landsat.SWIR,
    ("landsat", "ndmi"): landsat.NDMI,
    ("landsat", "ndwi"): landsat.NDWI,
    # Sentinel-1
    ("sentinel1", "vv"): sentinel1.VV,
    ("sentinel1", "vh"): sentinel1.VH,
    ("sentinel1", "rgb"): sentinel1.RGB,
    ("sentinel1", "rvi"): sentinel1.RVI,
}


def get_evalscript(satellite_type: str, visual_type: str) -> str:
    key = (satellite_type, visual_type)
    script = _REGISTRY.get(key)
    if script is None:
        raise ValueError(
            f"Evalscript não encontrado para satellite_type={satellite_type!r}, "
            f"visual_type={visual_type!r}"
        )
    return script
