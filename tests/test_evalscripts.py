"""Testes para o dispatcher de evalscripts."""

import pytest

from app.evalscripts import get_evalscript


# ─── Sentinel-2 ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "visual_type,expected_bands",
    [
        ("truecolor", ["B04", "B03", "B02"]),
        ("falsecolor", ["B08", "B04", "B03"]),
        ("ndvi", ["B04", "B08"]),
        ("evi", ["B02", "B04", "B08"]),
        ("swir", ["B11", "B08", "B03"]),
        ("ndmi", ["B08", "B11"]),
        ("ndwi", ["B03", "B08"]),
    ],
)
def test_s2_evalscripts_contain_bands(visual_type, expected_bands):
    """Evalscripts S2 devem referenciar as bandas corretas."""
    script = get_evalscript("sentinel2", visual_type)
    for band in expected_bands:
        assert f'"{band}"' in script or f"s.{band}" in script, (
            f"Banda {band} não encontrada no evalscript {visual_type}"
        )


# ─── Landsat ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "visual_type,expected_bands",
    [
        ("truecolor", ["B04", "B03", "B02"]),
        ("falsecolor", ["B05", "B04", "B03"]),
        ("ndvi", ["B04", "B05"]),
        ("evi", ["B02", "B04", "B05"]),
        ("swir", ["B07", "B05", "B03"]),
        ("ndmi", ["B05", "B06"]),
        ("ndwi", ["B03", "B05"]),
    ],
)
def test_landsat_evalscripts_contain_bands(visual_type, expected_bands):
    """Evalscripts Landsat devem referenciar as bandas corretas."""
    script = get_evalscript("landsat", visual_type)
    for band in expected_bands:
        assert f'"{band}"' in script or f"s.{band}" in script, (
            f"Banda {band} não encontrada no evalscript Landsat {visual_type}"
        )


# ─── Sentinel-1 ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "visual_type,expected_keywords",
    [
        ("vv", ["VV"]),
        ("vh", ["VH"]),
        ("rgb", ["VV", "VH"]),
        ("rvi", ["VV", "VH"]),
    ],
)
def test_s1_evalscripts_contain_bands(visual_type, expected_keywords):
    """Evalscripts S1 devem referenciar as polarizações corretas."""
    script = get_evalscript("sentinel1", visual_type)
    for kw in expected_keywords:
        assert kw in script, f"Banda {kw} não encontrada no evalscript S1 {visual_type}"


# ─── Validade geral ───────────────────────────────────────────────────────────


def test_all_evalscripts_have_version_3():
    """Todos os evalscripts devem iniciar com //VERSION=3."""
    combos = [
        ("sentinel2", vt)
        for vt in ["truecolor", "falsecolor", "ndvi", "evi", "swir", "ndmi", "ndwi"]
    ] + [
        ("landsat", vt)
        for vt in ["truecolor", "falsecolor", "ndvi", "evi", "swir", "ndmi", "ndwi"]
    ] + [
        ("sentinel1", vt) for vt in ["vv", "vh", "rgb", "rvi"]
    ]

    for sat, vt in combos:
        script = get_evalscript(sat, vt)
        assert "//VERSION=3" in script, f"Faltando //VERSION=3 em ({sat}, {vt})"


def test_all_evalscripts_have_setup_and_evaluate():
    """Todos os evalscripts devem ter as funções setup() e evaluatePixel()."""
    combos = [
        ("sentinel2", "truecolor"),
        ("landsat", "ndvi"),
        ("sentinel1", "rgb"),
    ]
    for sat, vt in combos:
        script = get_evalscript(sat, vt)
        assert "function setup()" in script
        assert "function evaluatePixel" in script


def test_invalid_satellite_type_raises():
    """Deve lançar ValueError para satellite_type inválido."""
    with pytest.raises(ValueError, match="Evalscript não encontrado"):
        get_evalscript("cbers4a", "truecolor")


def test_invalid_visual_type_raises():
    """Deve lançar ValueError para visual_type inválido."""
    with pytest.raises(ValueError, match="Evalscript não encontrado"):
        get_evalscript("sentinel2", "thermal")
