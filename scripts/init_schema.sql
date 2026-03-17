-- PlanSearch Database Schema
-- Version: 1.1 — March 2026

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- CORE APPLICATIONS TABLE
CREATE TABLE applications (
    id                   SERIAL PRIMARY KEY,
    reg_ref              VARCHAR(20) UNIQUE NOT NULL,
    year                 INTEGER GENERATED ALWAYS AS (
                             EXTRACT(YEAR FROM apn_date)::INTEGER
                         ) STORED,
    apn_date             DATE,
    rgn_date             DATE,
    dec_date             DATE,
    final_grant_date     DATE,
    time_exp             DATE,
    proposal             TEXT,
    long_proposal        TEXT,
    location             TEXT,
    app_type             VARCHAR(20),
    stage                VARCHAR(100),
    decision             VARCHAR(50),

    -- AI Classification (populated by background worker)
    dev_category         VARCHAR(50),
    dev_subcategory      VARCHAR(100),
    classification_confidence FLOAT,
    classified_at        TIMESTAMPTZ,

    -- Applicant (populated by portal scraper)
    applicant_name       TEXT,
    applicant_scraped_at TIMESTAMPTZ,
    applicant_scrape_failed BOOLEAN DEFAULT FALSE,

    -- CRO enrichment
    cro_number           VARCHAR(20),
    cro_enriched_at      TIMESTAMPTZ,

    -- Spatial
    location_point       GEOMETRY(Point, 4326),
    itm_easting          FLOAT,
    itm_northing         FLOAT,

    -- Full-text search vector (auto-updated by trigger)
    search_vector        TSVECTOR,

    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    raw_data             JSONB
);

-- APPEALS TABLE
CREATE TABLE appeals (
    id              SERIAL PRIMARY KEY,
    reg_ref         VARCHAR(20) REFERENCES applications(reg_ref) ON DELETE CASCADE,
    appeal_ref      VARCHAR(30),
    appeal_date     DATE,
    appellant       TEXT,
    appeal_decision VARCHAR(50),
    appeal_dec_date DATE,
    raw_data        JSONB
);

-- FURTHER INFORMATION TABLE
CREATE TABLE further_info (
    id               SERIAL PRIMARY KEY,
    reg_ref          VARCHAR(20) REFERENCES applications(reg_ref) ON DELETE CASCADE,
    fi_date          DATE,
    fi_type          VARCHAR(50),
    fi_response_date DATE,
    raw_data         JSONB
);

-- CRO COMPANY DATA
CREATE TABLE companies (
    id                 SERIAL PRIMARY KEY,
    cro_number         VARCHAR(20) UNIQUE NOT NULL,
    company_name       TEXT NOT NULL,
    company_status     VARCHAR(50),
    registered_address TEXT,
    incorporation_date DATE,
    company_type       VARCHAR(100),
    directors          JSONB,
    raw_cro_data       JSONB,
    fetched_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE application_companies (
    application_id  INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    company_id      INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    match_confidence FLOAT,
    PRIMARY KEY (application_id, company_id)
);

-- ADMIN CONFIG (API keys stored here, encrypted)
CREATE TABLE admin_config (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    encrypted   BOOLEAN DEFAULT FALSE,
    description TEXT,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- JOB TRACKING
CREATE TABLE scrape_jobs (
    id          SERIAL PRIMARY KEY,
    job_type    VARCHAR(50) NOT NULL,
    reg_ref     VARCHAR(20),
    status      VARCHAR(20) DEFAULT 'pending',
    attempts    INTEGER DEFAULT 0,
    last_error  TEXT,
    scheduled_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- SYNC LOG
CREATE TABLE sync_log (
    id                SERIAL PRIMARY KEY,
    sync_type         VARCHAR(50),
    started_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,
    records_processed INTEGER,
    records_new       INTEGER,
    records_updated   INTEGER,
    error_message     TEXT,
    status            VARCHAR(20) DEFAULT 'running'
);

-- DOCUMENT METADATA TABLE
CREATE TABLE application_documents (
    id              SERIAL PRIMARY KEY,
    reg_ref         VARCHAR(20) REFERENCES applications(reg_ref) ON DELETE CASCADE,
    doc_name        TEXT NOT NULL,
    doc_type        VARCHAR(100),
    file_extension  VARCHAR(10),
    file_size_bytes BIGINT,
    portal_source   VARCHAR(20),
    direct_url      TEXT,
    portal_url      TEXT,
    internal_doc_id VARCHAR(100),
    archived        BOOLEAN DEFAULT FALSE,
    archived_path   TEXT,
    archived_at     TIMESTAMPTZ,
    content_text    TEXT,
    content_vector  TSVECTOR,
    content_extracted_at TIMESTAMPTZ,
    uploaded_date   DATE,
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
    doc_category    VARCHAR(50)
);

-- DOCUMENT SCRAPE TRACKING
CREATE TABLE document_scrape_status (
    reg_ref         VARCHAR(20) PRIMARY KEY REFERENCES applications(reg_ref),
    portal_source   VARCHAR(20),
    scrape_status   VARCHAR(20) DEFAULT 'pending',
    doc_count       INTEGER DEFAULT 0,
    last_scraped    TIMESTAMPTZ,
    error_message   TEXT
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_applications_search ON applications USING GIN(search_vector);
CREATE INDEX idx_applications_location_trgm ON applications USING GIN(location gin_trgm_ops);
CREATE INDEX idx_applications_applicant_trgm ON applications USING GIN(applicant_name gin_trgm_ops);
CREATE INDEX idx_applications_proposal_trgm ON applications USING GIN(proposal gin_trgm_ops);
CREATE INDEX idx_applications_dev_category ON applications(dev_category);
CREATE INDEX idx_applications_decision ON applications(decision);
CREATE INDEX idx_applications_year ON applications(year);
CREATE INDEX idx_applications_apn_date ON applications(apn_date DESC);
CREATE INDEX idx_applications_location_point ON applications USING GIST(location_point);

CREATE INDEX idx_documents_content_vector ON application_documents USING GIN(content_vector);
CREATE INDEX idx_documents_reg_ref ON application_documents(reg_ref);
CREATE INDEX idx_documents_doc_type ON application_documents(doc_type);

CREATE INDEX idx_appeals_reg_ref ON appeals(reg_ref);
CREATE INDEX idx_further_info_reg_ref ON further_info(reg_ref);
CREATE INDEX idx_scrape_jobs_status ON scrape_jobs(status);
CREATE INDEX idx_scrape_jobs_job_type ON scrape_jobs(job_type);

-- ============================================================
-- TRIGGERS
-- ============================================================

-- SEARCH VECTOR TRIGGER
CREATE OR REPLACE FUNCTION update_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.reg_ref, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.applicant_name, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.location, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.proposal, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.long_proposal, '')), 'D');
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_search_vector
    BEFORE INSERT OR UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- DOCUMENT CONTENT VECTOR TRIGGER
CREATE OR REPLACE FUNCTION update_document_content_vector() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.content_text IS NOT NULL AND NEW.content_text != '' THEN
        NEW.content_vector :=
            setweight(to_tsvector('english', COALESCE(NEW.doc_name, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(NEW.content_text, '')), 'B');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_document_content_vector
    BEFORE INSERT OR UPDATE ON application_documents
    FOR EACH ROW EXECUTE FUNCTION update_document_content_vector();
