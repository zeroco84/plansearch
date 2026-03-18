'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, Zap, Play, Settings, Search, TrendingUp, BookOpen, Map as MapIcon } from 'lucide-react';
import { triggerClassification, getClassifyStatus, CATEGORY_LABELS } from '@/lib/api';

export default function ClassifyPage() {
  const [token, setToken] = useState('');
  const [status, setStatus] = useState<any>(null);
  const [batchSize, setBatchSize] = useState(100);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) { setToken(saved); loadStatus(saved); }
  }, []);

  const loadStatus = async (t: string) => {
    try {
      const data = await getClassifyStatus(t);
      setStatus(data);
    } catch {}
  };

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const result = await triggerClassification(token, batchSize) as any;
      setMessage(result.message || 'Classification triggered');
      setTimeout(() => loadStatus(token), 5000);
    } catch { setMessage('Failed to trigger'); }
    setTriggering(false);
  };

  const costEstimate = (batchSize * 0.0003).toFixed(2);

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

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '1.5rem', fontFamily: "'Playfair Display', serif" }}>AI Classification</h1>

        {status && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4" style={{ marginBottom: '1.25rem' }}>
            <div className="stat-card">
              <div className="stat-value text-2xl">{status.total_classified?.toLocaleString()}</div>
              <div className="stat-label">Classified</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-2xl">{status.total_unclassified?.toLocaleString()}</div>
              <div className="stat-label">Remaining</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-2xl">{status.total_applications?.toLocaleString()}</div>
              <div className="stat-label">Total</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-2xl">{status.percentage_classified}%</div>
              <div className="stat-label">Complete</div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${status.percentage_classified}%` }} />
              </div>
            </div>
          </div>
        )}

        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <h3 className="text-base font-semibold mb-4">Run Classification Batch</h3>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="text-xs text-[var(--text-muted)] uppercase block mb-1">Batch Size</label>
              <select
                className="filter-select"
                value={batchSize}
                onChange={(e) => setBatchSize(Number(e.target.value))}
              >
                <option value={100}>100 records</option>
                <option value={500}>500 records</option>
                <option value={1000}>1,000 records</option>
                <option value={5000}>5,000 records</option>
              </select>
            </div>
            <div className="text-sm text-[var(--text-muted)]">
              Estimated cost: ~${costEstimate}
            </div>
            <button className="btn-primary" onClick={handleTrigger} disabled={triggering}>
              <Zap className="w-4 h-4" />
              {triggering ? 'Running...' : 'Run Classification Batch'}
            </button>
          </div>
          {message && <p className="text-sm text-green-600 mt-3">{message}</p>}
        </div>

        {status?.categories && Object.keys(status.categories).length > 0 && (
          <div className="admin-card">
            <h3 className="text-base font-semibold mb-4">Category Breakdown</h3>
            <div className="space-y-2">
              {Object.entries(status.categories as Record<string, number>)
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .map(([cat, count]) => {
                  const pct = status.total_classified > 0 ? ((count as number) / status.total_classified * 100) : 0;
                  return (
                    <div key={cat} className="flex items-center gap-3">
                      <span className="text-xs text-[var(--text-muted)] w-32 truncate">{CATEGORY_LABELS[cat] || cat}</span>
                      <div className="flex-1 h-2 bg-[var(--warm-white-dark)] rounded-full overflow-hidden">
                        <div className="h-full bg-[var(--teal)] rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-[var(--text-muted)] w-16 text-right">{(count as number).toLocaleString()}</span>
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
