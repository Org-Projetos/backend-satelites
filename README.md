# Agro Satélite — Backend

Backend Python/FastAPI que serve como proxy seguro para o **Copernicus Data Space Ecosystem (CDSE)**, expondo uma API REST simples para o app Flutter **Agro Satélite**.

## Visão geral

O app Flutter deixa de falar diretamente com o CDSE. Este backend:

- Guarda as credenciais CDSE (`client_id` / `client_secret`) com segurança
- Gerencia o token OAuth2 com cache automático e renovação transparente
- Expõe endpoints de busca de cenas, renderização, verificação de dados e thumbnail
- Implementa proteção contra SSRF no proxy de thumbnail

## Requisitos

- Python 3.11+

Verifique sua versão com:

```bash
python --version
```

---

## Passo a passo para rodar

### 1. Acesse a pasta do projeto

```bash
cd backend-agro
```

### 2. Crie o ambiente virtual (venv)

O ambiente virtual isola as dependências do projeto do Python global da sua máquina.

```bash
python -m venv venv
```

### 3. Ative o ambiente virtual

**Windows:**
```bash
venv\Scripts\activate
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

Você saberá que funcionou quando aparecer `(venv)` no início do terminal.

### 4. Instale as dependências

```bash
pip install -e ".[dev]"
```

Isso instala o projeto e todas as dependências (incluindo as de teste).

### 5. Crie o arquivo de configuração

```bash
copy .env.example .env
```

> **Linux/macOS:** use `cp .env.example .env`

### 6. Preencha suas credenciais CDSE

Abra o `.env` e edite as duas linhas obrigatórias:

```env
CDSE_CLIENT_ID=seu_client_id_aqui
CDSE_CLIENT_SECRET=seu_client_secret_aqui
```

Obtenha suas credenciais em: https://dataspace.copernicus.eu/

### 7. Rode o servidor

```bash
uvicorn app.main:app --reload
```

O servidor estará disponível em `http://localhost:8000`.

| URL | Descrição |
|-----|-----------|
| http://localhost:8000/health | Verifica se o servidor está no ar |
| http://localhost:8000/docs | Documentação interativa (Swagger UI) |
| http://localhost:8000/redoc | Documentação alternativa |

---

## Rodando os testes

Com a venv ativada:

```bash
pytest
```

## Docker

```bash
# Build
docker build -t backend-agro .

# Run
docker run -p 8000:8000 --env-file .env backend-agro
```

Ou via Docker Compose:

```bash
docker compose up
```

## Testes

```bash
pytest
```

Para ver cobertura:

```bash
pip install pytest-cov
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

## Estrutura do projeto

```
backend-agro/
├── app/
│   ├── main.py               # Criação do app FastAPI, middleware CORS, rotas
│   ├── config.py             # Settings via pydantic-settings (.env)
│   ├── auth/
│   │   └── cdse.py           # Gerenciamento de token OAuth2 com cache
│   ├── models/
│   │   └── schemas.py        # Modelos Pydantic (request / response)
│   ├── evalscripts/
│   │   ├── __init__.py       # Dispatcher get_evalscript(satellite, visual)
│   │   ├── sentinel2.py      # Evalscripts JS para Sentinel-2 L2A
│   │   ├── landsat.py        # Evalscripts JS para Landsat 8/9
│   │   └── sentinel1.py      # Evalscripts JS para Sentinel-1 GRD
│   ├── services/
│   │   ├── stac.py           # Busca de cenas via catálogo STAC
│   │   └── process_api.py    # Renderização e hasData via Process API
│   └── routes/
│       ├── search.py         # POST /api/search, POST /api/search/optical
│       ├── render.py         # POST /api/render, POST /api/render/s1
│       ├── has_data.py       # POST /api/hasData
│       ├── thumbnail.py      # GET /api/thumbnail
│       └── cloud_cover.py    # POST/GET /api/cloudCover
├── tests/
│   ├── conftest.py           # Fixtures, mocks de dados
│   ├── test_auth.py
│   ├── test_search.py
│   ├── test_render.py
│   ├── test_has_data.py
│   ├── test_thumbnail.py
│   ├── test_cloud_cover.py
│   ├── test_evalscripts.py
│   └── test_health.py
├── docs/
│   └── API.md                # Documentação completa dos endpoints
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── .gitignore
```

## Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/search` | Busca cenas STAC por tipo de satélite |
| POST | `/api/search/optical` | Busca mesclada S2 + Landsat |
| POST | `/api/hasData` | Verifica se há dados na bbox/data |
| POST | `/api/render` | Renderiza imagem óptica (S2/Landsat) → PNG |
| POST | `/api/render/s1` | Renderiza imagem SAR Sentinel-1 → PNG |
| GET | `/api/thumbnail?href=...` | Proxy de thumbnail com auth CDSE |
| POST/GET | `/api/cloudCover` | % de nuvens na bbox (SCL Sentinel-2) |

Documentação completa em [docs/API.md](docs/API.md) e em `/docs` (Swagger UI).

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `CDSE_CLIENT_ID` | — | Client ID CDSE (obrigatório) |
| `CDSE_CLIENT_SECRET` | — | Client Secret CDSE (obrigatório) |
| `TOKEN_RENEWAL_MARGIN_SECONDS` | 120 | Margem antes de renovar o token |
| `HAS_DATA_THRESHOLD_BYTES` | 1500 | Tamanho mínimo PNG para considerar dados |
| `CORS_ORIGINS` | `["*"]` | Origins CORS permitidas |
| `ALLOWED_THUMBNAIL_DOMAINS` | `["dataspace.copernicus.eu"]` | Domínios permitidos para proxy |
| `DEBUG` | `false` | Modo debug |

## Segurança

- **Credenciais CDSE**: nunca expostas ao cliente, armazenadas apenas no servidor via variáveis de ambiente.
- **SSRF Protection**: o endpoint `/api/thumbnail` valida que o `href` pertence a domínios configurados.
- **CORS**: configure `CORS_ORIGINS` com as origens do seu app em produção.
