'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import {
  Search, MapPin, Filter, Download, ChevronDown,
  Building2, Calendar, Scale, ArrowUpDown, X, Settings,
  Database, Map as MapIcon
} from 'lucide-react';
import {
  searchApplications, SearchParams, ApplicationSummary, SearchResponse,
  CATEGORY_LABELS, getDecisionColor, formatDate,
} from '@/lib/api';

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

      performSearch(params);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, category, decision, yearFrom, yearTo, locationFilter, applicantFilter, sort, page, performSearch]);

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
  };

  const hasActiveFilters = category || decision || yearFrom || yearTo || locationFilter || applicantFilter;

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 25 }, (_, i) => currentYear - i);

  return (
    <main className="min-h-screen">
      {/* ── Navigation ──────────────────────────────────── */}
      <nav className="hero-gradient" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
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
            <Link href="/admin" className="nav-link">
              <Settings className="w-4 h-4" />
              <span className="hidden sm:inline">Admin</span>
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero Search ──────────────────────────────────── */}
      <section className="hero-gradient py-16 md:py-24">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h1 className="text-3xl md:text-5xl text-white mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
            Dublin Planning
            <span className="block text-[var(--teal)]">Intelligence</span>
          </h1>
          <p className="text-sm md:text-base text-white/50 mb-8 max-w-xl mx-auto font-light">
            Search 200,000+ Dublin City Council planning applications.
            AI-classified, company-enriched, and document-linked.
          </p>

          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              ref={searchInputRef}
              type="text"
              className="search-input pl-12 pr-16"
              placeholder="Search by address, applicant, description..."
              value={query}
              onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            />
            <kbd className="absolute right-4 top-1/2 -translate-y-1/2 text-white/30 text-xs border border-white/20 rounded px-1.5 py-0.5">
              /
            </kbd>
          </div>

          {/* Quick stats */}
          {results && (
            <div className="mt-4 flex items-center justify-center gap-4 text-sm text-white/40">
              <span>
                <strong className="text-white/70">{results.total.toLocaleString()}</strong> results
              </span>
              {results.query_time_ms && (
                <span>{results.query_time_ms.toFixed(0)}ms</span>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ── Content ──────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-4 py-6">
        {/* Filter bar */}
        <div className="filter-panel mb-6">
          <select
            className="filter-select"
            value={category}
            onChange={(e) => { setCategory(e.target.value); setPage(1); }}
          >
            <option value="">All Categories</option>
            {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>

          <select
            className="filter-select"
            value={decision}
            onChange={(e) => { setDecision(e.target.value); setPage(1); }}
          >
            {DECISIONS.map(d => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>

          <select
            className="filter-select"
            value={yearFrom}
            onChange={(e) => { setYearFrom(e.target.value); setPage(1); }}
          >
            <option value="">From Year</option>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          <select
            className="filter-select"
            value={yearTo}
            onChange={(e) => { setYearTo(e.target.value); setPage(1); }}
          >
            <option value="">To Year</option>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          <button
            className="btn-secondary"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="w-4 h-4" />
            More Filters
            <ChevronDown className={`w-3 h-3 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
          </button>

          <select
            className="filter-select ml-auto"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            {SORT_OPTIONS.map(s => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>

          {hasActiveFilters && (
            <button className="btn-secondary text-red-500" onClick={clearFilters}>
              <X className="w-3 h-3" />
              Clear
            </button>
          )}
        </div>

        {/* Extended filters */}
        {showFilters && (
          <div className="filter-panel mb-6 fade-in">
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider block mb-1">Applicant Name</label>
              <input
                type="text"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--warm-white)] text-sm focus:outline-none focus:border-[var(--teal)]"
                placeholder="Search applicant..."
                value={applicantFilter}
                onChange={(e) => { setApplicantFilter(e.target.value); setPage(1); }}
              />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider block mb-1">Location</label>
              <input
                type="text"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--warm-white)] text-sm focus:outline-none focus:border-[var(--teal)]"
                placeholder="Search location..."
                value={locationFilter}
                onChange={(e) => { setLocationFilter(e.target.value); setPage(1); }}
              />
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700 text-sm">
            {error}
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
            <Link
              key={app.id}
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
              </div>
            </Link>
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
            <button className="btn-secondary">
              <Download className="w-4 h-4" />
              Export CSV ({Math.min(results.total, 5000).toLocaleString()} rows)
            </button>
          </div>
        )}
      </section>

      {/* ── Footer ──────────────────────────────────────── */}
      <footer className="border-t border-[var(--border)] py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-[var(--text-muted)]">
          <p>PlanSearch — Dublin Planning Intelligence Platform</p>
          <p className="mt-1">
            Data sourced from Dublin City Council Open Data (CC BY 4.0).
            AI classification powered by Claude.
          </p>
        </div>
      </footer>
    </main>
  );
}
