"""PlanSearch — Worker Tests.

Tests for background workers: ingest, classifier, scraper, CRO enrichment.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.workers.ingest import (
    parse_csv_row,
    merge_spatial_data,
    detect_year_from_ref,
)
from app.workers.classifier import (
    build_classification_prompt,
    parse_classification_response,
)
from app.workers.scraper import (
    should_run_scraper,
)


# ─── Ingest Worker Tests ────────────────────────────────────


def test_detect_year_from_ref():
    """Extract year from various REG_REF formats."""
    assert detect_year_from_ref("2345/24") == 2024
    assert detect_year_from_ref("FRL/2024/12345") == 2024
    assert detect_year_from_ref("1234/05") == 2005
    assert detect_year_from_ref("INVALID") is None


def test_parse_csv_row_basic():
    """Parse a basic CSV row into application fields."""
    row = {
        "APPLICATION_NUMBER": "1234/24",
        "APPLICATION_TYPE": "PERMISSION",
        "APPLICATION_DATE": "01/01/2024",
        "LOCATION_1": "123 Test Street, Dublin 2",
        "DESCRIPTION": "Single storey extension to rear",
        "DECISION": "GRANTED",
        "DECISION_DATE": "01/03/2024",
        "REGISTRATION_DATE": "15/01/2024",
    }

    result = parse_csv_row(row)
    assert result is not None
    assert result["reg_ref"] == "1234/24"
    assert result["app_type"] == "PERMISSION"
    assert result["location"] == "123 Test Street, Dublin 2"


def test_parse_csv_row_empty():
    """Parse handles empty/missing fields gracefully."""
    row = {
        "APPLICATION_NUMBER": "",
    }

    result = parse_csv_row(row)
    assert result is None


# ─── Classifier Tests ───────────────────────────────────────


def test_build_classification_prompt():
    """Build prompt includes proposal text."""
    prompt = build_classification_prompt(
        "Construction of 4-storey apartment block containing 24 residential units"
    )
    assert "apartment" in prompt.lower()
    assert "residential" in prompt.lower() or "category" in prompt.lower()


def test_parse_classification_valid():
    """Parse a valid classification response."""
    response = '{"category": "residential_new_build", "subcategory": "apartments", "confidence": 0.95}'
    result = parse_classification_response(response)
    assert result is not None
    assert result["category"] == "residential_new_build"
    assert result["confidence"] == 0.95


def test_parse_classification_invalid():
    """Parse handles invalid JSON gracefully."""
    result = parse_classification_response("this is not json")
    assert result is None


def test_parse_classification_missing_category():
    """Parse handles missing category field."""
    response = '{"subcategory": "test", "confidence": 0.5}'
    result = parse_classification_response(response)
    assert result is None


# ─── Scraper Tests ──────────────────────────────────────────


def test_scraper_off_peak_hours():
    """Scraper should only run during off-peak hours (8pm-8am)."""
    # 2am — should run
    assert should_run_scraper(hour=2) is True

    # 12pm — should NOT run
    assert should_run_scraper(hour=12) is False

    # 8pm — edge case, should run
    assert should_run_scraper(hour=20) is True

    # 7am — should run
    assert should_run_scraper(hour=7) is True

    # 10am — should NOT run
    assert should_run_scraper(hour=10) is False
