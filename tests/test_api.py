import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.providers.mock_provider import MockProvider


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
