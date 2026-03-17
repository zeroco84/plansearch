'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import {
  Search, MapPin, Filter, Download, ChevronDown,
  Building2, Calendar, Scale, ArrowUpDown, X, Settings,
  Database, Map as MapIcon, TrendingUp, BookOpen
} from 'lucide-react';
import {
  searchApplications, SearchParams, ApplicationSummary, SearchResponse,
  CATEGORY_LABELS, IRISH_AUTHORITIES, LIFECYCLE_STAGES, LIFECYCLE_COLORS,
  VALUE_RANGES, getDecisionColor, formatDate, formatValue,
} from '@/lib/api';
import PromotedCard from '@/components/PromotedCard';

const DECISIONS = [
  { value: '', label: 'All Decisions' },
  { value: 'GRANTED', label: 'Granted' },
  { value: 'REFUSED', label: 'Refused' },
  { value: 'FURTHER_INFO', label: 'Further Info' },
  { value: 'SPLIT', label: 'Split Decision' },
  { value: 'WITHDRAWN', label: 'Withdrawn' },
];

const SORT_OPTIONS = [
  { value: 'date_desc', label: 'Newest First' },
  { value: 'date_asc', label: 'Oldest First' },
  { value: 'relevance', label: 'Most Relevant' },
  { value: 'value_desc', label: 'Highest Value' },
  { value: 'significance', label: 'Most Significant' },
];

function getDecisionClass(decision: string | null): string {
  if (!decision) return 'decision-pending';
  const upper = decision.toUpperCase();
  if (upper.includes('GRANT')) return 'decision-granted';
  if (upper.includes('REFUS')) return 'decision-refused';
  if (upper.includes('FURTHER') || upper.includes('INFO')) return 'decision-further-info';
  if (upper.includes('SPLIT')) return 'decision-split';
  if (upper.includes('WITHDRAW')) return 'decision-withdrawn';
  return 'decision-pending';
}

function getDecisionLabel(decision: string | null): string {
  if (!decision) return 'Pending';
  const upper = decision.toUpperCase();
  if (upper.includes('GRANT')) return 'Granted';
  if (upper.includes('REFUS')) return 'Refused';
  if (upper.includes('FURTHER') || upper.includes('INFO')) return 'Further Info';
  if (upper.includes('SPLIT')) return 'Split';
  if (upper.includes('WITHDRAW')) return 'Withdrawn';
  return decision;
}

export default function Home() {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [decision, setDecision] = useState('');
  const [yearFrom, setYearFrom] = useState('');
  const [yearTo, setYearTo] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [applicantFilter, setApplicantFilter] = useState('');
  const [sort, setSort] = useState('date_desc');
  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);
  // Phase 2 national filters
  const [authority, setAuthority] = useState('');
  const [lifecycleStage, setLifecycleStage] = useState('');
  const [valueMin, setValueMin] = useState('');

  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Keyboard shortcut: "/" to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const performSearch = useCallback(async (params: SearchParams) => {
    setLoading(true);
    setError(null);
    try {
      const res = await searchApplications(params);
      setResults(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      const params: SearchParams = { page, page_size: 25 };
      if (query) params.q = query;
      if (category) params.category = category;
      if (decision) params.decision = decision;
      if (yearFrom) params.year_from = parseInt(yearFrom);
      if (yearTo) params.year_to = parseInt(yearTo);
      if (locationFilter) params.location = locationFilter;
      if (applicantFilter) params.applicant = applicantFilter;
      if (sort) params.sort = sort;
      // Phase 2 national filters
      if (authority) params.authority = authority;
      if (lifecycleStage) params.lifecycle_stage = lifecycleStage;
      if (valueMin) params.value_min = parseInt(valueMin);

      performSearch(params);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, category, decision, yearFrom, yearTo, locationFilter, applicantFilter, sort, page, authority, lifecycleStage, valueMin, performSearch]);

  const clearFilters = () => {
    setQuery('');
    setCategory('');
    setDecision('');
    setYearFrom('');
    setYearTo('');
    setLocationFilter('');
    setApplicantFilter('');
    setSort('date_desc');
    setPage(1);
    setAuthority('');
    setLifecycleStage('');
    setValueMin('');
  };

  const hasActiveFilters = category || decision || yearFrom || yearTo || locationFilter || applicantFilter || authority || lifecycleStage || valueMin;

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 25 }, (_, i) => currentYear - i);

  return (
    <main className="min-h-screen flex flex-col">

      {/* NAV */}
      <nav style={{ background: '#0d1117', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-6xl mx-auto py-4 flex items-center justify-between" style={{ padding: '1rem 1.5rem' }}>
          <Link href="/" className="flex items-center gap-2 text-white no-underline">
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>
              PlanSearch
            </span>
          </Link>
          <div className="flex items-center gap-1">
            <Link href="/map" className="nav-link">
              <MapIcon className="w-4 h-4" />
              <span className="hidden sm:inline">Map</span>
            </Link>
            <Link href="/significant" className="nav-link">
              <TrendingUp className="w-4 h-4" />
              <span className="hidden sm:inline">Significant</span>
            </Link>
            <Link href="/insights" className="nav-link">
              <BookOpen className="w-4 h-4" />
              <span className="hidden sm:inline">Insights</span>
            </Link>
            <Link href="/admin" className="nav-link">
              <Settings className="w-4 h-4" />
              <span className="hidden sm:inline">Admin</span>
            </Link>
          </div>
        </div>
      </nav>

      {/* HERO — flex-1 fills remaining viewport height, centres content */}
      <section
        className="flex-1 flex flex-col items-center justify-center"
        style={{ background: 'linear-gradient(160deg, #0d1117 0%, #111827 50%, #0f2027 100%)', padding: '3rem 1.5rem', minHeight: '70vh' }}
      >
        <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.7rem', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: '2rem', textAlign: 'center', width: '100%', padding: '0 1rem' }}>
          650,000+ planning applications · 31 local authorities · AI-classified
        </p>
        <div style={{ width: '100%', maxWidth: 'min(680px, 90vw)' }}>
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: 'rgba(255,255,255,0.35)' }} />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search planning applications..."
              value={query}
              onChange={(e) => { setQuery(e.target.value); setPage(1); }}
              style={{
                width: '100%',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: '12px',
                padding: '1rem 3.5rem 1rem 3rem',
                color: 'white',
                fontSize: '1.05rem',
                outline: 'none',
                transition: 'border-color 0.2s, box-shadow 0.2s',
              }}
              onFocus={e => { e.target.style.borderColor = '#1d9e75'; e.target.style.boxShadow = '0 0 0 3px rgba(29,158,117,0.15)'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(255,255,255,0.12)'; e.target.style.boxShadow = 'none'; }}
            />
            <kbd style={{ position: 'absolute', right: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,0.2)', fontSize: '0.7rem', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '4px', padding: '2px 6px' }}>/</kbd>
          </div>
          {results && query && (
            <p style={{ textAlign: 'center', color: 'rgba(255,255,255,0.3)', fontSize: '0.75rem', marginTop: '0.75rem' }}>
              {results.total.toLocaleString()} results
              {results.query_time_ms && <span style={{ marginLeft: '0.5rem', opacity: 0.6 }}>{results.query_time_ms.toFixed(0)}ms</span>}
            </p>
          )}
        </div>

        {/* Suggestion chips — show only when no query */}
        {!query && (
          <div style={{ marginTop: '2.5rem', textAlign: 'center' }}>
            <p style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.25)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.75rem' }}>Try searching for</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center', marginTop: '0.5rem' }}>
              {['apartments Dublin', 'hotel Cork', 'student accommodation Galway', 'data centre Kildare', 'protected structure'].map(example => (
                <button
                  key={example}
                  onClick={() => { setQuery(example); setPage(1); }}
                  style={{ fontSize: '0.8rem', padding: '6px 16px', borderRadius: '20px', border: '1px solid rgba(255,255,255,0.15)', background: 'transparent', color: 'rgba(255,255,255,0.5)', cursor: 'pointer', transition: 'all 0.15s' }}
                  onMouseEnter={e => { (e.target as HTMLButtonElement).style.borderColor = '#1d9e75'; (e.target as HTMLButtonElement).style.color = '#1d9e75'; }}
                  onMouseLeave={e => { (e.target as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.15)'; (e.target as HTMLButtonElement).style.color = 'rgba(255,255,255,0.5)'; }}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* RESULTS SECTION — only renders when there is a query */}
      {query && (
        <section style={{ background: '#f9f8f6', flex: 1, padding: '1.5rem 1.5rem 4rem' }}>
          <div style={{ maxWidth: '860px', margin: '0 auto' }}>

            {/* Filters row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '8px' }}>
              <button
                className="btn-secondary"
                style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.875rem' }}
                onClick={() => setShowFilters(!showFilters)}
              >
                <Filter className="w-4 h-4" />
                Filters
                {hasActiveFilters && <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#1d9e75', display: 'inline-block' }} />}
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {hasActiveFilters && (
                  <button onClick={clearFilters} style={{ fontSize: '0.75rem', color: '#9ca3af', background: 'none', border: 'none', cursor: 'pointer' }}>
                    Clear all
                  </button>
                )}
                <select className="filter-select" value={sort} onChange={(e) => setSort(e.target.value)}>
                  {SORT_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
            </div>

            {/* Expanded filters */}
            {showFilters && (
              <div className="filter-panel fade-in" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                <select className="filter-select" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
                  <option value="">All Categories</option>
                  {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>

                <select className="filter-select" value={authority} onChange={(e) => { setAuthority(e.target.value); setPage(1); }}>
                  <option value="">All Ireland</option>
                  {Object.entries(IRISH_AUTHORITIES).map(([province, councils]) => (
                    <optgroup key={province} label={province}>
                      {councils.map(c => <option key={c} value={c}>{c}</option>)}
                    </optgroup>
                  ))}
                </select>

                <select className="filter-select" value={decision} onChange={(e) => { setDecision(e.target.value); setPage(1); }}>
                  {DECISIONS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>

                <select className="filter-select" value={lifecycleStage} onChange={(e) => { setLifecycleStage(e.target.value); setPage(1); }}>
                  <option value="">All Stages</option>
                  {Object.entries(LIFECYCLE_STAGES).map(([key, label]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>

                <select className="filter-select" value={valueMin} onChange={(e) => { setValueMin(e.target.value); setPage(1); }}>
                  <option value="">Est. Value</option>
                  {VALUE_RANGES.filter(r => r.min).map(r => (
                    <option key={r.label} value={r.min}>{r.label}</option>
                  ))}
                </select>

                <select className="filter-select" value={yearFrom} onChange={(e) => { setYearFrom(e.target.value); setPage(1); }}>
                  <option value="">From Year</option>
                  {years.map(y => <option key={y} value={y}>{y}</option>)}
                </select>

                <input
                  type="text"
                  className="filter-input"
                  placeholder="Applicant name..."
                  value={applicantFilter}
                  onChange={(e) => { setApplicantFilter(e.target.value); setPage(1); }}
                />

                <input
                  type="text"
                  className="filter-input"
                  placeholder="Location..."
                  value={locationFilter}
                  onChange={(e) => { setLocationFilter(e.target.value); setPage(1); }}
                />
              </div>
            )}

            {/* Error */}
            {error && !loading && (
              <div style={{ background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '8px', padding: '1rem', marginBottom: '1rem', fontSize: '0.875rem', color: '#92400e' }}>
                ⏳ Connecting to search service — results will appear shortly.
              </div>
            )}

            {/* Results */}
            <div className="space-y-3">
              {loading && !results && (
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="result-card">
                    <div className="skeleton h-4 w-24 mb-3" />
                    <div className="skeleton h-5 w-3/4 mb-2" />
                    <div className="skeleton h-4 w-1/2" />
                  </div>
                ))
              )}

              {results?.results.map((app, i) => (
                <div key={app.id}>
                  {i === 9 && (
                    <PromotedCard
                      devCategory={category}
                      council={authority}
                      lifecycleStage={lifecycleStage}
                      pagePath="/search"
                    />
                  )}
                  <Link
                    href={`/application/${encodeURIComponent(app.reg_ref)}`}
                    className="no-underline"
                  >
                    <div className="result-card fade-in" style={{ animationDelay: `${i * 30}ms` }}>
                      <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="reg-ref-badge">{app.reg_ref}</span>
                          <span className={`decision-chip ${getDecisionClass(app.decision)}`}>
                            {getDecisionLabel(app.decision)}
                          </span>
                          {app.dev_category && (
                            <span className="category-tag">
                              {CATEGORY_LABELS[app.dev_category] || app.dev_category}
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-[var(--text-muted)]">
                          {formatDate(app.apn_date)}
                        </span>
                      </div>

                      {app.location && (
                        <div className="flex items-start gap-1.5 mb-1.5">
                          <MapPin className="w-3.5 h-3.5 text-[var(--text-muted)] mt-0.5 flex-shrink-0" />
                          <span className="text-sm font-medium text-[var(--text-primary)]">{app.location}</span>
                        </div>
                      )}

                      {app.proposal && (
                        <p className="text-sm text-[var(--text-secondary)] line-clamp-2 ml-5">
                          {app.proposal}
                        </p>
                      )}

                      {app.applicant_name && (
                        <div className="flex items-center gap-1.5 mt-2 ml-5">
                          <Building2 className="w-3 h-3 text-[var(--text-muted)]" />
                          <span className="text-xs text-[var(--text-muted)]">{app.applicant_name}</span>
                        </div>
                      )}

                      <div className="flex flex-wrap items-center gap-2 mt-2 ml-5">
                        {app.planning_authority && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-700" style={{ fontSize: '0.65rem' }}>
                            {app.planning_authority}
                          </span>
                        )}
                        {app.lifecycle_stage && (
                          <span
                            className="text-xs px-1.5 py-0.5 rounded text-white"
                            style={{ backgroundColor: LIFECYCLE_COLORS[app.lifecycle_stage] || '#6b7280', fontSize: '0.65rem' }}
                          >
                            {LIFECYCLE_STAGES[app.lifecycle_stage] || app.lifecycle_stage}
                          </span>
                        )}
                        {app.est_value_high && (
                          <span className="text-xs font-semibold text-emerald-600" style={{ fontSize: '0.7rem' }}>
                            {formatValue(app.est_value_high)}
                          </span>
                        )}
                        {app.num_residential_units && app.num_residential_units > 0 && (
                          <span className="text-xs text-[var(--text-muted)]">
                            {app.num_residential_units} units
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                </div>
              ))}

              {results && results.results.length === 0 && (
                <div className="text-center py-16">
                  <Search className="w-12 h-12 text-[var(--border)] mx-auto mb-4" />
                  <h3 className="text-lg text-[var(--text-secondary)]" style={{ fontFamily: "'Playfair Display', serif" }}>
                    No applications found
                  </h3>
                  <p className="text-sm text-[var(--text-muted)] mt-1">
                    Try adjusting your search or filters
                  </p>
                </div>
              )}
            </div>

            {/* Pagination */}
            {results && results.total_pages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8 mb-12">
                <button
                  className="btn-secondary"
                  disabled={page <= 1}
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <span className="text-sm text-[var(--text-muted)] px-4">
                  Page {page} of {results.total_pages}
                </span>
                <button
                  className="btn-secondary"
                  disabled={page >= results.total_pages}
                  onClick={() => setPage(p => p + 1)}
                >
                  Next
                </button>
              </div>
            )}

            {/* CSV Export */}
            {results && results.total > 0 && (
              <div className="text-center mb-8">
                <a
                  href={(() => {
                    const params = new URLSearchParams();
                    if (query) params.set('q', query);
                    if (category) params.set('category', category);
                    if (decision) params.set('decision', decision);
                    if (yearFrom) params.set('year_from', yearFrom);
                    if (yearTo) params.set('year_to', yearTo);
                    if (applicantFilter) params.set('applicant', applicantFilter);
                    if (locationFilter) params.set('location', locationFilter);
                    return `https://api.plansearch.cc/api/export/csv?${params.toString()}`;
                  })()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary inline-flex no-underline"
                >
                  <Download className="w-4 h-4" />
                  Export CSV ({Math.min(results.total, 5000).toLocaleString()} rows)
                </a>
              </div>
            )}

          </div>
        </section>
      )}

      {/* FOOTER */}
      <footer style={{ borderTop: '1px solid #e5e7eb', padding: '2rem 1.5rem', background: query ? '#f9f8f6' : '#0d1117' }}>
        <div style={{ maxWidth: '860px', margin: '0 auto', textAlign: 'center', fontSize: '0.75rem', color: query ? '#9ca3af' : 'rgba(255,255,255,0.25)' }}>
          <p>PlanSearch — Irish National Planning Intelligence Platform</p>
          <p style={{ marginTop: '4px' }}>Data sourced from NPAD, BCMS, and DCC Open Data (CC BY 4.0). AI classification and value estimation powered by Claude.</p>
        </div>
      </footer>

    </main>
  );
}

