"""PlanSearch Phase 2 — Unit Tests.

Tests for NPAD ingest, BCMS ingest, lifecycle computation,
value estimation, significance scoring, and digest generation.

All tests use mock objects and avoid importing modules that require
a live database connection.
"""

import sys
import types
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch


# ── Setup mock database module before any app imports ──────────────────
# This prevents SQLAlchemy from trying to connect to PostgreSQL

mock_database = types.ModuleType("app.database")
mock_database.Base = MagicMock()
mock_database.get_db = MagicMock()
sys.modules.setdefault("app.database", mock_database)


# ── NPAD Ingest Tests ──────────────────────────────────────────────────

from app.workers.npad_ingest import (
    normalise_ref,
    epoch_to_date,
    map_npad_feature,
)


def test_normalise_ref_basic():
    assert normalise_ref("FRL/2023/12345") == "FRL/2023/12345"


def test_normalise_ref_strips_whitespace():
    assert normalise_ref("  23/1234  ") == "23/1234"


def test_normalise_ref_uppercase():
    assert normalise_ref("d23a/1234") == "D23A/1234"


def test_normalise_ref_removes_internal_spaces():
    assert normalise_ref("FRL / 2023 / 12345") == "FRL/2023/12345"


def test_normalise_ref_none():
    assert normalise_ref(None) is None


def test_normalise_ref_empty():
    assert normalise_ref("") is None


def test_epoch_to_date_valid():
    # 2023-01-15 00:00:00 UTC
    epoch_ms = 1673740800000
    result = epoch_to_date(epoch_ms)
    assert result == date(2023, 1, 15)


def test_epoch_to_date_none():
    assert epoch_to_date(None) is None


def test_epoch_to_date_zero():
    assert epoch_to_date(0) is None


def test_map_npad_feature_full():
    feature = {
        "attributes": {
            "OBJECTID": 12345,
            "ApplicationNumber": "DCC/2023/0001",
            "PlanningAuthority": "Dublin City Council",
            "DevelopmentDescription": "New 50-unit apartment block",
            "DevelopmentAddress": "123 O'Connell Street, Dublin 1",
            "DevelopmentPostcode": "D01 X2Y3",
            "ApplicationType": "Permission",
            "ApplicationStatus": "Decision Made",
            "Decision": "GRANTED",
            "LandUseCode": "Residential",
            "AreaofSite": 2500.0,
            "NumResidentialUnits": 50,
            "FloorArea": 4200.0,
            "OneOffHouse": False,
            "ApplicantForename": "John",
            "ApplicantSurname": "Murphy",
            "ApplicantAddress": "1 Main Street, Dublin",
            "LinkAppDetails": "https://planning.agileapplications.ie/...",
            "ReceivedDate": 1673740800000,
            "ITMEasting": 315000.0,
            "ITMNorthing": 234000.0,
        },
        "geometry": {"x": -6.26, "y": 53.35},
    }

    mapped = map_npad_feature(feature)
    assert mapped["reg_ref"] == "DCC/2023/0001"
    assert mapped["planning_authority"] == "Dublin City Council"
    assert mapped["num_residential_units"] == 50
    assert mapped["floor_area"] == 4200.0
    assert mapped["applicant_name"] == "John Murphy"
    assert mapped["data_source"] == "npad_arcgis"
    assert mapped["npad_object_id"] == 12345


def test_map_npad_feature_empty_applicant():
    feature = {
        "attributes": {
            "ApplicationNumber": "TEST/001",
            "ApplicantForename": "",
            "ApplicantSurname": "",
        },
        "geometry": {},
    }
    mapped = map_npad_feature(feature)
    assert mapped["applicant_name"] is None
    assert mapped["applicant_forename"] is None


# ── BCMS Ingest Tests ──────────────────────────────────────────────────

from app.workers.bcms_ingest import (
    normalise_ref as bcms_normalise_ref,
    parse_date,
    safe_float,
    safe_int,
    safe_bool,
)


def test_bcms_parse_date_iso():
    assert parse_date("2024-03-15") == date(2024, 3, 15)


def test_bcms_parse_date_slash():
    assert parse_date("15/03/2024") == date(2024, 3, 15)


def test_bcms_parse_date_none():
    assert parse_date(None) is None


def test_bcms_parse_date_empty():
    assert parse_date("") is None


def test_safe_float_valid():
    assert safe_float("1234.5") == 1234.5


def test_safe_float_none():
    assert safe_float(None) is None


def test_safe_float_invalid():
    assert safe_float("not a number") is None


def test_safe_int_valid():
    assert safe_int("42") == 42


def test_safe_int_float():
    assert safe_int("42.9") == 42


def test_safe_int_none():
    assert safe_int(None) is None


def test_safe_bool_true():
    assert safe_bool("True") is True
    assert safe_bool("yes") is True
    assert safe_bool("1") is True


def test_safe_bool_false():
    assert safe_bool("False") is False
    assert safe_bool("no") is False
    assert safe_bool("0") is False


def test_safe_bool_none():
    assert safe_bool(None) is None


# ── Lifecycle Computation Tests ────────────────────────────────────────

from app.workers.lifecycle import compute_lifecycle_stage


class MockApp:
    """Mock Application for lifecycle testing."""

    def __init__(self, **kwargs):
        defaults = {
            "apn_date": None,
            "rgn_date": None,
            "dec_date": None,
            "decision": None,
            "time_exp": None,
            "fi_request_date": None,
            "appeal_ref_number": None,
            "appeal_decision": None,
            "appeal_decision_date": None,
        }
        for k, v in {**defaults, **kwargs}.items():
            setattr(self, k, v)


def test_lifecycle_submitted():
    app = MockApp(apn_date=date(2024, 1, 1))
    assert compute_lifecycle_stage(app) == "submitted"


def test_lifecycle_registered():
    app = MockApp(apn_date=date(2024, 1, 1), rgn_date=date(2024, 1, 8))
    assert compute_lifecycle_stage(app) == "registered"


def test_lifecycle_further_info():
    app = MockApp(
        rgn_date=date(2024, 1, 8),
        fi_request_date=date(2024, 2, 1),
    )
    assert compute_lifecycle_stage(app) == "further_info"


def test_lifecycle_granted():
    app = MockApp(
        rgn_date=date(2024, 1, 8),
        dec_date=date(2024, 3, 15),
        decision="GRANTED",
        time_exp=date(2029, 3, 15),
    )
    assert compute_lifecycle_stage(app) == "decided_granted"


def test_lifecycle_refused():
    app = MockApp(
        rgn_date=date(2024, 1, 8),
        dec_date=date(2024, 3, 15),
        decision="REFUSED",
    )
    assert compute_lifecycle_stage(app) == "decided_refused"


def test_lifecycle_expired():
    app = MockApp(
        rgn_date=date(2024, 1, 8),
        dec_date=date(2024, 3, 15),
        decision="GRANTED",
        time_exp=date(2020, 3, 15),  # Expired in the past
    )
    assert compute_lifecycle_stage(app) == "expired"


def test_lifecycle_appealed():
    app = MockApp(
        dec_date=date(2024, 3, 15),
        decision="REFUSED",
        appeal_ref_number="ABP-123",
    )
    assert compute_lifecycle_stage(app) == "appealed"


def test_lifecycle_appeal_granted():
    app = MockApp(
        dec_date=date(2024, 3, 15),
        decision="REFUSED",
        appeal_ref_number="ABP-123",
        appeal_decision="GRANTED BY ABP",
        appeal_decision_date=date(2024, 9, 1),
    )
    assert compute_lifecycle_stage(app) == "appeal_granted"


def test_lifecycle_fsc_filed():
    app = MockApp(
        dec_date=date(2024, 3, 15),
        decision="GRANTED",
    )
    assert compute_lifecycle_stage(app, fsc_submission_date=date(2024, 6, 1)) == "fsc_filed"


def test_lifecycle_under_construction():
    app = MockApp(
        dec_date=date(2024, 3, 15),
        decision="GRANTED",
    )
    assert compute_lifecycle_stage(app, cn_commencement_date=date(2024, 9, 1)) == "under_construction"


def test_lifecycle_complete():
    app = MockApp(
        dec_date=date(2024, 3, 15),
        decision="GRANTED",
    )
    assert compute_lifecycle_stage(
        app,
        cn_commencement_date=date(2024, 9, 1),
        ccc_date_validated=date(2025, 6, 1),
    ) == "complete"


# ── Value Estimation Tests ─────────────────────────────────────────────

from app.workers.value_estimator import (
    should_estimate_value,
    compute_significance_score,
)


class MockAppValue:
    """Mock Application for value testing."""

    def __init__(self, **kwargs):
        defaults = {
            "floor_area": None,
            "num_residential_units": None,
            "proposal": None,
            "value_estimated_at": None,
            "est_value_high": None,
            "dev_category": None,
            "decision": None,
            "one_off_house": None,
        }
        for k, v in {**defaults, **kwargs}.items():
            setattr(self, k, v)


def test_should_estimate_floor_area():
    app = MockAppValue(floor_area=500.0)
    assert should_estimate_value(app) is True


def test_should_estimate_units():
    app = MockAppValue(num_residential_units=10)
    assert should_estimate_value(app) is True


def test_should_estimate_long_description():
    app = MockAppValue(proposal="Construction of a new two-storey dwelling with garage and access road")
    assert should_estimate_value(app) is True


def test_should_not_estimate_already_done():
    app = MockAppValue(floor_area=500.0, value_estimated_at=datetime.utcnow())
    assert should_estimate_value(app) is False


def test_should_not_estimate_insufficient():
    app = MockAppValue(proposal="Fence")
    assert should_estimate_value(app) is False


def test_significance_score_high_value():
    app = MockAppValue(
        est_value_high=60_000_000,
        num_residential_units=200,
        dev_category="residential_new_build",
        decision="GRANTED",
        one_off_house=False,
    )
    score = compute_significance_score(app)
    assert score >= 80  # Should be highly significant


def test_significance_score_small_project():
    app = MockAppValue(
        est_value_high=100_000,
        num_residential_units=0,
        dev_category="residential_extension",
        decision="GRANTED",
        one_off_house=True,
    )
    score = compute_significance_score(app)
    assert score < 50  # Not significant


def test_significance_score_hotel():
    app = MockAppValue(
        est_value_high=25_000_000,
        dev_category="hotel_accommodation",
        decision="GRANTED",
        one_off_house=False,
    )
    score = compute_significance_score(app)
    assert score >= 50  # Should be significant


def test_significance_score_zero():
    app = MockAppValue()
    score = compute_significance_score(app)
    assert score >= 0
    assert score <= 100


# ── Digest Tests ───────────────────────────────────────────────────────

from app.workers.digest import generate_rss_xml


def test_rss_xml_generation():
    digest_data = {
        "entries": [
            {
                "reg_ref": "DCC/2024/001",
                "planning_authority": "Dublin City Council",
                "proposal": "New 50-unit apartment block",
                "location": "123 Main Street, Dublin 1",
                "applicant": "Murphy Developments Ltd",
                "est_value_str": "€15m – €20m",
                "est_value_high": 20_000_000,
                "link_app_details": "https://example.ie/plan/001",
            }
        ]
    }

    xml = generate_rss_xml(digest_data, date(2026, 3, 10))
    assert "PlanSearch" in xml
    assert "DCC/2024/001" in xml
    assert "Murphy Developments" in xml
    assert "rss" in xml


def test_rss_xml_empty():
    xml = generate_rss_xml({"entries": []}, date(2026, 3, 10))
    assert "PlanSearch" in xml
    assert "rss" in xml


# ── Format Value Tests ─────────────────────────────────────────────────

def test_format_value():
    """Test the formatValue equivalent logic."""
    def format_value(v):
        if not v:
            return "—"
        if v >= 1_000_000:
            return f"€{v / 1_000_000:.1f}m"
        if v >= 1_000:
            return f"€{v / 1_000:.0f}k"
        return f"€{v}"

    assert format_value(50_000_000) == "€50.0m"
    assert format_value(2_500_000) == "€2.5m"
    assert format_value(750_000) == "€750k"
    assert format_value(500) == "€500"
    assert format_value(None) == "—"
    assert format_value(0) == "—"
