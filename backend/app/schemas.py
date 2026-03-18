"""PlanSearch — Pydantic request/response schemas."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Constants ───────────────────────────────────────────────────────────

CATEGORY_LABELS = {
    "residential_new_build": "New Residential",
    "residential_extension": "Extension / Renovation",
    "residential_conversion": "Residential Conversion",
    "hotel_accommodation": "Hotel & Accommodation",
    "commercial_retail": "Retail & Food",
    "commercial_office": "Office",
    "industrial_warehouse": "Industrial / Warehouse",
    "mixed_use": "Mixed Use",
    "protected_structure": "Protected Structure",
    "telecommunications": "Telecoms",
    "renewable_energy": "Renewable Energy",
    "signage": "Signage",
    "change_of_use": "Change of Use",
    "demolition": "Demolition",
    "other": "Other",
}


# ── Search ──────────────────────────────────────────────────────────────

class SearchParams(BaseModel):
    """Query parameters for the search endpoint."""
    q: Optional[str] = None
    category: Optional[str] = None
    decision: Optional[str] = None
    applicant: Optional[str] = None
    location: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_m: Optional[int] = None
    sort: str = "date_desc"
    page: int = 1
    page_size: int = 25


class ApplicationSummary(BaseModel):
    """Compact application for search results."""
    id: int
    reg_ref: str
    apn_date: Optional[date] = None
    proposal: Optional[str] = None
    location: Optional[str] = None
    decision: Optional[str] = None
    dev_category: Optional[str] = None
    dev_subcategory: Optional[str] = None
    applicant_name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    relevance_score: Optional[float] = None
    # Phase 2 national fields
    planning_authority: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    est_value_low: Optional[int] = None
    est_value_high: Optional[int] = None
    significance_score: Optional[int] = None
    num_residential_units: Optional[int] = None
    floor_area: Optional[float] = None

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Paginated search results."""
    results: List[ApplicationSummary]
    total: int
    page: int
    page_size: int
    total_pages: int
    query_time_ms: Optional[float] = None
    inferred_location: Optional[str] = None


# ── Application Detail ──────────────────────────────────────────────────

class AppealDetail(BaseModel):
    """Appeal record."""
    id: int
    appeal_ref: Optional[str] = None
    appeal_date: Optional[date] = None
    appellant: Optional[str] = None
    appeal_decision: Optional[str] = None
    appeal_dec_date: Optional[date] = None

    class Config:
        from_attributes = True


class FurtherInfoDetail(BaseModel):
    """Further information record."""
    id: int
    fi_date: Optional[date] = None
    fi_type: Optional[str] = None
    fi_response_date: Optional[date] = None

    class Config:
        from_attributes = True


class CompanyDetail(BaseModel):
    """CRO company information."""
    cro_number: str
    company_name: str
    company_status: Optional[str] = None
    registered_address: Optional[str] = None
    incorporation_date: Optional[date] = None
    company_type: Optional[str] = None
    directors: Optional[list] = None

    class Config:
        from_attributes = True


class DocumentDetail(BaseModel):
    """Document metadata."""
    id: int
    doc_name: str
    doc_type: Optional[str] = None
    file_extension: Optional[str] = None
    file_size_bytes: Optional[int] = None
    portal_source: Optional[str] = None
    direct_url: Optional[str] = None
    portal_url: Optional[str] = None
    uploaded_date: Optional[date] = None
    doc_category: Optional[str] = None

    class Config:
        from_attributes = True


class ApplicationDetail(BaseModel):
    """Full application detail with related records."""
    id: int
    reg_ref: str
    year: Optional[int] = None
    apn_date: Optional[date] = None
    rgn_date: Optional[date] = None
    dec_date: Optional[date] = None
    final_grant_date: Optional[date] = None
    time_exp: Optional[date] = None
    proposal: Optional[str] = None
    long_proposal: Optional[str] = None
    proposal_summary: Optional[str] = None
    location: Optional[str] = None
    app_type: Optional[str] = None
    stage: Optional[str] = None
    decision: Optional[str] = None
    dev_category: Optional[str] = None
    dev_subcategory: Optional[str] = None
    classification_confidence: Optional[float] = None
    applicant_name: Optional[str] = None
    cro_number: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    portal_url: Optional[str] = None

    appeals: List[AppealDetail] = []
    further_info: List[FurtherInfoDetail] = []
    company: Optional[CompanyDetail] = None
    documents: List[DocumentDetail] = []

    class Config:
        from_attributes = True


# ── Map ─────────────────────────────────────────────────────────────────

class MapPoint(BaseModel):
    """GeoJSON-compatible map point."""
    reg_ref: str
    lat: float
    lng: float
    decision: Optional[str] = None
    dev_category: Optional[str] = None
    proposal: Optional[str] = None
    location: Optional[str] = None


class MapResponse(BaseModel):
    """Map points for the map view."""
    type: str = "FeatureCollection"
    features: List[dict]
    total: int


# ── Stats ───────────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    """Platform statistics."""
    total_applications: int
    total_classified: int
    total_applicants_scraped: int
    total_cro_enriched: int
    total_documents: int
    categories: dict
    decisions: dict
    years: dict
    last_sync: Optional[datetime] = None


# ── Admin ───────────────────────────────────────────────────────────────

class AdminConfigItem(BaseModel):
    """Admin configuration key-value pair (value masked for display)."""
    key: str
    value_masked: str
    encrypted: bool
    description: Optional[str] = None
    updated_at: Optional[datetime] = None


class AdminConfigUpdate(BaseModel):
    """Update an admin config value."""
    key: str
    value: str
    encrypted: bool = False
    description: Optional[str] = None


class SyncLogEntry(BaseModel):
    """Sync log entry."""
    id: int
    sync_type: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    records_processed: Optional[int] = None
    records_new: Optional[int] = None
    records_updated: Optional[int] = None
    error_message: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


class SyncTriggerResponse(BaseModel):
    """Response when a sync is triggered."""
    message: str
    sync_id: int


class ClassifyStatusResponse(BaseModel):
    """Classification queue status."""
    total_unclassified: int
    total_classified: int
    total_applications: int
    percentage_classified: float
    categories: dict


class ScrapeStatusResponse(BaseModel):
    """Scraper queue status."""
    total_unscraped: int
    total_scraped: int
    total_failed: int
    total_applications: int
    percentage_scraped: float
