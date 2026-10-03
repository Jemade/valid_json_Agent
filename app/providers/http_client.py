"""Reuse injected connection pools while retaining standalone provider support."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx


@asynccontextmanager
async def provider_client(client: httpx.AsyncClient | None, timeout: float) -> AsyncIterator[httpx.AsyncClient]:
    if client is not None:
        yield client
    else:
        async with httpx.AsyncClient(timeout=timeout) as owned_client:
            yield owned_client
