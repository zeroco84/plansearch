-- PlanSearch Phase 3 Schema: The Build Integration + Advertising
-- Run after phase2_schema.sql
-- All statements are IF NOT EXISTS safe for re-runs

-- ═══════════════════════════════════════════════════════════════
-- Section 23: The Build Posts + Content Links
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS build_posts (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(200) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT,
    excerpt TEXT,                     -- plain text, max 400 chars
    featured_image_url TEXT,
    substack_url TEXT NOT NULL,
    published_at TIMESTAMPTZ,

    -- AI-generated metadata (background worker)
    summary_one_line TEXT,           -- one sentence for cards
    topics TEXT[],                   -- e.g. ['judicial_review', 'LRD', 'student_housing']
    mentioned_councils TEXT[],       -- councils discussed
    tone VARCHAR(20),               -- 'analysis'|'opinion'|'case_study'|'news'

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Links between Build posts and planning applications
CREATE TABLE IF NOT EXISTS post_application_links (
    post_id INTEGER REFERENCES build_posts(id) ON DELETE CASCADE,
    application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    link_type VARCHAR(30),
    -- 'mentioned'         the post explicitly references this application
    -- 'related_location'  the post discusses this area/development
    -- 'related_topic'     the post covers a topic relevant to this application
    confidence FLOAT,
    PRIMARY KEY (post_id, application_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_published ON build_posts(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_topics ON build_posts USING GIN(topics);
CREATE INDEX IF NOT EXISTS idx_posts_councils ON build_posts USING GIN(mentioned_councils);
CREATE INDEX IF NOT EXISTS idx_pal_application ON post_application_links(application_id);


-- ═══════════════════════════════════════════════════════════════
-- Section 24: Advertising
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS advertisers (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    industry VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ad_campaigns (
    id SERIAL PRIMARY KEY,
    advertiser_id INTEGER REFERENCES advertisers(id),
    campaign_name TEXT NOT NULL,
    campaign_type VARCHAR(20),       -- 'display' | 'sponsored_content'
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'active',  -- active|paused|ended

    -- Display ad creative
    headline VARCHAR(60),
    body_text VARCHAR(120),
    cta_text VARCHAR(30),            -- e.g. 'Learn more'
    cta_url TEXT,
    logo_url TEXT,

    -- Contextual targeting (optional — all nullable)
    target_categories TEXT[],        -- dev categories to show alongside
    target_councils TEXT[],          -- councils to show alongside
    target_lifecycle TEXT[],         -- lifecycle stages

    -- Analytics (aggregate only — no personal data)
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,

    -- Financials
    agreed_price NUMERIC(10,2),
    invoice_ref TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Aggregate impression log — no user data
CREATE TABLE IF NOT EXISTS ad_impressions (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES ad_campaigns(id),
    page_path TEXT,
    clicked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_impressions_campaign ON ad_impressions(campaign_id);
CREATE INDEX IF NOT EXISTS idx_impressions_date ON ad_impressions(created_at);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON ad_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_dates ON ad_campaigns(start_date, end_date);
