import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.providers.mock_provider import MockProvider


@pytest.fixture(autouse=True)
async def api_lifespan():
    async with app.router.lifespan_context(app):
        yield


@pytest.mark.asyncio
async def test_api_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_api_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        data = res.json()
        assert "total_requests" in data
        assert "successful_validations" in data
        assert "average_retries" in data


@pytest.mark.asyncio
async def test_api_extract_success(sample_invoice_text, valid_invoice_json, monkeypatch):
    mock = MockProvider(responses=[valid_invoice_json])
    monkeypatch.setattr("app.main.get_provider", lambda *args, **kwargs: mock)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/v1/extract",
            json={
                "document_text": sample_invoice_text,
                "provider": "mock",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["attempts"] == 1
        assert "request_id" in data
        assert data["data"]["invoice_number"] == "INV-2024-8841"
        assert data["data"]["total"] == 2976.88


@pytest.mark.asyncio
async def test_api_extract_exhausted_retries_returns_422(sample_invoice_text, monkeypatch):
    bad_output = '{"invalid": "data"}'
    mock = MockProvider(responses=[bad_output, bad_output, bad_output])
    monkeypatch.setattr("app.main.get_provider", lambda *args, **kwargs: mock)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/v1/extract",
            json={
                "document_text": sample_invoice_text,
                "provider": "mock",
                "max_retries": 3,
            },
        )
        assert res.status_code == 422
        data = res.json()
        assert data["error_type"] == "StructuredOutputError"
        assert data["attempts"] == 3
        assert "request_id" in data
        assert "details" in data


@pytest.mark.asyncio
async def test_api_extract_unsupported_provider(sample_invoice_text):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/v1/extract",
            json={
                "document_text": sample_invoice_text,
                "provider": "unsupported_provider",
            },
        )
        assert res.status_code == 400
        assert "Unsupported provider" in res.json()["detail"]


@pytest.mark.asyncio
async def test_overload_returns_503_without_provider_call(sample_invoice_text, monkeypatch):
    import asyncio

    from app.config import settings

    monkeypatch.setattr(settings, "admission_timeout_seconds", 0.01)
    app.state.extraction_slots = asyncio.Semaphore(1)
    await app.state.extraction_slots.acquire()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/v1/extract", json={"document_text": sample_invoice_text})
    assert res.status_code == 503
    assert res.headers["retry-after"] == "1"
    assert app.state.extraction_slots.locked()
    app.state.extraction_slots.release()


@pytest.mark.asyncio
async def test_deadline_releases_capacity(sample_invoice_text, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock

    from app.config import settings

    async def slow_completion(**kwargs):
        await asyncio.Event().wait()

    provider = MockProvider()
    provider.complete = AsyncMock(side_effect=slow_completion)
    monkeypatch.setattr("app.main.get_provider", lambda *args, **kwargs: provider)
    monkeypatch.setattr(settings, "extraction_timeout_seconds", 0.01)
    app.state.extraction_slots = asyncio.Semaphore(1)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/v1/extract", json={"document_text": sample_invoice_text})
    assert res.status_code == 504
    assert res.json()["error_type"] == "ExtractionTimeoutError"
    assert not app.state.extraction_slots.locked()


@pytest.mark.asyncio
async def test_document_size_limit():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/v1/extract", json={"document_text": "x" * 100_001})
    assert res.status_code == 422
