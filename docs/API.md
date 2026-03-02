# API Reference — Agro Satélite Backend

Base URL: `http://localhost:8000` (ou o domínio do seu deploy)

Todas as rotas que recebem `bbox` usam o formato **WGS84 `[west, south, east, north]`**.
Datas em **ISO 8601** (`YYYY-MM-DD` ou `YYYY-MM-DDTHH:MM:SSZ`).

---

## Índice

1. [Health Check](#1-health-check)
2. [Busca de Cenas — por tipo](#2-busca-de-cenas--por-tipo)
3. [Busca de Cenas — óptico mesclado](#3-busca-de-cenas--óptico-mesclado)
4. [Verificação de Dados (hasData)](#4-verificação-de-dados-hasdata)
5. [Renderização — óptico (S2 / Landsat)](#5-renderização--óptico-s2--landsat)
6. [Renderização — Sentinel-1 (SAR)](#6-renderização--sentinel-1-sar)
7. [Proxy de Thumbnail](#7-proxy-de-thumbnail)
8. [Cobertura de Nuvens na Bbox](#8-cobertura-de-nuvens-na-bbox)

---

## 1. Health Check

```
GET /health
```

### Resposta 200

```json
{ "status": "ok" }
```

---

## 2. Busca de Cenas — por tipo

```
POST /api/search
```

Consulta o catálogo STAC do CDSE para um único tipo de satélite.

### Body (JSON)

```json
{
  "bbox": [-47.0, -23.0, -46.5, -22.5],
  "start": "2024-01-01",
  "end": "2024-01-31",
  "maxCloudCover": 80,
  "satelliteType": "sentinel2"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `bbox` | `[float, float, float, float]` | Sim | `[west, south, east, north]` WGS84 |
| `start` | `string` | Sim | Data inicial ISO 8601 |
| `end` | `string` | Sim | Data final ISO 8601 |
| `maxCloudCover` | `float` (0–100) | Não | Máx. % de nuvens (padrão: 80). Ignorado para `sentinel1`. |
| `satelliteType` | `"sentinel2"` \| `"landsat"` \| `"sentinel1"` | Sim | Tipo de satélite |

### Resposta 200

```json
{
  "scenes": [
    {
      "id": "S2A_MSIL2A_20240115T130259_N0510_R090_T22KCD",
      "date": "2024-01-15T13:02:59Z",
      "cloudCover": 5.2,
      "thumbnailHref": "https://sh.dataspace.copernicus.eu/...",
      "satelliteType": "sentinel2"
    }
  ]
}
```

**Ordenação:**
- `sentinel2` / `landsat`: por `cloudCover` crescente (menos nuvens primeiro)
- `sentinel1`: por `date` decrescente (mais recente primeiro)

### Erros

| Status | Descrição |
|--------|-----------|
| 422 | Payload inválido (campos ausentes ou valores fora do domínio) |
| 502 | Erro ao consultar o catálogo STAC do CDSE |

---

## 3. Busca de Cenas — óptico mesclado

```
POST /api/search/optical
```

Realiza buscas em paralelo para Sentinel-2 e Landsat e mescla os resultados.

### Body (JSON)

```json
{
  "bbox": [-47.0, -23.0, -46.5, -22.5],
  "start": "2024-01-01",
  "end": "2024-01-31",
  "maxCloudCover": 80
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `bbox` | `[float x4]` | Sim | `[west, south, east, north]` WGS84 |
| `start` | `string` | Sim | Data inicial ISO 8601 |
| `end` | `string` | Sim | Data final ISO 8601 |
| `maxCloudCover` | `float` (0–100) | Não | Máx. % de nuvens (padrão: 80) |

### Resposta 200

Mesmo formato de `{ "scenes": [...] }`.

**Ordenação:** data decrescente; no mesmo dia, `cloudCover` crescente.
Se o Landsat falhar, retorna apenas cenas Sentinel-2 (degradação graciosa).

---

## 4. Verificação de Dados (hasData)

```
POST /api/hasData
```

Verifica se há dados reais na bbox para a data informada, usando um tile 64×64 como sonda.

### Body (JSON)

```json
{
  "bbox": [-47.0, -23.0, -46.5, -22.5],
  "date": "2024-01-15",
  "satelliteType": "sentinel2"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `bbox` | `[float x4]` | Sim | |
| `date` | `string` | Sim | Data central (YYYY-MM-DD) |
| `satelliteType` | `"sentinel2"` \| `"landsat"` \| `"sentinel1"` | Sim | |

### Resposta 200

```json
true
```
ou
```json
false
```

**Heurística:** se o PNG de resposta tiver mais de `HAS_DATA_THRESHOLD_BYTES` (padrão: 1500 bytes), considera que há dados. Erros de rede/API resultam em `false`.

---

## 5. Renderização — óptico (S2 / Landsat)

```
POST /api/render
```

Chama a Sentinel Hub Process API e retorna uma imagem PNG renderizada.

### Body (JSON)

```json
{
  "bbox": [-47.0, -23.0, -46.5, -22.5],
  "date": "2024-01-15",
  "visualType": "truecolor",
  "resolution": "medium",
  "maxCloudCover": 30,
  "satelliteType": "sentinel2"
}
```

| Campo | Tipo | Padrão | Descrição |
|-------|------|--------|-----------|
| `bbox` | `[float x4]` | — | |
| `date` | `string` | — | Data de referência. A janela temporal é ±15 dias. |
| `visualType` | string | `"truecolor"` | Ver tabela abaixo |
| `resolution` | `"low"` \| `"medium"` \| `"high"` \| `"native"` | `"medium"` | |
| `maxCloudCover` | `float` | 30 | |
| `satelliteType` | `"sentinel2"` \| `"landsat"` | `"sentinel2"` | |

#### Tipos de visualização

| `visualType` | Sentinel-2 | Landsat |
|---|---|---|
| `truecolor` | B04, B03, B02 → RGB natural | B04, B03, B02 |
| `falsecolor` | B08, B04, B03 → falsa cor (NIR) | B05, B04, B03 |
| `ndvi` | (B08-B04)/(B08+B04), colorizado | (B05-B04)/(B05+B04) |
| `evi` | 2.5×(B08-B04)/(B08+6B04-7.5B02+1) | idem com B05/NIR |
| `swir` | B11, B08, B03 | B07, B05, B03 |
| `ndmi` | (B08-B11)/(B08+B11), colorizado | (B05-B06)/(B05+B06) |
| `ndwi` | (B03-B08)/(B03+B08), colorizado | (B03-B05)/(B03+B05) |

#### Resoluções

| `resolution` | Pixels |
|---|---|
| `low` | max 512 px no lado maior |
| `medium` | max 1024 px no lado maior |
| `high` | max 2048 px no lado maior |
| `native` | ~10 m/px, máximo 2500 px |

A imagem mantém o **aspect ratio** da bbox.

### Resposta 200

`Content-Type: image/png`
Corpo: bytes binários do PNG.

---

## 6. Renderização — Sentinel-1 (SAR)

```
POST /api/render/s1
```

### Body (JSON)

```json
{
  "bbox": [-47.0, -23.0, -46.5, -22.5],
  "date": "2024-01-15",
  "visualType": "rgb",
  "resolution": "medium"
}
```

| Campo | Tipo | Padrão | Descrição |
|-------|------|--------|-----------|
| `bbox` | `[float x4]` | — | |
| `date` | `string` | — | Janela temporal: ±6 dias |
| `visualType` | `"vv"` \| `"vh"` \| `"rgb"` \| `"rvi"` | `"rgb"` | |
| `resolution` | `"low"` \| `"medium"` \| `"high"` \| `"native"` | `"medium"` | |

#### Tipos de visualização Sentinel-1

| `visualType` | Descrição |
|---|---|
| `vv` | Polarização VV em escala de cinza (`√VV × 3`) |
| `vh` | Polarização VH em escala de cinza (`√VH × 6`) |
| `rgb` | RGB composto: R=√VV×3, G=√VH×6, B=√(VV/VH)×1.5 |
| `rvi` | Radar Vegetation Index (`4×VH/(VV+VH)`), colorizado |

### Resposta 200

`Content-Type: image/png`

---

## 7. Proxy de Thumbnail

```
GET /api/thumbnail?href=<url>
```

Faz um GET autenticado no URL do thumbnail e devolve os bytes da imagem.

### Query Parameters

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `href` | `string` | Sim | URL do thumbnail (campo `assets.thumbnail.href` retornado pelo endpoint search) |

### Resposta 200

`Content-Type: image/jpeg` (ou `image/png`, conforme o CDSE retornar)
Corpo: bytes binários da imagem.

### Segurança (SSRF Protection)

O backend valida que o domínio de `href` está na lista `ALLOWED_THUMBNAIL_DOMAINS` (padrão: `dataspace.copernicus.eu` e seus subdomínios). Domínios externos são rejeitados com **400**.

### Erros

| Status | Descrição |
|--------|-----------|
| 400 | Domínio do `href` não permitido |
| 404 | Thumbnail não encontrado no CDSE |
| 422 | Parâmetro `href` ausente |

---

## 8. Cobertura de Nuvens na Bbox

```
POST /api/cloudCover
GET  /api/cloudCover
```

Calcula a porcentagem de cobertura de nuvens **dentro da bbox informada** para uma cena Sentinel-2 L2A, usando a banda SCL (Scene Classification Layer).

> **Nota:** este endpoint é uma melhoria sobre o `cloudCover` do catálogo STAC, que reflete a cena inteira. Este valor é específico para a área do usuário.

### POST — Body (JSON)

```json
{
  "sceneId": "S2A_MSIL2A_20240115T130259_N0510_R090_T22KCD",
  "bbox": [-47.0, -23.0, -46.5, -22.5],
  "date": "2024-01-15"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `sceneId` | `string` | Sim | ID da cena retornado pelo endpoint search |
| `bbox` | `[float x4]` | Sim | |
| `date` | `string` | Sim | Data ISO 8601 da cena |

### GET — Query Parameters

```
GET /api/cloudCover?sceneId=<id>&bbox=-47.0,-23.0,-46.5,-22.5&date=2024-01-15
```

### Resposta 200

```json
{
  "cloudCover": 12.5,
  "sceneId": "S2A_MSIL2A_20240115T130259_N0510_R090_T22KCD"
}
```

`cloudCover` é um número de 0 a 100 representando a % de pixels classificados como nuvem (SCL valores 8 ou 9) dentro da bbox.

#### Valores SCL considerados nuvem

| Valor SCL | Classe |
|-----------|--------|
| 8 | Cloud medium probability |
| 9 | Cloud high probability |

---

## Tipos de erros comuns

| Status | Significado |
|--------|-------------|
| 422 | Validação falhou — verifique os campos e tipos do payload |
| 502 | Erro ao se comunicar com o CDSE — verifique as credenciais e status do serviço |

---

## Exemplos de uso (curl)

### Buscar cenas Sentinel-2

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "bbox": [-47.0, -23.0, -46.5, -22.5],
    "start": "2024-01-01",
    "end": "2024-01-31",
    "maxCloudCover": 30,
    "satelliteType": "sentinel2"
  }'
```

### Renderizar NDVI (Sentinel-2)

```bash
curl -X POST http://localhost:8000/api/render \
  -H "Content-Type: application/json" \
  -d '{
    "bbox": [-47.0, -23.0, -46.5, -22.5],
    "date": "2024-01-15",
    "visualType": "ndvi",
    "resolution": "medium",
    "satelliteType": "sentinel2"
  }' \
  --output ndvi.png
```

### Verificar se há dados

```bash
curl -X POST http://localhost:8000/api/hasData \
  -H "Content-Type: application/json" \
  -d '{
    "bbox": [-47.0, -23.0, -46.5, -22.5],
    "date": "2024-01-15",
    "satelliteType": "sentinel2"
  }'
# Retorna: true ou false
```

### Obter thumbnail

```bash
curl "http://localhost:8000/api/thumbnail?href=https://sh.dataspace.copernicus.eu/thumbnails/example.jpg" \
  --output thumb.jpg
```

### Cobertura de nuvens na bbox

```bash
curl -X POST http://localhost:8000/api/cloudCover \
  -H "Content-Type: application/json" \
  -d '{
    "sceneId": "S2A_MSIL2A_20240115T130259_N0510_R090_T22KCD",
    "bbox": [-47.0, -23.0, -46.5, -22.5],
    "date": "2024-01-15"
  }'
# Retorna: {"cloudCover": 12.5, "sceneId": "..."}
```
