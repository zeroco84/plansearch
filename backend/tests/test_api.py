"""PlanSearch — Backend Test Suite.

Comprehensive tests for API endpoints, workers, and utilities.
"""

import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from datetime import date, datetime
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import Application
from app.config import get_settings


# ─── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Health Check Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Health check endpoint returns 200."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


# ─── Search Endpoint Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_search_empty_query(client: AsyncClient):
    """Search with no query returns results."""
    response = await client.get("/api/search")
    # Should return 200 even with no results (empty DB)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.asyncio
async def test_search_with_query(client: AsyncClient):
    """Search with text query."""
    response = await client.get("/api/search", params={"q": "Dublin"})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


@pytest.mark.asyncio
async def test_search_with_category_filter(client: AsyncClient):
    """Search with category filter."""
    response = await client.get("/api/search", params={
        "category": "residential_new_build"
    })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_with_year_filter(client: AsyncClient):
    """Search with year range filter."""
    response = await client.get("/api/search", params={
        "year_from": 2020,
        "year_to": 2024,
    })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_pagination(client: AsyncClient):
    """Search with pagination params."""
    response = await client.get("/api/search", params={
        "page": 1,
        "page_size": 10,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_search_sort_options(client: AsyncClient):
    """Search with different sort options."""
    for sort in ["date_desc", "date_asc", "relevance"]:
        response = await client.get("/api/search", params={"sort": sort})
        assert response.status_code == 200


# ─── Application Detail Tests ───────────────────────────────


@pytest.mark.asyncio
async def test_application_not_found(client: AsyncClient):
    """Application detail for non-existent ref returns 404."""
    response = await client.get("/api/applications/NONEXISTENT/9999")
    assert response.status_code == 404


# ─── Map Endpoint Tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_map_points(client: AsyncClient):
    """Map points endpoint returns GeoJSON."""
    response = await client.get("/api/map/points")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data


@pytest.mark.asyncio
async def test_map_points_with_category(client: AsyncClient):
    """Map points with category filter."""
    response = await client.get("/api/map/points", params={
        "category": "commercial_retail"
    })
    assert response.status_code == 200


# ─── Stats Endpoint Tests ───────────────────────────────────


@pytest.mark.asyncio
async def test_stats(client: AsyncClient):
    """Stats endpoint returns platform statistics."""
    response = await client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_applications" in data


# ─── CSV Export Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_csv_export(client: AsyncClient):
    """CSV export returns correct content type."""
    response = await client.get("/api/export/csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "plansearch_export" in response.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_csv_export_with_filters(client: AsyncClient):
    """CSV export respects filter parameters."""
    response = await client.get("/api/export/csv", params={
        "category": "residential_new_build",
        "year_from": 2020,
    })
    assert response.status_code == 200


# ─── Admin Endpoint Tests ───────────────────────────────────


@pytest.mark.asyncio
async def test_admin_no_auth(client: AsyncClient):
    """Admin endpoints reject unauthenticated requests."""
    response = await client.get("/api/admin/sync/status")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_admin_wrong_token(client: AsyncClient):
    """Admin endpoints reject wrong token."""
    response = await client.get(
        "/api/admin/sync/status",
        headers={"Authorization": "Bearer wrong_token_12345"}
    )
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_admin_config_no_auth(client: AsyncClient):
    """Admin config endpoint rejects unauthenticated."""
    response = await client.get("/api/admin/config")
    assert response.status_code in [401, 403]


# ─── Utility Tests ──────────────────────────────────────────


def test_itm_to_wgs84():
    """ITM coordinate conversion produces Dublin-ish coordinates."""
    from app.utils.itm_to_wgs84 import itm_to_wgs84

    # Dublin City Hall approximate ITM coordinates
    lat, lng = itm_to_wgs84(715800, 734000)

    # Should be in Dublin area
    assert 53.0 < lat < 53.6, f"Latitude {lat} not in Dublin range"
    assert -6.5 < lng < -6.0, f"Longitude {lng} not in Dublin range"


def test_itm_to_wgs84_invalid():
    """ITM conversion handles invalid coordinates."""
    from app.utils.itm_to_wgs84 import itm_to_wgs84

    lat, lng = itm_to_wgs84(0, 0)
    # Should still return numbers, but not Dublin coords
    assert isinstance(lat, float)
    assert isinstance(lng, float)


def test_text_clean():
    """Text cleaning normalises whitespace and encoding."""
    from app.utils.text_clean import clean_text

    assert clean_text("  Hello   World  ") == "Hello World"
    assert clean_text(None) is None
    assert clean_text("") is None


def test_normalise_address():
    """Address normalisation works correctly."""
    from app.utils.text_clean import normalise_address

    result = normalise_address("123 O'Connell Street, Dublin 1")
    assert result is not None
    assert isinstance(result, str)


def test_crypto_round_trip():
    """Fernet encryption/decryption round-trip."""
    from app.utils.crypto import encrypt_value, decrypt_value

    original = "test-api-key-12345"

    encrypted = encrypt_value(original)
    assert encrypted != original

    decrypted = decrypt_value(encrypted)
    assert decrypted == original


def test_crypto_mask():
    """API key masking works correctly."""
    from app.utils.crypto import mask_key

    assert mask_key("sk-ant-1234567890") == "sk-ant-******7890"
    assert mask_key("ab") == "****"
    assert mask_key(None) == "****"


# ─── Model Tests ────────────────────────────────────────────


def test_category_labels():
    """All categories have display labels."""
    from app.schemas import CATEGORY_LABELS

    expected_categories = [
        "residential_new_build",
        "residential_extension",
        "residential_conversion",
        "hotel_accommodation",
        "commercial_retail",
        "commercial_office",
        "industrial_warehouse",
        "mixed_use",
        "protected_structure",
        "telecommunications",
        "renewable_energy",
        "signage",
        "change_of_use",
        "demolition",
        "other",
    ]

    for cat in expected_categories:
        assert cat in CATEGORY_LABELS, f"Missing label for category: {cat}"
