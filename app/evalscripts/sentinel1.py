"""Evalscripts JavaScript para Sentinel-1 GRD (coleção: sentinel-1-grd)."""

VV = """//VERSION=3
function setup() {
  return { input: ["VV"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  var v = Math.sqrt(s.VV) * 3;
  return [v, v, v];
}
"""

VH = """//VERSION=3
function setup() {
  return { input: ["VH"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  var v = Math.sqrt(s.VH) * 6;
  return [v, v, v];
}
"""

RGB = """//VERSION=3
function setup() {
  return { input: ["VV", "VH"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  return [
    Math.sqrt(s.VV) * 3,
    Math.sqrt(s.VH) * 6,
    Math.sqrt(s.VV / (s.VH + 1e-9)) * 1.5
  ];
}
"""

RVI = """//VERSION=3
function setup() {
  return { input: ["VV", "VH"], output: { bands: 3 } };
}
function evaluatePixel(s) {
  var rvi = 4 * s.VH / (s.VV + s.VH + 1e-9);
  return rviColor(rvi);
}
function rviColor(v) {
  if (v < 0.10) return [0.83, 0.67, 0.42];
  if (v < 0.20) return [0.91, 0.84, 0.52];
  if (v < 0.30) return [0.79, 0.88, 0.37];
  if (v < 0.40) return [0.47, 0.78, 0.18];
  if (v < 0.50) return [0.23, 0.62, 0.09];
  return [0.05, 0.43, 0.04];
}
"""
