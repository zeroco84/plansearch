'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, FileText, Play, Pause, RefreshCw, Settings, Search, TrendingUp, BookOpen, Map as MapIcon } from 'lucide-react';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

export default function DocsPage() {
  const [token, setToken] = useState('');
  const [status, setStatus] = useState<any>(null);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState('');
  const [sseMessages, setSseMessages] = useState<string[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) { setToken(saved); loadStatus(saved); }
    return () => { eventSourceRef.current?.close(); };
  }, []);

  const loadStatus = async (t: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/docs/status`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (res.ok) setStatus(await res.json());
    } catch {}
  };

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/docs/trigger`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setMessage(data.message || 'Document scraping triggered');
      startSSE();
      setTimeout(() => loadStatus(token), 5000);
    } catch { setMessage('Failed to trigger'); }
    setTriggering(false);
  };

  const startSSE = () => {
    if (eventSourceRef.current) eventSourceRef.current.close();

    const es = new EventSource(`${API_BASE}/api/admin/stream?token=${token}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      setSseMessages((prev) => [...prev.slice(-50), event.data]);
    };

    es.onerror = () => {
      es.close();
    };
  };

  const scrapedPct = status
    ? Math.round((status.total_scraped / Math.max(status.total_applications, 1)) * 100)
    : 0;

  const estimatedHours = status && status.total_applications - status.total_scraped > 0
    ? Math.round(((status.total_applications - status.total_scraped) * 3) / 3600)
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
            <Link href="/insights" className="nav-link"><BookOpen className="w-5 h-5" /><span className="hidden sm:inline">Insights</span></Link>
            <Link href="/admin" className="nav-link" style={{ color: 'var(--teal)' }}><Settings className="w-5 h-5" /><span className="hidden sm:inline">Admin</span></Link>
          </div>
        </div>
      </nav>

      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem 2rem 4rem' }}>
        <Link href="/admin" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.875rem', color: 'var(--text-muted)', textDecoration: 'none', marginBottom: '1.5rem' }}>
          <ArrowLeft className="w-4 h-4" /> Back to Admin
        </Link>

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '1.5rem', fontFamily: "'Playfair Display', serif" }}>Document Scraping</h1>

        {/* Status cards */}
        {status && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4" style={{ marginBottom: '1.25rem' }}>
            <div className="stat-card">
              <div className="stat-value text-2xl">{status.total_applications?.toLocaleString()}</div>
              <div className="stat-label">Total Applications</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-2xl">{status.total_scraped?.toLocaleString()}</div>
              <div className="stat-label">Docs Scraped</div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${scrapedPct}%` }} />
              </div>
              <div className="text-xs text-white/40 mt-1">{scrapedPct}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-2xl">{status.total_documents?.toLocaleString()}</div>
              <div className="stat-label">Documents Found</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-2xl">~{estimatedHours}h</div>
              <div className="stat-label">Est. Remaining</div>
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <h3 className="text-base font-semibold mb-4">Scraper Controls</h3>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Scrapes document metadata (names, types, download URLs) from both the Agile Applications portal (pre-2024) and the National Planning Portal (post-2024).
            Rate limited to 1 request every 3 seconds.
          </p>
          <div className="flex items-center gap-4">
            <button className="btn-primary" onClick={handleTrigger} disabled={triggering}>
              {triggering ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {triggering ? 'Running...' : 'Run Document Scraping'}
            </button>
            <div className="text-sm text-[var(--text-muted)]">
              Rate limit: 1 req / 3 seconds
            </div>
          </div>
          {message && <p className="text-sm text-green-600 mt-3">{message}</p>}
        </div>

        {/* SSE Live Feed */}
        {sseMessages.length > 0 && (
          <div className="admin-card">
            <h3 className="text-base font-semibold mb-4">Live Progress</h3>
            <div className="bg-[var(--charcoal)] rounded-lg p-4 max-h-64 overflow-y-auto font-mono text-xs text-green-400">
              {sseMessages.map((msg, i) => (
                <div key={i} className="py-0.5">{msg}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
