"""
Serviço de análise de imagens via Anthropic Claude.
"""

import base64
from typing import Any

import httpx

from app.config import get_settings


# Template do prompt para análise agrícola
AI_ANALYSIS_PROMPT = """
Você é o assistente técnico de um sistema de monitoramento agrícola operacional baseado em imagens do satélite Sentinel-2.

Seu papel é gerar um relatório quantitativo e operacional, com linguagem clara e objetiva, voltado para produtores rurais.

IMAGENS FORNECIDAS:
1. Imagem de cor natural - mostra a área como o olho humano veria
2. Imagem NDVI - mostra a vitalidade da vegetação (verde = saudável, amarelo/vermelho = problemático)

ÁREA ANALISADA: {area_hectares} hectares
DATA DA ANÁLISE: {date}
COORDENADAS: {bbox}

Regras obrigatórias:

- Não realizar diagnóstico agronômico específico.
- Não identificar pragas ou doenças.
- Não recomendar aplicação de insumos.
- Não estimar produtividade exata.
- Utilizar linguagem indicativa e preventiva.
- Sempre deixar claro que é uma ferramenta de apoio à decisão.

Formato obrigatório do relatório:

1. Visão geral da condição vegetativa atual
2. Análise da distribuição da vegetação (áreas saudáveis vs problemáticas)
3. Identificação de áreas que merecem atenção
4. Nível de prioridade de vistoria (baixo, moderado ou alto)
5. Conclusão operacional

O relatório deve permitir que o produtor responda:

- Onde devo ir?
- Quantos hectares aparentam ter problema?
- Qual a prioridade de inspeção?

Use linguagem técnica simples e direta.
Não use emojis.
Não use termos excessivamente acadêmicos.
Baseie sua análise nas imagens fornecidas.
"""


def _image_content(label: str, image_b64: str) -> list[dict[str, Any]]:
    return [
        {"type": "text", "text": label},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_b64,
            },
        },
    ]


def _extract_text_content(result: dict[str, Any]) -> str:
    text_blocks = [
        block.get("text", "")
        for block in result.get("content", [])
        if block.get("type") == "text"
    ]
    return "\n".join(block for block in text_blocks if block).strip()


async def analyze_with_claude_vision(
    truecolor_b64: str,
    ndvi_b64: str,
    area_hectares: float,
    date: str,
    bbox: list[float],
    custom_prompt: str | None = None,
    previous_truecolor_b64: str | None = None,
    previous_ndvi_b64: str | None = None,
) -> str:
    """
    Envia imagens para Claude e recebe relatório de análise.
    
    Args:
        truecolor_b64: Imagem de cor natural em base64
        ndvi_b64: Imagem NDVI em base64
        area_hectares: Área em hectares
        date: Data da análise
        bbox: Coordenadas da área
        custom_prompt: Prompt customizado (opcional). Se não fornecido, usa o template padrão.
        previous_truecolor_b64: Imagem anterior de cor natural em base64 (opcional)
        previous_ndvi_b64: Imagem NDVI anterior em base64 (opcional)
    
    Returns:
        Relatório gerado pela IA
    """
    settings = get_settings()
    
    if not settings.anthropic_api_key:
        raise ValueError(
            "Anthropic API key não configurada. "
            "Configure a variável ANTHROPIC_API_KEY no arquivo .env"
        )
    
    # Usa prompt customizado ou padrão
    if custom_prompt:
        prompt = custom_prompt
    else:
        # Prepara o prompt com os dados específicos
        prompt = AI_ANALYSIS_PROMPT.format(
            area_hectares=area_hectares,
            date=date,
            bbox=bbox
        )
    
    content: list[dict[str, Any]] = []
    content.extend(_image_content("Imagem recente 1: cor natural (truecolor)", truecolor_b64))
    content.extend(_image_content("Imagem recente 2: índice de vegetação (NDVI)", ndvi_b64))

    if previous_truecolor_b64 and previous_ndvi_b64:
        content.extend(_image_content("Imagem anterior 1: cor natural (truecolor)", previous_truecolor_b64))
        content.extend(_image_content("Imagem anterior 2: índice de vegetação (NDVI)", previous_ndvi_b64))

    content.append({"type": "text", "text": prompt})

    messages = [
        {
            "role": "user",
            "content": content,
        }
    ]
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.anthropic_api_url,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": settings.anthropic_version,
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 2000,
                "messages": messages,
                "temperature": 0.3,
            },
            timeout=120,
        )
        response.raise_for_status()
        
        result = response.json()
        text = _extract_text_content(result)
        if not text:
            raise ValueError("Resposta do Claude não retornou conteúdo de texto.")
        return text


def encode_image_to_base64(image_bytes: bytes) -> str:
    """Converte bytes de imagem para string base64."""
    return base64.b64encode(image_bytes).decode('utf-8')
