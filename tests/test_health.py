"""Testes básicos de health check e estrutura da API."""


def test_health_endpoint(client):
    """Endpoint /health deve retornar status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_docs_available(client):
    """Documentação Swagger deve estar acessível."""
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_openapi_schema(client):
    """Schema OpenAPI deve estar disponível e bem formado."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "Agro Satélite — Backend"
    # Verifica endpoints principais presentes
    paths = schema["paths"]
    assert "/api/search" in paths
    assert "/api/search/optical" in paths
    assert "/api/hasData" in paths
    assert "/api/render" in paths
    assert "/api/render/s1" in paths
    assert "/api/thumbnail" in paths
    assert "/api/cloudCover" in paths
