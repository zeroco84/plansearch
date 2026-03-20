'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  searchApplications,
  getLatestDigest,
  IRISH_AUTHORITIES,
  LIFECYCLE_STAGES,
  LIFECYCLE_COLORS,
  VALUE_RANGES,
  CATEGORY_LABELS,
  formatValue,
  formatDate,
  getDecisionColor,
  type ApplicationSummary,
  type DigestResponse,
} from '@/lib/api';
import {
  Database, Settings, Map as MapIcon, TrendingUp, BookOpen, Search, Bell, UserCircle,
, BarChart3 } from 'lucide-react';

export default function SignificantPage() {
  const [entries, setEntries] = useState<ApplicationSummary[]>([]);
  const [digest, setDigest] = useState<DigestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [authority, setAuthority] = useState('');
  const [valueMin, setValueMin] = useState(2_000_000);
  const [decision, setDecision] = useState('grant');
  const [category, setCategory] = useState('');
  const [lifecycle, setLifecycle] = useState('');
  const [jurisdiction, setJurisdiction] = useState('');
  const [sort, setSort] = useState('date_desc');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await searchApplications({
        decision,
        authority: authority || undefined,
        value_min: valueMin || undefined,
        category: category || undefined,
        ...(lifecycle && { lifecycle_stage: lifecycle }),
        ...(jurisdiction && { jurisdiction }),
        sort,
        page_size: 50,
        one_off_house: false,
      });
      setEntries(result.results);
    } catch (e) {
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, [authority, valueMin, decision, category, lifecycle, sort]);

  useEffect(() => {
    fetchData();
    getLatestDigest().then(setDigest).catch(() => {});
  }, [fetchData]);

  return (
    <div className="significant-page">
      {/* NAV — matches homepage */}
      <nav style={{ background: '#0d1117', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '64px', padding: '0 2rem', width: '100%' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'white', textDecoration: 'none' }}>
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span style={{ color: 'white', fontSize: '1.125rem', fontWeight: '600', letterSpacing: '-0.01em', fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Link href="/" className="nav-link">
              <Search className="w-5 h-5" />
              <span className="hidden sm:inline">Search</span>
            </Link>
            <Link href="/map" className="nav-link">
              <MapIcon className="w-5 h-5" />
              <span className="hidden sm:inline">Map</span>
            </Link>
            <Link href="/significant" className="nav-link" style={{ color: 'var(--teal)' }}>
              <TrendingUp className="w-5 h-5" />
              <span className="hidden sm:inline">Significant</span>
            </Link>
            <Link href="/analytics" className="nav-link">
              <BarChart3 className="w-5 h-5" />
              <span className="hidden sm:inline">Analytics</span>
            </Link>
            <Link href="/blog" className="nav-link">
              <BookOpen className="w-5 h-5" />
              <span className="hidden sm:inline">Blog</span>
            </Link>
            <Link href="/alerts" className="nav-link">
              <Bell className="w-5 h-5" />
              <span className="hidden sm:inline">Alerts</span>
            </Link>
            <Link href="/login" className="nav-link">
              <UserCircle className="w-5 h-5" />
              <span className="hidden sm:inline">Login</span>
            </Link>
          </div>
        </div>
      </nav>

      <header className="significant-header">
        <div className="header-content">
          <h1>🏗️ Significant Planning Activity</h1>
          <p className="subtitle">
            {digest?.week_start && digest?.week_end
              ? `Week of ${formatDate(digest.week_start)} – ${formatDate(digest.week_end)}`
              : 'Commercially significant planning applications across Ireland'}
          </p>
        </div>
      </header>

      <section className="filters-bar">
        <div className="filter-group">
          <label>Authority</label>
          <select value={authority} onChange={(e) => setAuthority(e.target.value)}>
            <option value="">All Ireland</option>
            {Object.entries(IRISH_AUTHORITIES).map(([province, councils]) => (
              <optgroup key={province} label={province}>
                {councils.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Min Value</label>
          <select value={valueMin} onChange={(e) => setValueMin(Number(e.target.value))}>
            {VALUE_RANGES.map((r) => (
              <option key={r.label} value={r.min || 0}>{r.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Decision</label>
          <select value={decision} onChange={(e) => setDecision(e.target.value)}>
            <option value="">All</option>
            <option value="grant">Granted</option>
            <option value="refuse">Refused</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Type</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All Types</option>
            {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Stage</label>
          <select value={lifecycle} onChange={(e) => setLifecycle(e.target.value)}>
            <option value="">All Stages</option>
            <option value="under_construction">Under Construction</option>
            <option value="complete">Complete</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Jurisdiction</label>
          <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
            <option value="">All Ireland</option>
            <option value="roi">Republic of Ireland</option>
            <option value="ni">Northern Ireland</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Sort</label>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="date_desc">Newest First</option>
            <option value="value_desc">Highest Value</option>
            <option value="date_asc">Oldest First</option>
          </select>
        </div>
      </section>

      <section className="results-section">
        {loading && (
          <div className="loading-state">
            <div className="spinner" />
            <span>Loading significant applications...</span>
          </div>
        )}

        {!loading && entries.length === 0 && (
          <div className="empty-state">
            <p>No significant applications match your filters.</p>
            <p className="hint">Try widening your search criteria.</p>
          </div>
        )}

        {!loading && entries.map((app, index) => (
          <article key={app.id} className="significant-card">
            <div className="card-rank">{index + 1}</div>

            <div className="card-value">
              {app.est_value_high
                ? formatValue(app.est_value_high)
                : '—'}
            </div>

            <div className="card-body">
              <h3 className="card-title">
                <Link href={`/application/${encodeURIComponent(app.reg_ref)}`}>
                  {app.proposal
                    ? app.proposal.substring(0, 120) + (app.proposal.length > 120 ? '...' : '')
                    : app.reg_ref}
                </Link>
              </h3>

              <div className="card-meta">
                <span
                  className="authority-tag"
                  title={app.planning_authority || ''}
                >
                  {app.planning_authority || 'DCC'}
                </span>
                {app.data_source === 'NIDFT' && (
                  <span style={{
                    fontSize: '0.55rem', color: '#fff',
                    background: '#1d4ed8', padding: '0.1rem 0.3rem',
                    borderRadius: '3px', fontWeight: 700, letterSpacing: '0.05em',
                  }}>
                    NI
                  </span>
                )}

                {app.decision && (
                  <span
                    className="decision-badge"
                    style={{ backgroundColor: getDecisionColor(app.decision) }}
                  >
                    {app.decision}
                  </span>
                )}

                {app.lifecycle_stage && (
                  <span
                    className="lifecycle-badge"
                    style={{
                      backgroundColor: LIFECYCLE_COLORS[app.lifecycle_stage] || '#6b7280',
                    }}
                  >
                    {LIFECYCLE_STAGES[app.lifecycle_stage] || app.lifecycle_stage}
                  </span>
                )}

                {app.dev_category && (
                  <span className="category-tag">
                    {CATEGORY_LABELS[app.dev_category] || app.dev_category}
                  </span>
                )}
              </div>

              <div className="card-details">
                {app.location && <span className="detail">📍 {app.location}</span>}
                {app.applicant_name && <span className="detail">👤 {app.applicant_name}</span>}
                {app.num_residential_units && (
                  <span className="detail">🏠 {app.num_residential_units} units</span>
                )}
                {app.floor_area && (
                  <span className="detail">📐 {app.floor_area.toLocaleString()} m²</span>
                )}
                {app.apn_date && <span className="detail">📅 {formatDate(app.apn_date)}</span>}
              </div>

              <div className="card-footer">
                <span className="ref">{app.reg_ref}</span>
                {app.significance_score && (
                  <span className="score" title="Significance score">
                    ⭐ {app.significance_score}/100
                  </span>
                )}
              </div>
            </div>
          </article>
        ))}
      </section>

      <footer className="significant-footer">
        <div className="footer-links">
          <a href="/api/feed/weekly-digest.xml" className="rss-link" title="Subscribe to RSS">
            📡 RSS Feed
          </a>
          <a href="/api/digest/latest" className="api-link" title="JSON API">
            {'{'} {'}'} JSON API
          </a>
          <Link href="/" className="home-link">← Back to Search</Link>
        </div>
        <p className="footer-note">
          Data sourced from NPAD, BCMS, and DCC open data under CC BY 4.0.
          AI value estimates powered by Claude.
        </p>
      </footer>

      <style jsx>{`
        .significant-page {
          min-height: 100vh;
          background: linear-gradient(145deg, #0f0f23 0%, #1a1a3e 50%, #0d1b2a 100%);
          color: #e2e8f0;
          font-family: 'Inter', -apple-system, sans-serif;
        }

        .significant-header {
          padding: 2rem 2rem 1.5rem;
          text-align: center;
          background: rgba(255,255,255,0.03);
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        h1 {
          font-size: 1.75rem;
          font-weight: 700;
          margin: 0 0 0.5rem;
          background: linear-gradient(135deg, #60a5fa, #a78bfa);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .subtitle {
          color: #94a3b8;
          font-size: 0.95rem;
          margin: 0;
        }

        .filters-bar {
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem;
          padding: 1rem 2rem;
          background: rgba(255,255,255,0.02);
          border-bottom: 1px solid rgba(255,255,255,0.06);
          max-width: 1100px;
          margin: 0 auto;
        }

        .filter-group {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
          min-width: 120px;
          flex: 1;
        }

        .filter-group label {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: #64748b;
          font-weight: 600;
        }

        .filter-group select {
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 8px;
          color: #e2e8f0;
          padding: 0.5rem 0.75rem;
          font-size: 0.85rem;
          cursor: pointer;
          outline: none;
          transition: border-color 0.2s;
        }

        .filter-group select:hover { border-color: rgba(255,255,255,0.2); }
        .filter-group select:focus { border-color: #60a5fa; }

        .results-section {
          max-width: 1100px;
          margin: 0 auto;
          padding: 1.5rem 2rem;
        }

        .loading-state, .empty-state {
          text-align: center;
          padding: 3rem;
          color: #94a3b8;
        }

        .spinner {
          width: 32px;
          height: 32px;
          border: 3px solid rgba(96, 165, 250, 0.2);
          border-top-color: #60a5fa;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          margin: 0 auto 1rem;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        .significant-card {
          display: flex;
          gap: 1rem;
          padding: 1.25rem;
          margin-bottom: 0.75rem;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 12px;
          transition: all 0.2s ease;
        }

        .significant-card:hover {
          background: rgba(255,255,255,0.06);
          border-color: rgba(96, 165, 250, 0.2);
          transform: translateY(-1px);
        }

        .card-rank {
          font-size: 0.85rem;
          font-weight: 700;
          color: #64748b;
          min-width: 24px;
          padding-top: 0.15rem;
        }

        .card-value {
          font-size: 1.35rem;
          font-weight: 800;
          color: #10b981;
          min-width: 80px;
          padding-top: 0.1rem;
        }

        .card-body { flex: 1; min-width: 0; }

        .card-title {
          font-size: 1rem;
          font-weight: 600;
          margin: 0 0 0.5rem;
          line-height: 1.4;
        }

        .card-title a {
          color: #e2e8f0;
          text-decoration: none;
        }

        .card-title a:hover { color: #60a5fa; }

        .card-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 0.4rem;
          margin-bottom: 0.5rem;
        }

        .authority-tag {
          background: rgba(96, 165, 250, 0.12);
          color: #93c5fd;
          padding: 0.15rem 0.5rem;
          border-radius: 4px;
          font-size: 0.75rem;
          font-weight: 500;
        }

        .decision-badge, .lifecycle-badge {
          padding: 0.15rem 0.5rem;
          border-radius: 4px;
          font-size: 0.7rem;
          font-weight: 600;
          color: white;
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }

        .category-tag {
          background: rgba(167, 139, 250, 0.12);
          color: #c4b5fd;
          padding: 0.15rem 0.5rem;
          border-radius: 4px;
          font-size: 0.75rem;
        }

        .card-details {
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem;
          margin-bottom: 0.5rem;
        }

        .detail {
          font-size: 0.8rem;
          color: #94a3b8;
        }

        .card-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .ref {
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.75rem;
          color: #64748b;
        }

        .score {
          font-size: 0.8rem;
          color: #f59e0b;
          font-weight: 600;
        }

        .significant-footer {
          text-align: center;
          padding: 2rem;
          border-top: 1px solid rgba(255,255,255,0.06);
          margin-top: 2rem;
        }

        .footer-links {
          display: flex;
          gap: 1.5rem;
          justify-content: center;
          margin-bottom: 1rem;
        }

        .footer-links a {
          color: #60a5fa;
          text-decoration: none;
          font-size: 0.85rem;
        }

        .footer-links a:hover { text-decoration: underline; }

        .footer-note {
          font-size: 0.75rem;
          color: #475569;
          max-width: 500px;
          margin: 0 auto;
          line-height: 1.5;
        }

        @media (max-width: 768px) {
          .filters-bar { flex-wrap: wrap; }
          .significant-card { flex-direction: column; gap: 0.5rem; }
          .card-value { font-size: 1.1rem; }
          h1 { font-size: 1.3rem; }
        }
      `}</style>
    </div>
  );
}
