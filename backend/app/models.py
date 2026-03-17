"""PlanSearch — SQLAlchemy ORM models.

Maps to the PostgreSQL schema defined in scripts/init_schema.sql.
"""

from datetime import date, datetime
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    BigInteger,
    func,
    Computed,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import relationship

from app.database import Base


class Application(Base):
    """Core planning application record."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_ref = Column(String(20), unique=True, nullable=False, index=True)
    year = Column(Integer, Computed("EXTRACT(YEAR FROM apn_date)::INTEGER", persisted=True))

    apn_date = Column(Date)
    rgn_date = Column(Date)
    dec_date = Column(Date)
    final_grant_date = Column(Date)
    time_exp = Column(Date)

    proposal = Column(Text)
    long_proposal = Column(Text)
    location = Column(Text)
    app_type = Column(String(20))
    stage = Column(String(100))
    decision = Column(String(50))

    # AI Classification
    dev_category = Column(String(50))
    dev_subcategory = Column(String(100))
    classification_confidence = Column(Float)
    classified_at = Column(DateTime(timezone=True))

    # Applicant (portal scraper)
    applicant_name = Column(Text)
    applicant_scraped_at = Column(DateTime(timezone=True))
    applicant_scrape_failed = Column(Boolean, default=False)

    # CRO enrichment
    cro_number = Column(String(20))
    cro_enriched_at = Column(DateTime(timezone=True))

    # Spatial
    location_point = Column(Geometry("POINT", srid=4326))
    itm_easting = Column(Float)
    itm_northing = Column(Float)

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
    reg_ref = Column(String(20), ForeignKey("applications.reg_ref", ondelete="CASCADE"))
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
    reg_ref = Column(String(20), ForeignKey("applications.reg_ref", ondelete="CASCADE"))
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
    reg_ref = Column(String(20))
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
    reg_ref = Column(String(20), ForeignKey("applications.reg_ref", ondelete="CASCADE"))
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

    reg_ref = Column(String(20), ForeignKey("applications.reg_ref"), primary_key=True)
    portal_source = Column(String(20))
    scrape_status = Column(String(20), default="pending")
    doc_count = Column(Integer, default=0)
    last_scraped = Column(DateTime(timezone=True))
    error_message = Column(Text)
