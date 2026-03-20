'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, Settings, Search, TrendingUp, BookOpen,
  Map as MapIcon, RefreshCw, Play, Square, Download, Clock, BarChart3 } from 'lucide-react';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

interface CorkProgress {
  running: boolean;
  mode: string | null;
  scraped_today: number;
  records_found_today: number;
  last_ref: string | null;
  current_window: string | null;
  windows_done: number;
  total_windows: number;
  started_at: string | null;
  error: string | null;
}

export default function CorkScraperPage() {
  const [token, setToken] = useState('');
  const [progress, setProgress] = useState<CorkProgress | null>(null);
  const [message, setMessage] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      fetchProgress(saved);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const fetchProgress = useCallback(async (t?: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/scrape/cork/progress`, {
        headers: { Authorization: `Bearer ${t || token}` },
      });
      if (res.ok) setProgress(await res.json());
    } catch {}
  }, [token]);

  useEffect(() => {
    if (progress?.running) {
      pollRef.current = setInterval(() => fetchProgress(), 15000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [progress?.running, fetchProgress]);

  const apiCall = async (endpoint: string) => {
    setMessage('');
    try {
      const res = await fetch(`${API_BASE}/api/admin/scrape/cork/${endpoint}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setMessage(data.message || data.status || 'OK');
      setTimeout(() => fetchProgress(), 2000);
    } catch {
      setMessage('Request failed');
    }
  };

  const isRunning = progress?.running ?? false;
  const backfillProgress = progress?.total_windows
    ? Math.round((progress.windows_done / progress.total_windows) * 100)
    : 0;

  return (
    <main style={{ minHeight: '100vh', background: '#f9f8f6' }}>
      <nav style={{ background: '#0d1117', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '64px', padding: '0 2rem', width: '100%' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'white', textDecoration: 'none' }}>
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span style={{ color: 'white', fontSize: '1.125rem', fontWeight: '600', letterSpacing: '-0.01em', fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Link href="/" className="nav-link"><Search className="w-5 h-5" /><span className="hidden sm:inline">Search</span></Link>
            <Link href="/map" className="nav-link"><MapIcon className="w-5 h-5" /><span className="hidden sm:inline">Map</span></Link>
            <Link href="/significant" className="nav-link"><TrendingUp className="w-5 h-5" /><span className="hidden sm:inline">Significant</span></Link>
            <Link href="/analytics" className="nav-link"><BarChart3 className="w-5 h-5" /><span className="hidden sm:inline">Analytics</span></Link>
            <Link href="/blog" className="nav-link"><BookOpen className="w-5 h-5" /><span className="hidden sm:inline">Blog</span></Link>
            <Link href="/admin" className="nav-link" style={{ color: 'var(--teal)' }}><Settings className="w-5 h-5" /><span className="hidden sm:inline">Admin</span></Link>
          </div>
        </div>
      </nav>

      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem 2rem 4rem' }}>
        <Link href="/admin" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.875rem', color: 'var(--text-muted)', textDecoration: 'none', marginBottom: '1.5rem' }}>
          <ArrowLeft className="w-4 h-4" /> Back to Admin
        </Link>

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '0.5rem', fontFamily: "'Playfair Display', serif" }}>
          🏛️ Cork County Council Scraper
        </h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
          Scrapes planning applications from Cork County Council&apos;s ePlan portal (planning.corkcoco.ie).
          Cork County is Ireland&apos;s largest council by area and is not covered by NPAD.
          Records are geocoded automatically by the Nominatim geocoder.
        </p>

        {/* Progress Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4" style={{ marginBottom: '1.25rem' }}>
          <div className="stat-card">
            <div className="stat-value text-2xl">
              {isRunning
                ? <span style={{ color: '#22c55e' }}>● {progress?.mode === 'backfill' ? 'Backfill' : 'Running'}</span>
                : <span style={{ color: '#6b7280' }}>● Idle</span>
              }
            </div>
            <div className="stat-label">Status</div>
          </div>
          <div className="stat-card">
            <div className="stat-value text-2xl">{progress?.records_found_today?.toLocaleString() ?? '0'}</div>
            <div className="stat-label">Records Found</div>
          </div>
          <div className="stat-card">
            <div className="stat-value text-2xl">{progress?.scraped_today?.toLocaleString() ?? '0'}</div>
            <div className="stat-label">Rows Processed</div>
          </div>
          <div className="stat-card">
            <div className="stat-value text-sm" style={{ wordBreak: 'break-all' }}>
              {progress?.last_ref || '—'}
            </div>
            <div className="stat-label">Last Ref</div>
          </div>
        </div>

        {/* Backfill progress */}
        {progress?.mode === 'backfill' && progress.total_windows > 0 && (
          <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1rem 1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              <span>Backfill Progress</span>
              <span>{progress.windows_done}/{progress.total_windows} windows ({backfillProgress}%)</span>
            </div>
            <div className="progress-bar" style={{ height: '8px', background: 'var(--border)', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${backfillProgress}%`, background: 'var(--teal)', borderRadius: '4px', transition: 'width 0.5s ease' }} />
            </div>
            {progress.current_window && (
              <div className="text-xs text-[var(--text-muted)] mt-2">
                <Clock className="w-3 h-3 inline mr-1" />
                Current window: {progress.current_window}
              </div>
            )}
          </div>
        )}

        {/* Controls */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <h3 className="text-base font-semibold mb-4">Scraper Controls</h3>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            <strong>Continuous</strong> scrapes the latest 42-day window every 4 hours during off-peak (8pm–8am).
            <strong> Backfill</strong> walks back 2 years in 42-day chunks (~25,000–30,000 records).
            Rate limit: 1 request per 2 seconds. User-Agent identifies PlanSearch.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <button
              className="btn-primary"
              onClick={() => apiCall('start')}
              disabled={isRunning}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <Play className="w-4 h-4" /> Start Continuous
            </button>
            <button
              className="btn-secondary"
              onClick={() => apiCall('backfill')}
              disabled={isRunning}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <Download className="w-4 h-4" /> Run 2-Year Backfill
            </button>
            <button
              className="btn-secondary"
              onClick={() => apiCall('stop')}
              disabled={!isRunning}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', opacity: isRunning ? 1 : 0.5 }}
            >
              <Square className="w-4 h-4" /> Stop
            </button>
            <button
              className="text-sm text-[var(--text-muted)]"
              onClick={() => fetchProgress()}
              style={{ border: 'none', background: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
            >
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
          {message && <p className="text-sm text-green-600 mt-3">{message}</p>}
          {progress?.error && <p className="text-sm text-red-600 mt-3">Error: {progress.error}</p>}
          {progress?.started_at && (
            <p className="text-xs text-[var(--text-muted)] mt-2">
              Started: {new Date(progress.started_at).toLocaleString()}
            </p>
          )}
        </div>

        {/* Data source info */}
        <div className="admin-card" style={{ padding: '1.5rem' }}>
          <h3 className="text-base font-semibold mb-3">Data Source Details</h3>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0', fontWeight: 600 }}>Field</th>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0', fontWeight: 600 }}>Value</th>
                </tr>
              </thead>
              <tbody>
                <tr><td style={{ padding: '0.35rem 0' }}>Source</td><td>Cork County ePlan (planning.corkcoco.ie)</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Licence</td><td>LGMA public planning register</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Coordinates</td><td>None — geocoded via OSM Nominatim (~60-70% success)</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Applicant Names</td><td>✅ Available in listing (unlike NPAD)</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Update Frequency</td><td>Continuous (scraper-driven, off-peak)</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Rate Limit</td><td>2s between requests, 8pm–8am Irish time</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>data_source value</td><td><code>CORKCOCO_EPLAN</code></td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>reg_ref prefix</td><td><code>CC/</code></td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Est. backfill volume</td><td>~25,000–30,000 records (2 years)</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}
