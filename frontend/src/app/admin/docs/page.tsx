'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, FileText, Play, Square, Settings,
  Search, TrendingUp, BookOpen, Map as MapIcon, RefreshCw, BarChart3 } from 'lucide-react';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

interface DocScraperProgress {
  running: boolean;
  scraped_today: number;
  documents_found_today: number;
  last_ref: string | null;
  started_at: string | null;
  error: string | null;
}

export default function DocsPage() {
  const [token, setToken] = useState('');
  const [progress, setProgress] = useState<DocScraperProgress | null>(null);
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
      const res = await fetch(`${API_BASE}/api/admin/scrape/docs/progress`, {
        headers: { Authorization: `Bearer ${t || token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setProgress(data);
      }
    } catch {}
  }, [token]);

  // Poll every 15 seconds when running
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

  const handleStart = async () => {
    setMessage('');
    try {
      const res = await fetch(`${API_BASE}/api/admin/scrape/docs/start`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setMessage(data.status === 'already_running' ? 'Already running' : 'Document scraper started');
      setTimeout(() => fetchProgress(), 1000);
    } catch {
      setMessage('Failed to start');
    }
  };

  const handleStop = async () => {
    setMessage('');
    try {
      await fetch(`${API_BASE}/api/admin/scrape/docs/stop`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      setMessage('Document scraper stopped');
      setTimeout(() => fetchProgress(), 1000);
    } catch {
      setMessage('Failed to stop');
    }
  };

  const isRunning = progress?.running ?? false;

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

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '1.5rem', fontFamily: "'Playfair Display', serif" }}>
          <FileText style={{ display: 'inline', width: '1.25rem', height: '1.25rem', marginRight: '0.5rem', verticalAlign: 'middle' }} />
          Document Scraping
        </h1>

        {/* Live Status */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4" style={{ marginBottom: '1.25rem' }}>
          <div className="stat-card">
            <div className="stat-value text-2xl">
              {isRunning
                ? <span style={{ color: '#22c55e' }}>● Running</span>
                : <span style={{ color: '#ef4444' }}>● Stopped</span>
              }
            </div>
            <div className="stat-label">Status</div>
          </div>
          <div className="stat-card">
            <div className="stat-value text-2xl">{progress?.scraped_today?.toLocaleString() ?? '0'}</div>
            <div className="stat-label">Apps Scraped Today</div>
          </div>
          <div className="stat-card">
            <div className="stat-value text-2xl">{progress?.documents_found_today?.toLocaleString() ?? '0'}</div>
            <div className="stat-label">Documents Found Today</div>
          </div>
          <div className="stat-card">
            <div className="stat-value text-lg" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem', wordBreak: 'break-all' }}>
              {progress?.last_ref || '—'}
            </div>
            <div className="stat-label">Last Ref</div>
          </div>
        </div>

        {/* Controls */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <h3 className="text-base font-semibold mb-4">Scraper Controls</h3>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Scrapes document metadata (names, types, download URLs) from ePlanning.ie
            and Agile Applications portals using <code>link_app_details</code> from the database.
            Rate limited to 1 request every 3 seconds. Prioritises 2023+ applications.
          </p>
          <div className="flex items-center gap-4">
            {!isRunning ? (
              <button className="btn-primary" onClick={handleStart}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                <Play className="w-4 h-4" /> Start Document Scraper
              </button>
            ) : (
              <button className="btn-primary" onClick={handleStop}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: '#ef4444' }}>
                <Square className="w-4 h-4" /> Stop Scraper
              </button>
            )}
            <button className="text-sm text-[var(--text-muted)]" onClick={() => fetchProgress()}
              style={{ border: 'none', background: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
          {message && <p className="text-sm text-green-600 mt-3">{message}</p>}
          {progress?.error && (
            <p className="text-sm text-red-600 mt-3">Error: {progress.error}</p>
          )}
          {progress?.started_at && (
            <p className="text-xs text-[var(--text-muted)] mt-2">
              Started: {new Date(progress.started_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
