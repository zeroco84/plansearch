-- PlanSearch Phase 2 Schema Extensions
-- National Expansion + Lifecycle Tracking + AI Intelligence

-- ============================================================
-- 1. NEW COLUMNS ON applications TABLE (Section 14.5)
-- ============================================================

-- National data (NPAD fields)
ALTER TABLE applications ADD COLUMN IF NOT EXISTS planning_authority VARCHAR(100);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS land_use_code VARCHAR(50);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS area_of_site FLOAT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS num_residential_units INTEGER;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS floor_area FLOAT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS one_off_house BOOLEAN;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS applicant_forename VARCHAR(100);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS applicant_surname VARCHAR(100);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS applicant_address TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS link_app_details TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS npad_object_id INTEGER;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS data_source VARCHAR(20) DEFAULT 'dcc_csv';
ALTER TABLE applications ADD COLUMN IF NOT EXISTS eircode VARCHAR(10);

-- NPAD appeal fields (richer than Phase 1)
ALTER TABLE applications ADD COLUMN IF NOT EXISTS appeal_ref_number VARCHAR(30);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS appeal_status VARCHAR(50);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS appeal_decision VARCHAR(50);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS appeal_decision_date DATE;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS fi_request_date DATE;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS fi_rec_date DATE;

-- Lifecycle stage (Section 15.4)
ALTER TABLE applications ADD COLUMN IF NOT EXISTS lifecycle_stage VARCHAR(30);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS lifecycle_updated_at TIMESTAMPTZ;

-- AI value estimation (Section 16.2)
ALTER TABLE applications ADD COLUMN IF NOT EXISTS est_value_low BIGINT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS est_value_high BIGINT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS est_value_basis TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS est_value_type VARCHAR(100);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS est_value_confidence VARCHAR(10);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS value_estimated_at TIMESTAMPTZ;

-- Significance scoring (Section 16.3)
ALTER TABLE applications ADD COLUMN IF NOT EXISTS significance_score INTEGER DEFAULT 0;

-- Professional identification (Section 16.4)
ALTER TABLE applications ADD COLUMN IF NOT EXISTS planning_agent_name TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS planning_agent_company TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS architect_name TEXT;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS architect_company TEXT;

-- ============================================================
-- 2. NEW INDEXES FOR NATIONAL SEARCH
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_applications_authority ON applications(planning_authority);
CREATE INDEX IF NOT EXISTS idx_applications_land_use ON applications(land_use_code);
CREATE INDEX IF NOT EXISTS idx_applications_units ON applications(num_residential_units);
CREATE INDEX IF NOT EXISTS idx_applications_floor_area ON applications(floor_area);
CREATE INDEX IF NOT EXISTS idx_applications_authority_date ON applications(planning_authority, apn_date DESC);
CREATE INDEX IF NOT EXISTS idx_applications_value ON applications(est_value_high DESC) WHERE est_value_high IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_applications_significance ON applications(significance_score DESC);
CREATE INDEX IF NOT EXISTS idx_applications_lifecycle ON applications(lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_applications_data_source ON applications(data_source);

-- ============================================================
-- 3. COMMENCEMENT NOTICES + COMPLETIONS TABLE (Section 15.3)
-- ============================================================

CREATE TABLE IF NOT EXISTS commencement_notices (
    id                      SERIAL PRIMARY KEY,
    reg_ref                 VARCHAR(30),
    local_authority         VARCHAR(100),

    -- Commencement
    cn_commencement_date    DATE,
    cn_proposed_end_date    DATE,
    cn_project_status       VARCHAR(50),
    cn_date_granted         DATE,
    cn_date_expiry          DATE,
    cn_description          TEXT,
    cn_proposed_use_desc    TEXT,

    -- Building characteristics
    cn_total_floor_area     FLOAT,
    cn_total_dwelling_units INTEGER,
    cn_total_apartments     INTEGER,
    cn_number_stories_above INTEGER,
    cn_number_bedrooms      INTEGER,
    cn_protected_structure  BOOLEAN,
    cn_phase                VARCHAR(10),
    cn_units_for_phase      INTEGER,
    cn_total_phases         INTEGER,

    -- Address
    cn_street               TEXT,
    cn_town                 TEXT,
    cn_eircode              VARCHAR(10),
    cn_county               VARCHAR(50),
    cn_lat                  FLOAT,
    cn_lng                  FLOAT,
    location_point          GEOMETRY(Point, 4326),

    -- Completion
    ccc_date_validated      DATE,
    ccc_units_completed     INTEGER,
    ccc_type                VARCHAR(100),

    -- Metadata
    raw_data                JSONB,
    ingested_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cn_reg_ref ON commencement_notices(reg_ref);
CREATE INDEX IF NOT EXISTS idx_cn_date ON commencement_notices(cn_commencement_date DESC);
CREATE INDEX IF NOT EXISTS idx_cn_authority ON commencement_notices(local_authority);
CREATE INDEX IF NOT EXISTS idx_cn_location ON commencement_notices USING GIST(location_point);
CREATE INDEX IF NOT EXISTS idx_cn_ccc ON commencement_notices(ccc_date_validated) WHERE ccc_date_validated IS NOT NULL;

-- ============================================================
-- 4. FIRE SAFETY / DISABILITY ACCESS CERTIFICATES (Section 15.3)
-- ============================================================

CREATE TABLE IF NOT EXISTS fsc_applications (
    id                          SERIAL PRIMARY KEY,
    reg_ref                     VARCHAR(30),
    application_reference_no    VARCHAR(50),
    application_type            VARCHAR(20),
    local_authority             VARCHAR(100),
    submission_date             DATE,
    date_of_decision            DATE,
    decision_type               VARCHAR(50),

    -- Building data
    floor_area_of_building      FLOAT,
    total_combined_floor_area   FLOAT,
    no_of_stories_above_ground  INTEGER,
    site_area                   FLOAT,
    use_of_proposed_works       TEXT,
    main_construction_type      VARCHAR(100),

    -- Construction status
    date_construction_started   DATE,
    is_construction_complete    BOOLEAN,
    date_of_completion          DATE,
    is_building_occupied        BOOLEAN,

    -- Applicant
    applicant_name              TEXT,
    applicant_address_line_1    TEXT,
    applicant_town              TEXT,
    applicant_county            VARCHAR(50),

    -- Location
    lat                         FLOAT,
    longitude                   FLOAT,
    eircode                     VARCHAR(10),
    location_point              GEOMETRY(Point, 4326),

    raw_data                    JSONB,
    ingested_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fsc_reg_ref ON fsc_applications(reg_ref);
CREATE INDEX IF NOT EXISTS idx_fsc_type ON fsc_applications(application_type);
CREATE INDEX IF NOT EXISTS idx_fsc_date ON fsc_applications(submission_date DESC);
CREATE INDEX IF NOT EXISTS idx_fsc_decision ON fsc_applications(decision_type);

-- ============================================================
-- 5. COST BENCHMARKS TABLE (admin-configurable)
-- ============================================================

CREATE TABLE IF NOT EXISTS cost_benchmarks (
    id                  SERIAL PRIMARY KEY,
    development_type    VARCHAR(100) NOT NULL UNIQUE,
    unit_label          VARCHAR(20) NOT NULL,
    cost_low            INTEGER NOT NULL,
    cost_high           INTEGER NOT NULL,
    notes               TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default benchmarks (Section 16.2)
INSERT INTO cost_benchmarks (development_type, unit_label, cost_low, cost_high, notes) VALUES
    ('apartments_social',       'per unit', 280000, 340000, 'Social/affordable apartments'),
    ('apartments_private',      'per unit', 320000, 420000, 'Private apartments'),
    ('student_accommodation',   'per bed',  90000,  130000, 'Student accommodation'),
    ('houses_one_off',          'per house',180000, 260000, 'One-off rural houses'),
    ('houses_scheme',           'per unit', 200000, 280000, 'Scheme housing'),
    ('hotel',                   'per room', 180000, 280000, 'Hotels'),
    ('office',                  'per m²',   2800,   4200,   'Office'),
    ('retail',                  'per m²',   1800,   2800,   'Retail/restaurant'),
    ('industrial_warehouse',    'per m²',   800,    1400,   'Industrial/warehouse'),
    ('data_centre',             'per m²',   8000,   15000,  'Data centres'),
    ('hospital_medical',        'per m²',   4000,   7000,   'Hospital/medical'),
    ('school_education',        'per m²',   2200,   3500,   'School/education'),
    ('mixed_use',               'blended',  0,      0,      'Calculate each component separately')
ON CONFLICT (development_type) DO NOTHING;

-- ============================================================
-- 6. WEEKLY DIGEST TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS weekly_digests (
    id              SERIAL PRIMARY KEY,
    week_start      DATE NOT NULL,
    week_end        DATE NOT NULL,
    generated_at    TIMESTAMPTZ DEFAULT NOW(),
    total_entries   INTEGER DEFAULT 0,
    digest_data     JSONB,
    published       BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_digests_week ON weekly_digests(week_start DESC);
