"""
Serviço de análise de imagens via OpenAI GPT-4o Vision.
"""

import asyncio
import base64
import time
from typing import Optional

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


async def analyze_with_gpt4o_vision(
    truecolor_b64: str,
    ndvi_b64: str,
    area_hectares: float,
    date: str,
    bbox: list[float],
) -> str:
    """
    Envia imagens para GPT-4o Vision e recebe relatório de análise.
    
    Args:
        truecolor_b64: Imagem de cor natural em base64
        ndvi_b64: Imagem NDVI em base64
        area_hectares: Área em hectares
        date: Data da análise
        bbox: Coordenadas da área
    
    Returns:
        Relatório gerado pela IA
    """
    settings = get_settings()
    
    # Verifica se a API key está configurada
    if not settings.openai_api_key:
        raise ValueError(
            "OpenAI API key não configurada. "
            "Configure a variável OPENAI_API_KEY no arquivo .env"
        )
    
    # Prepara o prompt com os dados específicos
    prompt = AI_ANALYSIS_PROMPT.format(
        area_hectares=area_hectares,
        date=date,
        bbox=bbox
    )
    
    # Prepara as mensagens para a API
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{truecolor_b64}",
                        "detail": "high"
                    }
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{ndvi_b64}",
                        "detail": "high"
                    }
                }
            ]
        }
    ]
    
    # Faz a chamada para a API OpenAI
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o",
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.3
            },
            timeout=120  # 2 minutos timeout
        )
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


def encode_image_to_base64(image_bytes: bytes) -> str:
    """Converte bytes de imagem para string base64."""
    return base64.b64encode(image_bytes).decode('utf-8')