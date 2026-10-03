import httpx
import pytest

from app.providers.anthropic_provider import AnthropicProvider
from app.providers.openai_provider import OpenAIProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_cls", [OpenAIProvider, AnthropicProvider])
async def test_injected_client_reused_and_not_closed(provider_cls):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "content": [{"type": "text", "text": "{}"}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = provider_cls(api_key="test", http_client=client)
        for _ in range(2):
            response = await provider.complete("Extract JSON")
            assert response.content == "{}"
            assert not client.is_closed
    assert len(calls) == 2
