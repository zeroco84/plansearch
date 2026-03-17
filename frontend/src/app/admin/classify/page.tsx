'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, Zap, Play } from 'lucide-react';
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
    <main className="min-h-screen bg-[var(--warm-white)]">
      <nav className="hero-gradient" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2 text-white no-underline">
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <span className="text-white/30">|</span>
          <span className="text-white/70 text-sm">AI Classification</span>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-6">
        <Link href="/admin" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--teal)] mb-6 no-underline">
          <ArrowLeft className="w-4 h-4" /> Back to Admin
        </Link>

        <h1 className="text-2xl mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>AI Classification</h1>

        {status && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
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

        <div className="admin-card mb-6">
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
