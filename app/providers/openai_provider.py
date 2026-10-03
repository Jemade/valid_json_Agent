import time

import httpx

from app.agent.exceptions import ProviderError, ProviderTimeoutError
from app.providers.base import ProviderResponse
from app.providers.http_client import provider_client


class OpenAIProvider:
    """Adapter for OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.http_client = http_client
        self.provider_name = "openai"

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(
                message="OpenAI API key is not configured. Set OPENAI_API_KEY environment variable.",
                provider=self.provider_name,
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.perf_counter()
        try:
            async with provider_client(self.http_client, self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            choice = data["choices"][0]
            content = choice["message"]["content"]
            usage = data.get("usage", {})

            return ProviderResponse(
                content=content,
                model=self.model,
                provider_name=self.provider_name,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                latency_ms=latency_ms,
            )

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                message=f"OpenAI request timed out after {self.timeout}s",
                provider=self.provider_name,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                message=f"OpenAI API returned error status {exc.response.status_code}: {exc.response.text}",
                provider=self.provider_name,
                status_code=exc.response.status_code,
            ) from exc
        except Exception as exc:
            raise ProviderError(
                message=f"Unexpected error communicating with OpenAI: {str(exc)}",
                provider=self.provider_name,
            ) from exc
