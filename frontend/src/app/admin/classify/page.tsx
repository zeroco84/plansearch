'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, Zap, Settings, Search, TrendingUp, BookOpen,
  Map as MapIcon, Square,
} from 'lucide-react';
import {
  triggerClassification, getClassifyStatus, fetchClassifyProgress,
  stopClassify, CATEGORY_LABELS,
} from '@/lib/api';

interface ClassifyProgress {
  running: boolean;
  processed: number;
  errors: number;
  total: number;
  started_at: string | null;
  stop_requested: boolean;
}

export default function ClassifyPage() {
  const [token, setToken] = useState('');
  const [status, setStatus] = useState<any>(null);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState('');
  const [progress, setProgress] = useState<ClassifyProgress | null>(null);
  const [polling, setPolling] = useState(false);
  const pollingRef = useRef(false);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      loadStatus(saved);
      checkExistingProgress(saved);
    }
  }, []);

  // Polling effect
  useEffect(() => {
    pollingRef.current = polling;
    if (!polling || !token) return;

    const interval = setInterval(async () => {
      if (!pollingRef.current) return;
      try {
        const prog = await fetchClassifyProgress(token) as ClassifyProgress;
        setProgress(prog);
        if (!prog.running) {
          setPolling(false);
          pollingRef.current = false;
          startTimeRef.current = null;
          loadStatus(token);
        }
      } catch {
        setPolling(false);
        pollingRef.current = false;
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [polling, token]);

  const checkExistingProgress = async (t: string) => {
    try {
      const prog = await fetchClassifyProgress(t) as ClassifyProgress;
      if (prog.running) {
        setProgress(prog);
        setPolling(true);
        startTimeRef.current = prog.started_at ? new Date(prog.started_at).getTime() : Date.now();
      }
    } catch {}
  };

  const loadStatus = async (t: string) => {
    try {
      const data = await getClassifyStatus(t);
      setStatus(data);
    } catch {}
  };

  const handleTrigger = async () => {
    setTriggering(true);
    setMessage('');
    try {
      await triggerClassification(token);
      setMessage('Classification triggered — 50 concurrent requests');
      startTimeRef.current = Date.now();
      setProgress({
        running: true, processed: 0, errors: 0, total: 0,
        started_at: new Date().toISOString(), stop_requested: false,
      });
      setPolling(true);
    } catch {
      setMessage('Failed to trigger classification');
    }
    setTriggering(false);
  };

  // Calculate rate and ETA
  const getRate = () => {
    if (!progress || !startTimeRef.current || progress.processed === 0) return null;
    const elapsed = (Date.now() - startTimeRef.current) / 1000;
    if (elapsed < 3) return null;
    return progress.processed / elapsed;
  };

  const getEta = () => {
    const rate = getRate();
    if (!rate || !progress || progress.total === 0) return null;
    const remaining = progress.total - progress.processed;
    if (remaining <= 0) return null;
    const seconds = remaining / rate;
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  const rate = getRate();

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
          <ArrowLeft style={{ width: '16px', height: '16px' }} /> Back to Admin
        </Link>

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '1.5rem', fontFamily: "'Playfair Display', serif" }}>AI Classification</h1>

        {message && (
          <div style={{ marginBottom: '1.25rem', padding: '0.75rem 1rem', background: '#ecfdf5', borderRadius: '8px', fontSize: '0.875rem', color: '#065f46', border: '1px solid #a7f3d0' }}>
            {message}
          </div>
        )}

        {/* Stats Cards */}
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

        {/* Live Progress Counter */}
        {progress?.running && (
          <div style={{
            marginBottom: '1.25rem', padding: '1.25rem 1.5rem',
            background: '#f5f3ff', border: '1px solid #7c3aed', borderRadius: '10px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                  <div style={{
                    width: '10px', height: '10px', borderRadius: '50%',
                    background: '#7c3aed', animation: 'classifyPulse 1.2s ease-in-out infinite',
                  }} />
                  <span style={{ fontSize: '0.9rem', fontWeight: '600', color: '#4c1d95' }}>
                    Classifying — 50 concurrent requests
                  </span>
                </div>
                <div style={{ fontSize: '2rem', fontWeight: '700', color: '#7c3aed', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                  {progress.processed.toLocaleString()}
                  {progress.total > 0 && (
                    <span style={{ fontSize: '1rem', fontWeight: '400', color: '#9ca3af' }}>
                      {' '}/ {progress.total.toLocaleString()}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '4px' }}>
                  records classified
                  {progress.errors > 0 && (
                    <span style={{ color: '#dc2626', marginLeft: '12px' }}>
                      {progress.errors.toLocaleString()} errors
                    </span>
                  )}
                  {rate && (
                    <span style={{ marginLeft: '12px', color: '#7c3aed' }}>
                      {rate.toFixed(1)}/sec
                    </span>
                  )}
                  {getEta() && (
                    <span style={{ marginLeft: '12px' }}>
                      ~{getEta()} remaining
                    </span>
                  )}
                </div>
                {progress.started_at && (
                  <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '6px' }}>
                    Started {new Date(progress.started_at).toLocaleTimeString('en-IE')}
                  </div>
                )}

                {/* Progress bar */}
                {progress.total > 0 && (
                  <div style={{
                    marginTop: '10px', height: '6px', background: '#e5e7eb',
                    borderRadius: '3px', overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%', background: '#7c3aed', borderRadius: '3px',
                      width: `${Math.min(100, (progress.processed / progress.total) * 100)}%`,
                      transition: 'width 0.5s ease',
                    }} />
                  </div>
                )}
              </div>
              <button
                onClick={async () => {
                  try {
                    await stopClassify(token);
                    setMessage('Stop requested — classification will halt after current batch');
                  } catch {}
                }}
                style={{
                  padding: '0.5rem 1rem', background: '#dc2626', color: 'white',
                  border: 'none', borderRadius: '8px', cursor: 'pointer',
                  fontSize: '0.8rem', fontWeight: '600',
                  display: 'flex', alignItems: 'center', gap: '0.35rem',
                  flexShrink: 0,
                }}
              >
                <Square style={{ width: '14px', height: '14px' }} />
                Stop
              </button>
            </div>
          </div>
        )}

        {/* Completion banner */}
        {progress && !progress.running && progress.processed > 0 && (
          <div style={{
            marginBottom: '1.25rem', padding: '1rem 1.25rem',
            background: '#f5f3ff', border: '1px solid #7c3aed', borderRadius: '10px',
          }}>
            <span style={{ color: '#4c1d95', fontWeight: '600' }}>
              ✓ Classification complete — {progress.processed.toLocaleString()} records classified
              {progress.errors > 0 && ` (${progress.errors} errors)`}
            </span>
          </div>
        )}

        {/* Trigger Button */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Zap style={{ width: '18px', height: '18px', color: '#7c3aed' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0 }}>AI Classification</h3>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Classify all unclassified planning applications using Claude Haiku.
            Runs 50 concurrent requests for maximum throughput.
            {status && status.total_unclassified > 0 && (
              <span style={{ display: 'block', marginTop: '0.5rem', color: '#7c3aed', fontWeight: '500' }}>
                {status.total_unclassified.toLocaleString()} records waiting
                {' '}— estimated cost: ~${(status.total_unclassified * 0.0003).toFixed(2)}
              </span>
            )}
          </p>
          <button
            className="btn-primary"
            onClick={handleTrigger}
            disabled={triggering || (progress?.running ?? false)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: '#7c3aed' }}
          >
            <Zap style={{ width: '16px', height: '16px' }} />
            {triggering ? 'Starting...' : progress?.running ? 'Running...' : 'Classify All Unclassified'}
          </button>
        </div>

        {/* Category Breakdown */}
        {status?.categories && Object.keys(status.categories).length > 0 && (
          <div className="admin-card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>Category Breakdown</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {Object.entries(status.categories as Record<string, number>)
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .map(([cat, count]) => {
                  const pct = status.total_classified > 0 ? ((count as number) / status.total_classified * 100) : 0;
                  return (
                    <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', width: '140px', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {CATEGORY_LABELS[cat] || cat}
                      </span>
                      <div style={{ flex: 1, height: '8px', background: 'var(--warm-white-dark)', borderRadius: '4px', overflow: 'hidden' }}>
                        <div style={{ height: '100%', background: 'var(--teal)', borderRadius: '4px', width: `${pct}%` }} />
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', width: '60px', textAlign: 'right', flexShrink: 0 }}>
                        {(count as number).toLocaleString()}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        @keyframes classifyPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.3); }
        }
      `}</style>
    </main>
  );
}
