'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, FileText, Play, Pause, RefreshCw } from 'lucide-react';

const API_BASE = typeof window === 'undefined'
  ? 'https://api.plansearch.cc'
  : (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://api.plansearch.cc';

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
    <main className="min-h-screen bg-[var(--warm-white)]">
      <nav className="hero-gradient" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2 text-white no-underline">
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <span className="text-white/30">|</span>
          <span className="text-white/70 text-sm">Document Scraping</span>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-6">
        <Link href="/admin" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--teal)] mb-6 no-underline">
          <ArrowLeft className="w-4 h-4" /> Back to Admin
        </Link>

        <h1 className="text-2xl mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>Document Scraping</h1>

        {/* Status cards */}
        {status && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
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
        <div className="admin-card mb-6">
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
