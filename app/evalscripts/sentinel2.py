"""Evalscripts JavaScript para Sentinel-2 L2A (coleção: sentinel-2-l2a)."""

TRUECOLOR = """//VERSION=3
function setup() {
  return { input: ["B04", "B03", "B02"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  return [2.5 * s.B04, 2.5 * s.B03, 2.5 * s.B02];
}
"""

FALSECOLOR = """//VERSION=3
function setup() {
  return { input: ["B08", "B04", "B03"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  return [2.5 * s.B08, 2.5 * s.B04, 2.5 * s.B03];
}
"""

NDVI = """//VERSION=3
function setup() {
  return { input: ["B04", "B08"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  var ndvi = index(s.B08, s.B04);
  return ndviColor(ndvi);
}
function ndviColor(v) {
  if (v < -0.5) return [0.05, 0.05, 0.05];
  if (v < 0.00) return [0.75, 0.75, 0.75];
  if (v < 0.10) return [1.00, 0.98, 0.72];
  if (v < 0.20) return [0.86, 0.94, 0.44];
  if (v < 0.30) return [0.57, 0.84, 0.30];
  if (v < 0.40) return [0.32, 0.70, 0.22];
  if (v < 0.50) return [0.13, 0.54, 0.14];
  return [0.01, 0.36, 0.07];
}
"""

EVI = """//VERSION=3
function setup() {
  return { input: ["B02", "B04", "B08"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  var evi = 2.5 * (s.B08 - s.B04) / (s.B08 + 6 * s.B04 - 7.5 * s.B02 + 1);
  return ndviColor(evi);
}
function ndviColor(v) {
  if (v < -0.5) return [0.05, 0.05, 0.05];
  if (v < 0.00) return [0.75, 0.75, 0.75];
  if (v < 0.10) return [1.00, 0.98, 0.72];
  if (v < 0.20) return [0.86, 0.94, 0.44];
  if (v < 0.30) return [0.57, 0.84, 0.30];
  if (v < 0.40) return [0.32, 0.70, 0.22];
  if (v < 0.50) return [0.13, 0.54, 0.14];
  return [0.01, 0.36, 0.07];
}
"""

SWIR = """//VERSION=3
function setup() {
  return { input: ["B11", "B08", "B03"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  return [2.5 * s.B11, 2.5 * s.B08, 2.5 * s.B03];
}
"""

NDMI = """//VERSION=3
function setup() {
  return { input: ["B08", "B11"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  var ndmi = index(s.B08, s.B11);
  return moistureColor(ndmi);
}
function moistureColor(v) {
  if (v < -0.8) return [0.50, 0.30, 0.10];
  if (v < -0.6) return [0.74, 0.62, 0.38];
  if (v < -0.4) return [0.88, 0.77, 0.51];
  if (v < -0.2) return [0.96, 0.93, 0.69];
  if (v < 0.00) return [1.00, 1.00, 0.88];
  if (v < 0.20) return [0.75, 0.91, 0.89];
  if (v < 0.40) return [0.44, 0.76, 0.82];
  if (v < 0.60) return [0.17, 0.55, 0.74];
  return [0.02, 0.30, 0.62];
}
"""

NDWI = """//VERSION=3
function setup() {
  return { input: ["B03", "B08"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  var ndwi = index(s.B03, s.B08);
  return waterColor(ndwi);
}
function waterColor(v) {
  if (v < -0.4) return [0.94, 0.87, 0.70];
  if (v < -0.2) return [0.76, 0.84, 0.64];
  if (v < 0.00) return [0.50, 0.74, 0.58];
  if (v < 0.20) return [0.30, 0.64, 0.84];
  if (v < 0.40) return [0.15, 0.46, 0.93];
  return [0.04, 0.24, 0.82];
}
"""

# Evalscript para cálculo de cloud cover local (SCL band → máscara binária)
# Retorna 1 canal UINT8: 255 = nuvem (SCL 8 ou 9), 0 = não-nuvem
CLOUD_MASK_SCL = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["SCL"], units: "DN" }],
    output: { bands: 1, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  var isCloud = (s.SCL === 8 || s.SCL === 9) ? 255 : 0;
  return [isCloud];
}
"""
