'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, RefreshCw, Play, CheckCircle, XCircle, Square,
  Settings, Search, TrendingUp, BookOpen, Map as MapIcon, Building2, BarChart3 } from 'lucide-react';
import { triggerNpadSync, triggerBcmsSync, triggerSubstackSync, fetchSyncProgress, stopSync, getSyncStatus, getAdminLogs } from '@/lib/api';

interface SyncProgress {
  running: boolean;
  processed: number;
  errors: number;
  started_at: string | null;
  source: string | null;
}

export default function SyncPage() {
  const [token, setToken] = useState('');
  const [syncStatus, setSyncStatus] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [triggeringNpad, setTriggeringNpad] = useState(false);
  const [triggeringBcms, setTriggeringBcms] = useState(false);
  const [triggeringSubstack, setTriggeringSubstack] = useState(false);
  const [message, setMessage] = useState('');
  const [progress, setProgress] = useState<SyncProgress | null>(null);
  const [polling, setPolling] = useState(false);
  const pollingRef = useRef(false);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      loadData(saved);
      // Check if a sync is already running on page load
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
        const prog = await fetchSyncProgress(token) as SyncProgress;
        setProgress(prog);
        if (!prog.running) {
          setPolling(false);
          pollingRef.current = false;
          loadData(token);
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
      const prog = await fetchSyncProgress(t) as SyncProgress;
      if (prog.running) {
        setProgress(prog);
        setPolling(true);
      }
    } catch {}
  };

  const loadData = async (t: string) => {
    try {
      const [status, logData] = await Promise.all([
        getSyncStatus(t).catch(() => null),
        getAdminLogs(t, 20).catch(() => []),
      ]);
      if (status) setSyncStatus(status);
      if (Array.isArray(logData)) setLogs(logData);
    } catch (err) {
      console.error(err);
    }
  };

  const handleNpadSync = async () => {
    setTriggeringNpad(true);
    setMessage('');
    try {
      await triggerNpadSync(token);
      setMessage('NPAD sync triggered');
      setProgress({ running: true, processed: 0, errors: 0, started_at: new Date().toISOString(), source: 'npad' });
      setPolling(true);
    } catch {
      setMessage('Failed to trigger NPAD sync');
    } finally {
      setTriggeringNpad(false);
    }
  };

  const handleBcmsSync = async () => {
    setTriggeringBcms(true);
    setMessage('');
    try {
      await triggerBcmsSync(token);
      setMessage('BCMS sync triggered');
      setProgress({ running: true, processed: 0, errors: 0, started_at: new Date().toISOString(), source: 'bcms' });
      setPolling(true);
    } catch {
      setMessage('Failed to trigger BCMS sync');
    } finally {
      setTriggeringBcms(false);
    }
  };

  const handleSubstackSync = async () => {
    setTriggeringSubstack(true);
    setMessage('');
    try {
      await triggerSubstackSync(token);
      setMessage('Substack sync triggered — posts loading in background');
    } catch {
      setMessage('Failed to trigger Substack sync');
    } finally {
      setTriggeringSubstack(false);
    }
  };

  const sourceLabel = progress?.source === 'bcms' ? 'BCMS' : 'NPAD';

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
          <ArrowLeft style={{ width: '16px', height: '16px' }} /> Back to Admin
        </Link>

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '2rem', fontFamily: "'Playfair Display', serif" }}>Data Sync Controls</h1>

        {message && (
          <div style={{ marginBottom: '1.25rem', padding: '0.75rem 1rem', background: '#ecfdf5', borderRadius: '8px', fontSize: '0.875rem', color: '#065f46', border: '1px solid #a7f3d0' }}>
            {message}
          </div>
        )}

        {/* Live Progress Counter */}
        {progress?.running && (
          <div style={{
            marginBottom: '1.25rem', padding: '1.25rem 1.5rem',
            background: '#f0fdfb', border: '1px solid #1d9e75', borderRadius: '10px',
          }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <div style={{
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: '#1d9e75', animation: 'syncPulse 1.2s ease-in-out infinite',
                }} />
                <span style={{ fontSize: '0.9rem', fontWeight: '600', color: '#065f46' }}>
                  {sourceLabel} sync running...
                </span>
              </div>
              <div style={{ fontSize: '2rem', fontWeight: '700', color: '#1d9e75', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                {progress.processed.toLocaleString()}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '4px' }}>
                records loaded
                {progress.errors > 0 && (
                  <span style={{ color: '#dc2626', marginLeft: '12px' }}>
                    {progress.errors.toLocaleString()} errors
                  </span>
                )}
              </div>
              {progress.started_at && (
                <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '6px' }}>
                  Started {new Date(progress.started_at).toLocaleTimeString('en-IE')}
                </div>
              )}
            </div>
            <button
              onClick={async () => {
                try {
                  await stopSync(token);
                  setMessage('Stop requested — sync will halt after current batch');
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
            background: '#f0fdfb', border: '1px solid #1d9e75', borderRadius: '10px',
          }}>
            <span style={{ color: '#065f46', fontWeight: '600' }}>
              ✓ Sync complete — {progress.processed.toLocaleString()} records loaded
            </span>
          </div>
        )}

        {/* NPAD Sync */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Database style={{ width: '18px', height: '18px', color: 'var(--teal)' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0 }}>NPAD — Planning Applications</h3>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Download all Irish planning applications from the National Planning Application Database (NPAD) ArcGIS API.
            Covers 30/31 local authorities, ~362,000 applications. Updated weekly.
          </p>
          <button
            className="btn-primary"
            onClick={handleNpadSync}
            disabled={triggeringNpad || (progress?.running ?? false)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            {triggeringNpad ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Play style={{ width: '16px', height: '16px' }} />}
            {triggeringNpad ? 'Starting...' : progress?.running && progress?.source === 'npad' ? 'Running...' : 'Trigger NPAD Sync'}
          </button>
        </div>

        {/* BCMS Sync */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Building2 style={{ width: '18px', height: '18px', color: '#f59e0b' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0 }}>BCMS — Building Control</h3>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Download commencement notices and Fire Safety Certificate applications from the Building Control Management System.
            Links construction activity to planning permissions and updates lifecycle stages.
          </p>
          <button
            className="btn-primary"
            onClick={handleBcmsSync}
            disabled={triggeringBcms || (progress?.running ?? false)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: '#f59e0b' }}
          >
            {triggeringBcms ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Play style={{ width: '16px', height: '16px' }} />}
            {triggeringBcms ? 'Starting...' : progress?.running && progress?.source === 'bcms' ? 'Running...' : 'Trigger BCMS Sync'}
          </button>
        </div>

        {/* Substack Sync */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <BookOpen style={{ width: '18px', height: '18px', color: '#FF6719' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0 }}>The Build — Substack Posts</h3>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Sync latest posts from The Build newsletter RSS feed. Updates the Insights page.
            Also syncs automatically on server startup and every 6 hours.
          </p>
          <button
            className="btn-primary"
            onClick={handleSubstackSync}
            disabled={triggeringSubstack}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: '#FF6719' }}
          >
            {triggeringSubstack ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Play style={{ width: '16px', height: '16px' }} />}
            {triggeringSubstack ? 'Syncing...' : 'Sync Substack Posts'}
          </button>
        </div>

        {/* Last Sync Status */}
        {syncStatus && (
          <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>Last Sync</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>Source</div>
                <div style={{ fontSize: '0.875rem', fontWeight: '600' }}>{syncStatus.sync_type || '—'}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>Status</div>
                <div style={{ fontSize: '0.875rem', fontWeight: '600', color: syncStatus.status === 'completed' ? '#16a34a' : syncStatus.status === 'running' ? '#2563eb' : '#dc2626', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  {syncStatus.status === 'completed' && <CheckCircle style={{ width: '16px', height: '16px' }} />}
                  {syncStatus.status === 'failed' && <XCircle style={{ width: '16px', height: '16px' }} />}
                  {syncStatus.status === 'running' && <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} />}
                  {syncStatus.status}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>Records</div>
                <div style={{ fontSize: '0.875rem', fontWeight: '600' }}>{syncStatus.records_processed?.toLocaleString() || '—'}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>Started</div>
                <div style={{ fontSize: '0.875rem' }}>{syncStatus.started_at ? new Date(syncStatus.started_at).toLocaleString() : '—'}</div>
              </div>
            </div>
            {syncStatus.error_message && (
              <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#fef2f2', borderRadius: '8px', fontSize: '0.875rem', color: '#b91c1c' }}>{syncStatus.error_message}</div>
            )}
          </div>
        )}

        {/* Sync Logs */}
        <div className="admin-card" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>Recent Sync Logs</h3>
          {logs.length === 0 ? (
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>No sync logs yet</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {logs.map((log: any, i: number) => (
                <div key={log.id || i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem', background: 'var(--warm-white)', borderRadius: '8px', fontSize: '0.875rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0, background: log.status === 'completed' ? '#22c55e' : log.status === 'running' ? '#3b82f6' : '#ef4444' }} />
                    <span style={{ fontWeight: '500' }}>{log.sync_type || 'sync'}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {log.records_processed != null && <span>{log.records_processed.toLocaleString()} records</span>}
                    <span>{log.started_at ? new Date(log.started_at).toLocaleString() : ''}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        @keyframes syncPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.3); }
        }
      `}</style>
    </main>
  );
}
