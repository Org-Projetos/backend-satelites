# Especificação do backend — Agro Satélite

Este documento descreve o que o **backend** deve implementar para substituir a lógica que hoje está no app (requisições ao Copernicus Data Space, Process API e, opcionalmente, tiler para fontes STAC/COG). O app Flutter passará a chamar **sua API** em vez de falar direto com o CDSE.

---

## 1. Visão geral

| O que o app faz hoje (no cliente) | O que o backend deve oferecer |
|-----------------------------------|-------------------------------|
| Obtém token CDSE (client_credentials) | Backend guarda `client_id`/`client_secret` e obtém token internamente |
| POST ao catálogo STAC (busca de cenas) | Endpoint **search** que repassa ao STAC e devolve lista no formato do app |
| Process API (renderizar PNG por bbox/data/evalscript) | Endpoint **render** que chama a Process API e devolve PNG (ou usa tiler) |
| hasData (tile 64×64 para filtrar cenas sem dados) | Endpoint **hasData** que faz a mesma chamada e devolve booleano |
| Thumbnail (GET com Bearer) | Endpoint **thumbnail** (proxy com auth) |

**Contrato:** o app envia `bbox`, `date`, `satelliteType`, `visualType`, etc.; o backend devolve **JSON** (listas de cenas, boolean) ou **PNG** (imagem). O app **não** envia credenciais CDSE; o backend é o único que fala com o CDSE (e com o tiler, se houver).

---

## 2. URLs e autenticação CDSE

O backend precisa falar com o **Copernicus Data Space Ecosystem (CDSE)** usando as mesmas URLs que o app usa hoje.

### 2.1 URLs base

| Uso | URL |
|-----|-----|
| **Token** | `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token` |
| **Catálogo STAC** | `https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search` |
| **Process API** | `https://sh.dataspace.copernicus.eu/api/v1/process` |

### 2.2 Obtenção do token

- **Método:** `POST` no URL do token.
- **Headers:** `Content-Type: application/x-www-form-urlencoded`
- **Body (form):**
  - `grant_type` = `client_credentials`
  - `client_id` = (credencial CDSE do backend)
  - `client_secret` = (credencial CDSE do backend)

- **Resposta 200:** JSON com `access_token` (string) e `expires_in` (segundos). O backend deve **cachear** o token e renovar antes de expirar (ex.: margem de 2 minutos).

Todo request ao **catálogo** e à **Process API** deve enviar:
- **Header:** `Authorization: Bearer <access_token>`
- **Header:** `Content-Type: application/json` (onde aplicável)

---

## 3. Busca de cenas (STAC)

O app precisa de dois fluxos de busca:

1. **Por tipo de satélite:** Sentinel-2, Landsat ou Sentinel-1.
2. **Óptico mesclado:** Sentinel-2 **e** Landsat na mesma chamada, mesclados e ordenados.

### 3.1 Endpoint sugerido: busca por tipo

**POST** `/api/search` (ou nome equivalente)

**Body (JSON):**

```json
{
  "bbox": [west, south, east, north],
  "start": "YYYY-MM-DD",
  "end": "YYYY-MM-DD",
  "maxCloudCover": 80,
  "satelliteType": "sentinel2"
}
```

- `bbox`: array de 4 números, WGS84 (west, south, east, north).
- `start` / `end`: datas em ISO (pode ser só data ou com hora).
- `maxCloudCover`: 0–100; usado apenas para **sentinel2** e **landsat**.
- `satelliteType`: `"sentinel2"` | `"landsat"` | `"sentinel1"`.

**Implementação no backend:** fazer um **POST** para o catálogo CDSE:

- **URL:** `https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search`
- **Body (JSON):**

```json
{
  "collections": ["<collection>"],
  "bbox": [west, south, east, north],
  "datetime": "<from>/<to>",
  "limit": 50
}
```

- **Coleções:**
  - `sentinel2` → `sentinel-2-l2a`
  - `landsat` → `landsat-ot-l1`
  - `sentinel1` → `sentinel-1-grd`

- **Datetime:** `from` e `to` em ISO 8601 (ex.: `2024-01-01T00:00:00Z` / `2024-03-31T23:59:59Z`).

- **Filtro de nuvens (apenas sentinel2 e landsat):** adicionar ao body:
  - `"filter": "eo:cloud_cover <= <maxCloudCover>"`
  - `"filter-lang": "cql2-text"`

A resposta do STAC é um GeoJSON com `features[]`. Cada feature tem:
- `id`: string
- `properties.datetime`: string ISO
- `properties["eo:cloud_cover"]`: número (ou ausente; usar 0)
- `assets.thumbnail.href`: string (opcional)

### 3.2 Formato de resposta do backend para o app

O backend deve devolver uma lista de **cenas** no formato que o app já espera (para minimizar mudanças no cliente):

```json
{
  "scenes": [
    {
      "id": "<string>",
      "date": "YYYY-MM-DDTHH:MM:SSZ",
      "cloudCover": 0.0,
      "thumbnailHref": "<url ou null>",
      "satelliteType": "sentinel2"
    }
  ]
}
```

- `id`: igual ao `id` da feature STAC.
- `date`: igual a `properties.datetime`.
- `cloudCover`: `properties["eo:cloud_cover"]` ou 0 se ausente.
- `thumbnailHref`: `assets.thumbnail.href` ou `null`.
- `satelliteType`: o mesmo que foi pedido na request.

**Ordenação:**
- Para **sentinel2** e **landsat:** ordenar por `cloudCover` ascendente (menos nuvens primeiro).
- Para **sentinel1:** ordenar por `date` descendente (mais recente primeiro).

### 3.3 Endpoint: busca óptico mesclada (S2 + Landsat)

**POST** `/api/search/optical` (ou nome equivalente)

**Body (JSON):**

```json
{
  "bbox": [west, south, east, north],
  "start": "YYYY-MM-DD",
  "end": "YYYY-MM-DD",
  "maxCloudCover": 80
}
```

**Implementação:**  
1. Chamar a busca STAC duas vezes (em paralelo): uma para `sentinel-2-l2a`, outra para `landsat-ot-l1` (mesmos bbox, start, end, maxCloudCover).  
2. Se a busca Landsat falhar (ex.: coleção indisponível), devolver só as cenas S2.  
3. Mesclar as duas listas e ordenar: primeiro por **data decrescente**, depois por **cloudCover crescente** (no mesmo dia, menos nuvens primeiro).  
4. Marcar cada cena com o `satelliteType` correto (`sentinel2` ou `landsat`).  
5. Devolver o mesmo formato `{ "scenes": [ ... ] }`.

---

## 4. Verificação “hasData”

O app usa isso para filtrar cenas que não têm dados reais na bbox (evitar listar cenas vazias).

### 4.1 Endpoint sugerido

**POST** `/api/hasData`

**Body (JSON):**

```json
{
  "bbox": [west, south, east, north],
  "date": "YYYY-MM-DD",
  "satelliteType": "sentinel2"
}
```

**Resposta:** `true` ou `false`.

### 4.2 Implementação

Fazer uma única chamada à **Process API** pedindo um tile pequeno (ex.: 64×64 px) com evalscript RGB simples:

- **Óptico (S2 ou Landsat):**
  - Coleção: `sentinel-2-l2a` ou `landsat-ot-l1`
  - Janela temporal: ±15 dias em torno de `date`
  - `maxCloudCoverage`: 30, `mosaickingOrder`: `leastCC`
  - Evalscript: 3 bandas (ex.: B04, B03, B02 para RGB), escala 2.5

- **Sentinel-1:**
  - Coleção: `sentinel-1-grd`
  - Janela: ±6 dias
  - `mosaickingOrder`: `mostRecent`
  - Evalscript: VV em escala de cinza (ex.: `Math.sqrt(s.VV)*3`)

O body da Process API deve seguir o mesmo formato da seção 5 (bounds, data, output, evalscript).  
**Heurística:** se o tamanho da resposta PNG &gt; ~1500 bytes, considerar que há dados; caso contrário, `false`. Falhas de rede/API podem ser tratadas como `false`.

---

## 5. Renderização de imagem (Process API)

O app pede uma imagem PNG para uma **bbox**, **data** e **tipo de visualização** (cor real, NDVI, etc.). O backend deve chamar a Process API do CDSE e devolver o PNG (ou, no futuro, usar o tiler para fontes que não têm Process API).

### 5.1 Endpoint sugerido: óptico (Sentinel-2 / Landsat)

**POST** `/api/render` (ou GET com query; se GET, bbox/dates em query params)

**Body (JSON):**

```json
{
  "bbox": [west, south, east, north],
  "date": "YYYY-MM-DD",
  "visualType": "truecolor",
  "resolution": "medium",
  "maxCloudCover": 30,
  "satelliteType": "sentinel2"
}
```

- `visualType`: `truecolor` | `falsecolor` | `ndvi` | `evi` | `swir` | `ndmi` | `ndwi`
- `resolution`: `low` (512 px) | `medium` (1024 px) | `high` (2048 px) | `native` (~10 m/px)
- `maxCloudCover`: 0–100
- `satelliteType`: `sentinel2` | `landsat`

**Resposta:** corpo binário **image/png** (e header `Content-Type: image/png`).

### 5.2 Endpoint: Sentinel-1 (SAR)

**POST** `/api/render/s1` (ou parâmetro no mesmo `/api/render`)

**Body (JSON):**

```json
{
  "bbox": [west, south, east, north],
  "date": "YYYY-MM-DD",
  "visualType": "rgb",
  "resolution": "medium"
}
```

- `visualType`: `vv` | `vh` | `rgb` | `rvi`

**Resposta:** image/png.

### 5.3 Formato do body da Process API (CDSE)

O backend monta um JSON e faz **POST** em  
`https://sh.dataspace.copernicus.eu/api/v1/process`  
com header `Authorization: Bearer <token>` e `Content-Type: application/json`.

**Estrutura geral:**

```json
{
  "input": {
    "bounds": {
      "bbox": [west, south, east, north],
      "properties": { "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84" }
    },
    "data": [
      {
        "type": "<collection>",
        "dataFilter": { ... },
        "processing": { ... }
      }
    ]
  },
  "output": {
    "width": <number>,
    "height": <number>,
    "responses": [{ "identifier": "default", "format": { "type": "image/png" } }]
  },
  "evalscript": "<string>"
}
```

#### Óptico (Sentinel-2 ou Landsat)

- **type:** `sentinel-2-l2a` ou `landsat-ot-l1`
- **dataFilter:**
  - `timeRange`: `{ "from": "<ISO>", "to": "<ISO>" }` — janela de **±15 dias** em torno de `date`
  - `maxCloudCoverage`: valor do request (ex.: 30)
  - `mosaickingOrder`: `"leastCC"`
- **processing:** `{ "upsampling": "BICUBIC", "downsampling": "BICUBIC" }`
- **evalscript:** depende de `visualType` e `satelliteType` (ver seção 6).

#### Sentinel-1

- **type:** `sentinel-1-grd`
- **dataFilter:**
  - `timeRange`: ±6 dias em torno de `date`
  - `mosaickingOrder`: `"mostRecent"`
- **processing:**
  - `backCoeff`: `"GAMMA0_TERRAIN"`
  - `orthorectify`: true
  - `demInstance`: `"COPERNICUS"`
- **evalscript:** conforme `visualType` (VV, VH, RGB, RVI) — seção 6.

#### Dimensões (width / height)

- **low:** máximo 512 px no lado maior; manter aspect ratio da bbox (ex.: se bbox mais larga que alta, width=512, height proporcional, mínimo 64).
- **medium:** 1024 px no lado maior.
- **high:** 2048 px no lado maior.
- **native:** calcular em metros (ex.: ~111320 m/grau em lat; longitude × cos(lat)); 10 m/px para S2/Landsat; 10 m/px para S1; limitar a um máximo (ex.: 2500 px) conforme documentação Sentinel Hub.

Fórmula de aspect ratio (exemplo para `maxPx = 1024`):

- `lngSpan = bbox[2] - bbox[0]`, `latSpan = bbox[3] - bbox[1]`
- Se `lngSpan >= latSpan`: width = 1024, height = round(1024 * latSpan / lngSpan), clamp height entre 64 e 1024.
- Caso contrário: height = 1024, width = round(1024 * lngSpan / latSpan), clamp width entre 64 e 1024.

---

## 6. Evalscripts (referência)

O backend precisa dos evalscripts exatos para cada `visualType` e satélite. Eles estão no app em `lib/models/copernicus_scene.dart`. Abaixo, **identificadores** e **bandas**; os scripts completos em JavaScript podem ser copiados desse arquivo ou mantidos num repositório do backend.

### 6.1 Sentinel-2 (coleção sentinel-2-l2a)

| visualType  | Bandas usadas | Observação |
|-------------|----------------|------------|
| truecolor   | B02, B03, B04  | RGB = 2.5×[B04,B03,B02] |
| falsecolor  | B03, B04, B08  | RGB = 2.5×[B08,B04,B03] |
| ndvi        | B04, B08       | (B08-B04)/(B08+B04), colorizado |
| evi         | B02, B04, B08  | 2.5*(B08-B04)/(B08+6*B04-7.5*B02+1), colorizado |
| swir        | B03, B08, B11  | RGB = 2.5×[B11,B08,B03] |
| ndmi        | B08, B11       | (B08-B11)/(B08+B11), colorizado |
| ndwi        | B03, B08       | (B03-B08)/(B03+B08), colorizado |

### 6.2 Landsat 8/9 (coleção landsat-ot-l1)

Bandas: B02 (azul), B03 (verde), B04 (vermelho), B05 (NIR), B06 (SWIR1), B07 (SWIR2).

| visualType  | Bandas | Observação |
|-------------|--------|------------|
| truecolor   | B02, B03, B04 | RGB = 2.5×[B04,B03,B02] |
| falsecolor  | B03, B04, B05 | RGB = 2.5×[B05,B04,B03] |
| ndvi        | B04, B05      | (B05-B04)/(B05+B04) — Landsat usa B05 como NIR |
| evi         | B02, B04, B05 | 2.5*(B05-B04)/(B05+6*B04-7.5*B02+1) |
| swir        | B03, B05, B07 | RGB = 2.5×[B07,B05,B03] |
| ndmi        | B05, B06      | (B05-B06)/(B05+B06) |
| ndwi        | B03, B05      | (B03-B05)/(B03+B05) |

### 6.3 Sentinel-1 (coleção sentinel-1-grd)

| visualType | Bandas | Observação |
|------------|--------|------------|
| vv         | VV     | Escala de cinza: sqrt(VV)*3 |
| vh         | VH     | Escala de cinza: sqrt(VH)*6 |
| rgb        | VV, VH | R=sqrt(VV)*3, G=sqrt(VH)*6, B=sqrt(VV/VH)*1.5 |
| rvi        | VV, VH | 4*VH/(VV+VH), colorizado por faixas |

Os scripts completos (incluindo colorização NDVI/EVI/NDMI/NDWI e RVI) estão em `lib/models/copernicus_scene.dart` (constantes `_s2*`, `_landsat*`, `_s1*`). O backend pode extraí-los para arquivos ou banco e escolher pelo par `(satelliteType, visualType)`.

---

## 7. Thumbnail (proxy com auth)

Algumas cenas STAC trazem `assets.thumbnail.href` que exige **Bearer token** CDSE. O app não deve enviar o token; o backend faz o GET e devolve os bytes.

### 7.1 Endpoint sugerido

**GET** `/api/thumbnail?href=<url_encoded_href>`

Ou **POST** com body `{ "href": "<url>" }` e resposta binária (image/jpeg ou image/png).

**Implementação:**  
1. Obter token CDSE.  
2. GET em `href` com header `Authorization: Bearer <token>`.  
3. Devolver o corpo da resposta com o mesmo `Content-Type` (e status 200, ou 4xx/5xx em caso de erro).

---

## 8. Tiler (fontes sem Process API)

Para fontes que **não** têm Process API (ex.: CBERS-4A, Amazonia-1, Landsat USGS, Brazil Data Cube), o backend pode implementar um **tiler** que:

1. **Busca** cenas via STAC (catálogo da fonte).
2. **Lê** apenas a região da bbox nos COG (Cloud Optimized GeoTIFF) — sem baixar cena inteira.
3. **Aplica** fórmulas de banda (RGB, NDVI, etc.) no servidor.
4. **Devolve** PNG.

Assim, o app continua com o mesmo contrato: “bbox + data + visualização → PNG”.

### 8.1 Fluxo geral do tiler

1. **Entrada:** bbox, date (ou intervalo), fonte (ex.: `cbers4a`), visualType (ex.: `truecolor`, `ndvi`).
2. **STAC:** consultar o catálogo da fonte (ex.: `https://stac.scitekno.com.br/v100/search`) com bbox + datetime; obter features com links para assets (COG).
3. **Seleção de cena:** escolher a cena que cobre a bbox na data (ou a mais próxima, ou “melhor pixel” em janela).
4. **Leitura:** usar biblioteca (ex.: **rio-tiler**, Python) para ler apenas a **janela** correspondente à bbox nos COG (bandas necessárias).
5. **Band math:** aplicar a fórmula (RGB, NDVI, etc.) — equivalente ao evalscript, mas em código (ex.: NumPy).
6. **Saída:** gerar PNG (ex.: PIL/Imageio) e devolver no response.

### 8.2 Exemplo: CBERS-4A (AWS)

- **STAC:** `https://stac.scitekno.com.br/v100` (ou catálogo estático citado na doc do app).  
- **Collections:** MUX, WFI, etc. (conforme doc CBERS).  
- **Dados:** COG no S3 (bucket `brazil-eosats`), acesso público read-only.  
- **Ferramentas:** **rio-tiler-pds** (ou rio-tiler genérico) com drivers para o COG; método `part(bbox)` ou equivalente para ler a região.  
- **Bandas MUX (ex.):** azul, verde, vermelho, NIR — mapear para True Color e NDVI como no óptico.

### 8.3 Endpoint unificado (Process API + tiler)

Para o app não precisar saber se a imagem veio do CDSE ou do tiler, o backend pode ter um único endpoint, por exemplo:

**POST** `/api/render`

**Body:** além dos campos atuais, incluir um campo opcional `source` ou usar `satelliteType` com valores estendidos:

- `sentinel2`, `landsat`, `sentinel1` → Process API CDSE (como hoje).
- `cbers4a`, `amazonia1`, etc. → tiler (STAC + COG + band math → PNG).

Assim, o app envia sempre a mesma request; o backend decide internamente se chama a Process API ou o tiler.

### 8.4 Cache (recomendado)

- Cachear imagens por chave: `(bbox, date, source, visualType, resolution)` (e eventualmente hash da bbox se precisar normalizar).
- TTL configurável (ex.: 24 h ou 7 dias) para reduzir carga no CDSE e no tiler.
- Headers HTTP de cache (ex.: `Cache-Control`, `ETag`) para o app ou CDN.

---

## 9. Possibilidade de melhoria: medição de nuvens nas fotos

Hoje a **porcentagem de nuvens** exibida no app vem do catálogo STAC: o campo **`eo:cloud_cover`** fornecido pelo provedor refere-se à **cena inteira** (todo o tile do satélite), não à **área desenhada pelo usuário** (bbox/polígono). Por isso o valor pode parecer “mentiroso”:

- Cena com **10%** na lista pode estar com nuvem em cima do talhão do usuário (a média da cena é baixa, mas a nuvem caiu na área dele).
- Cena com **40%** pode estar limpa na região do usuário (a nuvem está em outra parte do tile).

Ou seja: o número é **global da cena**, não “porcentagem de nuvem na minha área”.

### 9.1 Melhoria: porcentagem de nuvens na bbox do usuário

É possível estimar a **porcentagem de nuvem só na área do usuário** usando máscara de nuvem **dentro da bbox**:

**Sentinel-2 L2A — SCL (Scene Classification Layer)**  
O produto L2A inclui a banda **SCL**, que classifica cada pixel (solo, vegetação, nuvem, sombra de nuvem, etc.). O backend pode:

1. Para a cena e a bbox escolhidas, obter os dados da banda SCL apenas na janela da bbox (via Process API evalscript que retorne valores, ou via COG/rio-tiler se o backend tiver tiler).
2. Contar quantos pixels estão classificados como nuvem (e opcionalmente sombra de nuvem).
3. Calcular: **% nuvem na área = (pixels nuvem / total de pixels na bbox) × 100**.

Esse valor reflete de fato o que o usuário vê ao abrir a foto naquela região.

**Valores SCL (Sentinel-2 L2A) relevantes para nuvem:**

| Valor | Classe            | Uso típico na conta |
|-------|-------------------|----------------------|
| 3     | Cloud shadows     | Incluir como “coberto” se desejado |
| 8     | Cloud medium probability | Nuvem |
| 9     | Cloud high probability   | Nuvem |
| 10    | Thin cirrus        | Incluir como nuvem se desejado |

Definição usual: considerar “nuvem” os valores **8 e 9**; opcionalmente **3** (sombra) e **10** (cirrus).

### 9.2 Implementação no backend

- **Endpoint sugerido:**  
  **GET** ou **POST** `/api/cloudCover`  
  - Parâmetros: `sceneId` (ou `scene_id`), `bbox` (ou já conhecido pela cena).  
  - Resposta: `{ "cloudCover": 12.5 }` (porcentagem 0–100 na bbox).

- **Opção A — Process API:**  
  A Process API devolve imagens, não estatísticas. Dá para usar um evalscript que, na bbox, amostra a SCL e devolve uma “imagem” muito pequena (ex.: 1×1) onde o valor codificado seja a porcentagem (ex.: valor 0–255 = 0–100%). O backend decodifica e devolve o número. É um workaround; a opção B escala melhor.

- **Opção B — Tiler / COG:**  
  Se o backend já lê COG (tiler): buscar o asset da **SCL** da cena que cobre a bbox; usar rio-tiler (ou similar) para ler só a janela da bbox na SCL; contar pixels com valor 8, 9 (e 3, 10 se desejar); calcular a % e devolver no endpoint acima.

- **Integração com a lista de cenas:**  
  - No **search** (ou **search/optical**), o backend pode, para cada cena retornada, chamar internamente o cálculo de cloud cover na bbox e preencher um campo `cloudCoverInBbox` (ou substituir o `cloudCover` vindo do STAC por esse valor quando disponível).  
  - Ou o app chama `/api/cloudCover?sceneId=...&bbox=...` depois de receber a lista, para exibir/enviar a % “real” na área.  
  - Ordenação e filtros (ex.: “mostrar primeiro as com menos nuvem”) passam a usar a % na bbox, tornando a experiência mais coerente com o que se vê na foto.

### 9.3 Landsat e outras fontes

- **Landsat:** produtos podem ter máscara de qualidade ou banda de nuvem (ex.: QA_PIXEL ou similar). O mesmo raciocínio vale: ler a máscara na bbox, contar pixels “nuvem”, devolver %.
- **Outras fontes (CBERS, etc.):** se houver máscara de nuvem ou banda de qualidade no COG, o tiler pode expor o mesmo tipo de endpoint para uma “cloud cover na bbox” consistente com o que o usuário vê.

Incluir essa melhoria no backend torna a medição de nuvens nas fotos mais confiável e alinhada à área de interesse do usuário.

---

## 10. Resumo dos endpoints sugeridos

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/search` | Busca STAC por tipo (sentinel2 \| landsat \| sentinel1); devolve `{ "scenes": [...] }` |
| POST | `/api/search/optical` | Busca S2 + Landsat mesclada; devolve `{ "scenes": [...] }` |
| POST | `/api/hasData` | Verifica se há dados na bbox/date; devolve `true`/`false` |
| POST | `/api/render` | Imagem óptica (S2/Landsat) → PNG |
| POST | `/api/render/s1` | Imagem Sentinel-1 → PNG |
| GET  | `/api/thumbnail?href=...` | Proxy de thumbnail com auth CDSE |
| GET/POST | `/api/cloudCover` | *(Melhoria)* Porcentagem de nuvem **na bbox** (SCL/máscara); parâmetros `sceneId`, `bbox`. |

Todos os que recebem bbox/dates: **bbox** em WGS84 `[west, south, east, north]`; datas em ISO 8601.

---

## 11. Segurança e variáveis de ambiente

- **Credenciais CDSE:** não devem ir para o app. Guardar no backend como variáveis de ambiente (ex.: `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`).
- **Rate limit:** considerar limite por IP ou por API key para evitar abuso.
- **CORS:** configurar origens permitidas para o app (web/mobile conforme deploy).
- **Thumbnail:** validar que o `href` é de domínio confiável (ex.: `*.dataspace.copernicus.eu`) para evitar SSRF.

---

## 12. Referências

- Copernicus Data Space: https://dataspace.copernicus.eu/
- Documentação CDSE (APIs, STAC, Process): https://documentation.dataspace.copernicus.eu/
- Sentinel Hub Process API (evalscript, collections): documentação oficial Sentinel Hub / CDSE.
- rio-tiler (Python): https://github.com/developmentseed/rio-tiler
- CBERS on AWS / STAC: https://stac.scitekno.com.br/v100 — doc no repositório do app (`docs/CBERS-4A-vs-Copernicus-Sentinel2.md`, `docs/APIs-gratuitas-resolucao-e-Brasil.md`).

Documento gerado para o projeto **Agro Satélite**. Backend a ser implementado de forma independente; o app Flutter será adaptado para consumir estes endpoints em vez de chamar o CDSE diretamente.
