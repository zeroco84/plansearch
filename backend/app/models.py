"""PlanSearch — SQLAlchemy ORM models.

Maps to the PostgreSQL schema defined in scripts/init_schema.sql.
"""

from datetime import date, datetime
from typing import Optional
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    BigInteger,
    func,
    Computed,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, ARRAY, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Application(Base):
    """Core planning application record."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_ref = Column(String(100), unique=True, nullable=False, index=True)
    year = Column(Integer, Computed("EXTRACT(YEAR FROM apn_date)::INTEGER", persisted=True))

    apn_date = Column(Date)
    rgn_date = Column(Date)
    dec_date = Column(Date)
    final_grant_date = Column(Date)
    time_exp = Column(Date)

    proposal = Column(Text)
    long_proposal = Column(Text)
    proposal_summary = Column(Text)          # AI-generated clean summary
    proposal_summarised_at = Column(DateTime)
    location = Column(Text)
    app_type = Column(String(100))
    stage = Column(String(100))
    decision = Column(String(100))

    # AI Classification
    dev_category = Column(String(50))
    dev_subcategory = Column(String(100))
    classification_confidence = Column(Float)
    classified_at = Column(DateTime(timezone=True))

    # Applicant (portal scraper / NPAD)
    applicant_name = Column(Text)
    applicant_forename = Column(String(100))
    applicant_surname = Column(String(100))
    applicant_address = Column(Text)
    applicant_scraped_at = Column(DateTime(timezone=True))
    applicant_scrape_failed = Column(Boolean, default=False)

    # CRO enrichment
    cro_number = Column(String(50))
    cro_enriched_at = Column(DateTime(timezone=True))

    # National data (NPAD fields — Phase 2)
    planning_authority = Column(String(100))
    land_use_code = Column(String(100))
    area_of_site = Column(Float)
    num_residential_units = Column(Integer)
    floor_area = Column(Float)
    one_off_house = Column(Boolean)
    link_app_details = Column(Text)
    npad_object_id = Column(Integer)
    data_source = Column(String(50), default="dcc_csv")
    eircode = Column(String(10))

    # NPAD appeal fields
    appeal_ref_number = Column(String(100))
    appeal_status = Column(String(100))
    appeal_decision = Column(String(100))
    appeal_decision_date = Column(Date)
    fi_request_date = Column(Date)
    fi_rec_date = Column(Date)

    # Lifecycle stage (Phase 2)
    lifecycle_stage = Column(String(50))
    lifecycle_updated_at = Column(DateTime(timezone=True))

    # AI value estimation (Phase 2)
    est_value_low = Column(BigInteger)
    est_value_high = Column(BigInteger)
    est_value_basis = Column(Text)
    est_value_type = Column(String(100))
    est_value_confidence = Column(String(10))
    value_estimated_at = Column(DateTime(timezone=True))

    # Significance scoring (Phase 2)
    significance_score = Column(Integer, default=0)

    # Professional identification (Phase 2)
    planning_agent_name = Column(Text)
    planning_agent_company = Column(Text)
    architect_name = Column(Text)
    architect_company = Column(Text)

    # Spatial
    location_point = Column(Geometry("POINT", srid=4326))
    itm_easting = Column(Float)
    itm_northing = Column(Float)
    geocoded_at = Column(DateTime(timezone=True))

    # Full-text search
    search_vector = Column(TSVECTOR)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    raw_data = Column(JSONB)

    # Relationships
    appeals = relationship("Appeal", back_populates="application", cascade="all, delete-orphan")
    further_info_items = relationship("FurtherInfo", back_populates="application", cascade="all, delete-orphan")
    documents = relationship("ApplicationDocument", back_populates="application", cascade="all, delete-orphan")
    company_links = relationship("ApplicationCompany", back_populates="application", cascade="all, delete-orphan")


class Appeal(Base):
    """Appeal record linked to an application."""

    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_ref = Column(String(100), ForeignKey("applications.reg_ref", ondelete="CASCADE"))
    appeal_ref = Column(String(30))
    appeal_date = Column(Date)
    appellant = Column(Text)
    appeal_decision = Column(String(50))
    appeal_dec_date = Column(Date)
    raw_data = Column(JSONB)

    application = relationship("Application", back_populates="appeals")


class FurtherInfo(Base):
    """Further information request record."""

    __tablename__ = "further_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_ref = Column(String(100), ForeignKey("applications.reg_ref", ondelete="CASCADE"))
    fi_date = Column(Date)
    fi_type = Column(String(50))
    fi_response_date = Column(Date)
    raw_data = Column(JSONB)

    application = relationship("Application", back_populates="further_info_items")


class Company(Base):
    """CRO company data."""

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cro_number = Column(String(20), unique=True, nullable=False)
    company_name = Column(Text, nullable=False)
    company_status = Column(String(50))
    registered_address = Column(Text)
    incorporation_date = Column(Date)
    company_type = Column(String(100))
    directors = Column(JSONB)
    raw_cro_data = Column(JSONB)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    application_links = relationship("ApplicationCompany", back_populates="company", cascade="all, delete-orphan")


class ApplicationCompany(Base):
    """Many-to-many link between applications and companies."""

    __tablename__ = "application_companies"

    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    match_confidence = Column(Float)

    application = relationship("Application", back_populates="company_links")
    company = relationship("Company", back_populates="application_links")


class AdminConfig(Base):
    """Admin configuration store for encrypted API keys."""

    __tablename__ = "admin_config"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    encrypted = Column(Boolean, default=False)
    description = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ScrapeJob(Base):
    """Tracks individual scraping jobs."""

    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(50), nullable=False)
    reg_ref = Column(String(100))
    status = Column(String(20), default="pending")
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    scheduled_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class SyncLog(Base):
    """Logs for data synchronisation runs."""

    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String(50))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    records_processed = Column(Integer)
    records_new = Column(Integer)
    records_updated = Column(Integer)
    error_message = Column(Text)
    status = Column(String(20), default="running")


class ApplicationDocument(Base):
    """Document metadata for planning application documents."""

    __tablename__ = "application_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_ref = Column(String(100), ForeignKey("applications.reg_ref", ondelete="CASCADE"))
    doc_name = Column(Text, nullable=False)
    doc_type = Column(String(100))
    file_extension = Column(String(10))
    file_size_bytes = Column(BigInteger)
    portal_source = Column(String(20))
    direct_url = Column(Text)
    portal_url = Column(Text)
    internal_doc_id = Column(String(100))
    archived = Column(Boolean, default=False)
    archived_path = Column(Text)
    archived_at = Column(DateTime(timezone=True))
    content_text = Column(Text)
    content_vector = Column(TSVECTOR)
    content_extracted_at = Column(DateTime(timezone=True))
    uploaded_date = Column(Date)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    doc_category = Column(String(50))

    application = relationship("Application", back_populates="documents")


class DocumentScrapeStatus(Base):
    """Tracks document scraping status per application."""

    __tablename__ = "document_scrape_status"

    reg_ref = Column(String(100), ForeignKey("applications.reg_ref"), primary_key=True)
    portal_source = Column(String(20))
    scrape_status = Column(String(20), default="pending")
    doc_count = Column(Integer, default=0)
    last_scraped = Column(DateTime(timezone=True))
    error_message = Column(Text)


class CommencementNotice(Base):
    """BCMS Commencement Notice + Certificate of Compliance on Completion."""

    __tablename__ = "commencement_notices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_ref = Column(String(100), unique=True, index=True, nullable=False)
    local_authority = Column(String(100))

    # Commencement
    cn_commencement_date = Column(Date)
    cn_proposed_end_date = Column(Date)
    cn_project_status = Column(String(50))
    cn_date_granted = Column(Date)
    cn_date_expiry = Column(Date)
    cn_description = Column(Text)
    cn_proposed_use_desc = Column(Text)

    # Building characteristics
    cn_total_floor_area = Column(Float)
    cn_total_dwelling_units = Column(Integer)
    cn_total_apartments = Column(Integer)
    cn_number_stories_above = Column(Integer)
    cn_number_bedrooms = Column(Integer)
    cn_protected_structure = Column(Boolean)
    cn_phase = Column(String(10))
    cn_units_for_phase = Column(Integer)
    cn_total_phases = Column(Integer)

    # Address
    cn_street = Column(Text)
    cn_town = Column(Text)
    cn_eircode = Column(String(10))
    cn_county = Column(String(50))
    cn_lat = Column(Float)
    cn_lng = Column(Float)
    location_point = Column(Geometry("POINT", srid=4326))

    # Completion
    ccc_date_validated = Column(Date)
    ccc_units_completed = Column(Integer)
    ccc_type = Column(String(100))

    # Metadata
    raw_data = Column(JSONB)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())


class FSCApplication(Base):
    """BCMS Fire Safety Certificate / Disability Access Certificate application."""

    __tablename__ = "fsc_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_ref = Column(String(100), unique=True, index=True, nullable=False)
    application_reference_no = Column(String(50))
    application_type = Column(String(20))
    local_authority = Column(String(100))
    submission_date = Column(Date)
    date_of_decision = Column(Date)
    decision_type = Column(String(50))

    # Building data
    floor_area_of_building = Column(Float)
    total_combined_floor_area = Column(Float)
    no_of_stories_above_ground = Column(Integer)
    site_area = Column(Float)
    use_of_proposed_works = Column(Text)
    main_construction_type = Column(String(100))

    # Construction status
    date_construction_started = Column(Date)
    is_construction_complete = Column(Boolean)
    date_of_completion = Column(Date)
    is_building_occupied = Column(Boolean)

    # Applicant
    applicant_name = Column(Text)
    applicant_address_line_1 = Column(Text)
    applicant_town = Column(Text)
    applicant_county = Column(String(50))

    # Location
    lat = Column(Float)
    longitude = Column(Float)
    eircode = Column(String(10))
    location_point = Column(Geometry("POINT", srid=4326))

    raw_data = Column(JSONB)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())


class CostBenchmark(Base):
    """Construction cost benchmarks extracted from Mitchell McDermott InfoCards.

    Source: https://mitchellmcdermott.com/infocards/
    """

    __tablename__ = "cost_benchmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), default="Mitchell McDermott")
    source_url = Column(Text, default="https://mitchellmcdermott.com/infocards/")
    infocard_name = Column(String(200))
    infocard_pdf_url = Column(Text)
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())
    valid_from = Column(Date)
    inflation_rate = Column(Float)

    # Building type key — matches dev_category values in applications table
    building_type = Column(String(100), index=True)

    # Cost ranges
    cost_per_sqm_low = Column(Integer)
    cost_per_sqm_high = Column(Integer)
    cost_per_unit_low = Column(Integer)
    cost_per_unit_high = Column(Integer)
    cost_basis = Column(String(50))  # "per_sqm" | "per_unit" | "both"

    # What's included and excluded
    inclusions = Column(ARRAY(String))
    exclusions = Column(ARRAY(String))
    notes = Column(Text)

    # Raw extracted data for audit
    raw_extracted_json = Column(JSONB)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())



class WeeklyDigest(Base):
    """Generated weekly significant approvals digest."""

    __tablename__ = "weekly_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    total_entries = Column(Integer, default=0)
    digest_data = Column(JSONB)
    published = Column(Boolean, default=False)


# ═════════════════════════════════════════════════════════════════
# Phase 3: The Build Integration + Advertising
# ═════════════════════════════════════════════════════════════════


class BuildPost(Base):
    """The Build newsletter post, ingested from Substack RSS."""

    __tablename__ = "build_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(200), unique=True, nullable=False)
    title = Column(Text, nullable=False)
    subtitle = Column(Text)
    excerpt = Column(Text)
    featured_image_url = Column(Text)
    substack_url = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True))

    # AI-generated metadata
    summary_one_line = Column(Text)
    topics = Column(ARRAY(Text))
    mentioned_councils = Column(ARRAY(Text))
    tone = Column(String(20))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    application_links = relationship(
        "PostApplicationLink", back_populates="post", cascade="all, delete-orphan"
    )


class PostApplicationLink(Base):
    """Link between a Build post and a planning application."""

    __tablename__ = "post_application_links"

    post_id = Column(Integer, ForeignKey("build_posts.id", ondelete="CASCADE"), primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True)
    link_type = Column(String(30))  # mentioned | related_location | related_topic
    confidence = Column(Float)

    post = relationship("BuildPost", back_populates="application_links")
    application = relationship("Application")


class Advertiser(Base):
    """Advertising client."""

    __tablename__ = "advertisers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(Text, nullable=False)
    contact_name = Column(Text)
    contact_email = Column(Text)
    industry = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaigns = relationship("AdCampaign", back_populates="advertiser", cascade="all, delete-orphan")


class AdCampaign(Base):
    """Ad campaign with contextual targeting and privacy-first analytics."""

    __tablename__ = "ad_campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"))
    campaign_name = Column(Text, nullable=False)
    campaign_type = Column(String(20))  # display | sponsored_content
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default="active")  # active | paused | ended

    # Creative
    headline = Column(String(60))
    body_text = Column(String(120))
    cta_text = Column(String(30))
    cta_url = Column(Text)
    logo_url = Column(Text)

    # Contextual targeting
    target_categories = Column(ARRAY(Text))
    target_councils = Column(ARRAY(Text))
    target_lifecycle = Column(ARRAY(Text))

    # Aggregate analytics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)

    # Financials
    agreed_price = Column(Numeric(10, 2))
    invoice_ref = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    advertiser = relationship("Advertiser", back_populates="campaigns")


class AdImpression(Base):
    """Aggregate impression log — no user data."""

    __tablename__ = "ad_impressions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("ad_campaigns.id"))
    page_path = Column(Text)
    clicked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ═════════════════════════════════════════════════════════════════
# Phase 4: User Accounts & Paid Alerts
# ═════════════════════════════════════════════════════════════════


class User(Base):
    """Registered user with Stripe subscription."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    # Subscription
    stripe_customer_id = Column(String(100), nullable=True, unique=True)
    stripe_subscription_id = Column(String(100), nullable=True)
    subscription_tier = Column(String(20), default="free")  # free, starter, professional, agency
    subscription_status = Column(String(20), default="inactive")  # active, inactive, cancelled, past_due
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Meta
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    email_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    alert_profiles = relationship("AlertProfile", back_populates="user", cascade="all, delete-orphan")
    alert_deliveries = relationship("AlertDelivery", back_populates="user")


class AlertProfile(Base):
    """User-defined alert filter profile."""

    __tablename__ = "alert_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Trigger events — which lifecycle events to watch
    trigger_events = Column(JSON, default=list)

    # Filters — combined with AND logic
    planning_authorities = Column(JSON, default=list)
    dev_categories = Column(JSON, default=list)
    value_min = Column(Integer, nullable=True)
    value_max = Column(Integer, nullable=True)
    keywords = Column(String(500), nullable=True)

    # Delivery preferences
    frequency = Column(String(20), default="daily")      # instant, daily, weekly
    email_format = Column(String(20), default="digest")   # digest, individual

    user = relationship("User", back_populates="alert_profiles")
    deliveries = relationship("AlertDelivery", back_populates="alert_profile")


class AlertDelivery(Base):
    """Record of a sent alert email."""

    __tablename__ = "alert_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    alert_profile_id = Column(UUID(as_uuid=True), ForeignKey("alert_profiles.id"), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    application_count = Column(Integer, default=0)
    email_subject = Column(String(500), nullable=True)
    status = Column(String(20), default="sent")  # sent, failed, bounced

    user = relationship("User", back_populates="alert_deliveries")
    alert_profile = relationship("AlertProfile", back_populates="deliveries")


class AlertMatch(Base):
    """Individual application match for an alert delivery."""

    __tablename__ = "alert_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("alert_deliveries.id"), nullable=False)
    reg_ref = Column(String(100), nullable=False)
    trigger_event = Column(String(50), nullable=False)
    matched_at = Column(DateTime(timezone=True), server_default=func.now())


# ═════════════════════════════════════════════════════════════════
# Phase 5: Public API — Keys, Usage, Webhooks
# ═════════════════════════════════════════════════════════════════


class ApiKey(Base):
    """API key for commercial public API access."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)  # "Production", "Dev"
    key_hash = Column(String(64), unique=True, nullable=False)  # SHA-256 of raw key
    key_prefix = Column(String(20), nullable=False)  # "psk_live_ab12" for display
    environment = Column(String(10), default="live")  # live or test
    tier = Column(String(20), nullable=False, default="developer")
    is_active = Column(Boolean, default=True)
    calls_this_month = Column(Integer, default=0)
    monthly_quota = Column(Integer, default=1000)
    rate_limit_per_minute = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))

    user = relationship("User", backref="api_keys")
    usage_records = relationship("ApiUsage", back_populates="api_key", cascade="all, delete-orphan")
    webhooks = relationship("Webhook", back_populates="api_key", cascade="all, delete-orphan")


class ApiUsage(Base):
    """Per-call usage log for API keys."""

    __tablename__ = "api_usage"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False)
    endpoint = Column(String(100))
    status_code = Column(Integer)
    response_time_ms = Column(Integer)
    called_at = Column(DateTime(timezone=True), server_default=func.now())

    api_key = relationship("ApiKey", back_populates="usage_records")


class Webhook(Base):
    """Customer webhook for real-time event notifications."""

    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False)
    url = Column(String(500), nullable=False)
    events = Column(JSONB, default=list)  # ["application.granted", ...]
    filters = Column(JSONB, default=dict)  # {authorities: [...], categories: [...], value_min: N}
    secret_encrypted = Column(Text, nullable=False)  # Fernet-encrypted raw secret
    is_active = Column(Boolean, default=True)
    failure_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_delivered_at = Column(DateTime(timezone=True))

    api_key = relationship("ApiKey", back_populates="webhooks")
    deliveries = relationship("WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    """Individual webhook delivery attempt record."""

    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(UUID(as_uuid=True), ForeignKey("webhooks.id"), nullable=False)
    event = Column(String(50), nullable=False)
    reg_ref = Column(String(100))
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), default="pending")  # pending/delivered/failed
    attempts = Column(Integer, default=0)
    http_status = Column(Integer)  # last HTTP response code
    delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    webhook = relationship("Webhook", back_populates="deliveries")
