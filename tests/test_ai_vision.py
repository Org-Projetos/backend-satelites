import os

import httpx
import pytest
import respx


@respx.mock
@pytest.mark.asyncio
async def test_analyze_with_claude_vision_sends_anthropic_payload():
    os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"

    from app.config import get_settings
    from app.services.ai_vision import analyze_with_claude_vision

    get_settings.cache_clear()

    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": "Relatório gerado pelo Claude.",
                    }
                ]
            },
        )
    )

    result = await analyze_with_claude_vision(
        truecolor_b64="truecolor-base64",
        ndvi_b64="ndvi-base64",
        area_hectares=10.5,
        date="2026-05-11",
        bbox=[-47.0, -23.0, -46.5, -22.5],
    )

    assert result == "Relatório gerado pelo Claude."
    assert route.called

    request = route.calls.last.request
    assert request.headers["x-api-key"] == "test-anthropic-key"
    assert request.headers["anthropic-version"] == "2023-06-01"

    payload = request.content.decode("utf-8")
    assert '"model":"claude-sonnet-4-5"' in payload
    assert '"type":"image"' in payload
    assert '"media_type":"image/png"' in payload
    assert '"data":"truecolor-base64"' in payload
    assert '"data":"ndvi-base64"' in payload
