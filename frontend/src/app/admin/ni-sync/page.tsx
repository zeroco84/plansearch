'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, Settings, Search, TrendingUp, BookOpen,
  Map as MapIcon, RefreshCw, Play, Download,
, BarChart3 } from 'lucide-react';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

interface NISyncProgress {
  running: boolean;
  current_year: string | null;
  total_years: number;
  years_done: number;
  records_imported: number;
  errors: number;
  started_at: string | null;
  error: string | null;
}

export default function NISyncPage() {
  const [token, setToken] = useState('');
  const [progress, setProgress] = useState<NISyncProgress | null>(null);
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
      const res = await fetch(`${API_BASE}/api/admin/sync/ni/progress`, {
        headers: { Authorization: `Bearer ${t || token}` },
      });
      if (res.ok) setProgress(await res.json());
    } catch {}
  }, [token]);

  // Poll every 10s when running
  useEffect(() => {
    if (progress?.running) {
      pollRef.current = setInterval(() => fetchProgress(), 10000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [progress?.running, fetchProgress]);

  const handleSyncAll = async () => {
    setMessage('');
    try {
      const res = await fetch(`${API_BASE}/api/admin/sync/ni/all`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setMessage(data.message || data.status || 'NI sync started');
      setTimeout(() => fetchProgress(), 2000);
    } catch {
      setMessage('Failed to start sync');
    }
  };

  const handleSyncLatest = async () => {
    setMessage('');
    try {
      const res = await fetch(`${API_BASE}/api/admin/sync/ni/latest`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setMessage(data.message || data.status || 'NI latest year sync started');
      setTimeout(() => fetchProgress(), 2000);
    } catch {
      setMessage('Failed to start sync');
    }
  };

  const isRunning = progress?.running ?? false;
  const yearProgress = progress?.total_years
    ? Math.round((progress.years_done / progress.total_years) * 100)
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
          🇬🇧 Northern Ireland Sync
        </h1>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
          Downloads planning application CSVs from OpenDataNI. Covers 11 Local Planning Authorities
          and the Department for Infrastructure. Data published annually under Open Government Licence v3.0.
        </p>

        {/* Progress Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4" style={{ marginBottom: '1.25rem' }}>
          <div className="stat-card">
            <div className="stat-value text-2xl">
              {isRunning
                ? <span style={{ color: '#22c55e' }}>● Running</span>
                : <span style={{ color: '#6b7280' }}>● Idle</span>
              }
            </div>
            <div className="stat-label">Status</div>
          </div>
          <div className="stat-card">
            <div className="stat-value text-2xl">{progress?.records_imported?.toLocaleString() ?? '0'}</div>
            <div className="stat-label">Records Imported</div>
          </div>
          <div className="stat-card">
            <div className="stat-value text-2xl">{progress?.years_done ?? 0} / {progress?.total_years ?? 8}</div>
            <div className="stat-label">Years Processed</div>
            {isRunning && (
              <>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${yearProgress}%` }} />
                </div>
                <div className="text-xs text-white/40 mt-1">
                  {progress?.current_year ? `Processing ${progress.current_year}` : ''}
                </div>
              </>
            )}
          </div>
          <div className="stat-card">
            <div className="stat-value text-2xl" style={{ color: (progress?.errors ?? 0) > 0 ? '#ef4444' : '#22c55e' }}>
              {progress?.errors ?? 0}
            </div>
            <div className="stat-label">Errors</div>
          </div>
        </div>

        {/* Controls */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <h3 className="text-base font-semibold mb-4">Sync Controls</h3>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            <strong>Sync All Years</strong> downloads all 8 financial year CSVs (2017/18 → 2024/25) for a
            complete backfill of ~200,000 records. <strong>Sync Latest Year</strong> downloads only the
            most recent CSV. Coordinates are converted from Irish National Grid (EPSG:29903) to WGS84.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <button
              className="btn-primary"
              onClick={handleSyncAll}
              disabled={isRunning}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {isRunning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              {isRunning ? 'Syncing...' : 'Sync All Years'}
            </button>
            <button
              className="btn-secondary"
              onClick={handleSyncLatest}
              disabled={isRunning}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <Play className="w-4 h-4" /> Sync Latest Year
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
                <tr><td style={{ padding: '0.35rem 0' }}>Source</td><td>OpenDataNI (infrastructure-ni.gov.uk)</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Licence</td><td>Open Government Licence v3.0</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Coordinate System</td><td>Irish National Grid (EPSG:29903) → WGS84</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Update Frequency</td><td>Annual (published June/July)</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>Coverage</td><td>11 LPAs + Department for Infrastructure</td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>data_source value</td><td><code>NIDFT</code></td></tr>
                <tr><td style={{ padding: '0.35rem 0' }}>reg_ref prefix</td><td><code>NI/</code></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}
