-- LRD Schema Migration
-- Adds indexes for LRD candidate queries and archived document lookups.
--
-- Run with:
--   docker exec -i plansearch-postgres-1 psql -U plansearch plansearch < scripts/lrd_schema.sql
--
-- Or inside the container:
--   psql -U plansearch plansearch -f /tmp/lrd_schema.sql

-- ── Index for finding unarchived documents with direct URLs ─────────
-- Used by the LRD archiver to find its next batch of work.
CREATE INDEX IF NOT EXISTS idx_app_docs_unarchived
    ON application_documents (reg_ref)
    WHERE direct_url IS NOT NULL
      AND (archived IS NULL OR archived = false);

-- ── Index for looking up archived documents by reg_ref ──────────────
-- Used by the archived docs API when serving files.
CREATE INDEX IF NOT EXISTS idx_app_docs_archived_ref
    ON application_documents (reg_ref)
    WHERE archived = true;

-- ── Index on archived_path for file serving lookups ─────────────────
CREATE INDEX IF NOT EXISTS idx_app_docs_archived_path
    ON application_documents (archived_path)
    WHERE archived_path IS NOT NULL;

-- ── Partial index for LRD candidate selection ───────────────────────
-- Helps the archiver efficiently find recent applications with docs
-- that haven't been archived yet.
CREATE INDEX IF NOT EXISTS idx_app_docs_lrd_candidates
    ON application_documents (reg_ref, id)
    WHERE direct_url IS NOT NULL
      AND direct_url != ''
      AND (archived IS NULL OR archived = false);
