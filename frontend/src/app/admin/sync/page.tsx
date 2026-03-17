'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, RefreshCw, Play, CheckCircle, XCircle, Clock, Settings, Search, TrendingUp, BookOpen, Map as MapIcon } from 'lucide-react';
import { triggerSync, getSyncStatus, getAdminLogs } from '@/lib/api';

export default function SyncPage() {
  const [token, setToken] = useState('');
  const [syncStatus, setSyncStatus] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      loadData(saved);
    }
  }, []);

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

  const handleTriggerSync = async () => {
    setTriggering(true);
    setMessage('');
    try {
      const result = await triggerSync(token) as any;
      setMessage(result.message || 'Sync triggered successfully');
      setTimeout(() => loadData(token), 3000);
    } catch (err) {
      setMessage('Failed to trigger sync');
    } finally {
      setTriggering(false);
    }
  };

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

      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '1.5rem 2rem 4rem' }}>
        <Link href="/admin" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.875rem', color: 'var(--text-muted)', textDecoration: 'none', marginBottom: '1.5rem' }}>
          <ArrowLeft style={{ width: '16px', height: '16px' }} /> Back to Admin
        </Link>

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '1.5rem', fontFamily: "'Playfair Display', serif" }}>Data Sync Controls</h1>

        {/* Sync Trigger */}
        <div className="admin-card" style={{ marginBottom: '1.5rem', padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '0.75rem' }}>Manual Sync</h3>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Download latest DCC CSV files and upsert into database. Normally runs nightly at 2am.
          </p>
          <button
            className="btn-primary"
            onClick={handleTriggerSync}
            disabled={triggering}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            {triggering ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Play style={{ width: '16px', height: '16px' }} />}
            {triggering ? 'Syncing...' : 'Trigger Manual Sync Now'}
          </button>
          {message && (
            <p style={{ fontSize: '0.875rem', color: '#16a34a', marginTop: '0.75rem' }}>{message}</p>
          )}
        </div>

        {/* Last Sync Status */}
        {syncStatus && (
          <div className="admin-card" style={{ marginBottom: '1.5rem', padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>Last Sync</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem' }}>
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
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>Completed</div>
                <div style={{ fontSize: '0.875rem' }}>{syncStatus.completed_at ? new Date(syncStatus.completed_at).toLocaleString() : '—'}</div>
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
    </main>
  );
}
