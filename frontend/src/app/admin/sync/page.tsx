'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, RefreshCw, Play, CheckCircle, XCircle, Clock } from 'lucide-react';
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
    <main className="min-h-screen bg-[var(--warm-white)]">
      <nav className="hero-gradient" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2 text-white no-underline">
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <span className="text-white/30">|</span>
          <span className="text-white/70 text-sm">Data Sync</span>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-6">
        <Link href="/admin" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--teal)] mb-6 no-underline">
          <ArrowLeft className="w-4 h-4" /> Back to Admin
        </Link>

        <h1 className="text-2xl mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>Data Sync Controls</h1>

        {/* Sync Trigger */}
        <div className="admin-card mb-6">
          <h3 className="text-base font-semibold mb-4">Manual Sync</h3>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Download latest DCC CSV files and upsert into database. Normally runs nightly at 2am.
          </p>
          <button
            className="btn-primary"
            onClick={handleTriggerSync}
            disabled={triggering}
          >
            {triggering ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {triggering ? 'Syncing...' : 'Trigger Manual Sync Now'}
          </button>
          {message && (
            <p className="text-sm text-green-600 mt-3">{message}</p>
          )}
        </div>

        {/* Last Sync Status */}
        {syncStatus && (
          <div className="admin-card mb-6">
            <h3 className="text-base font-semibold mb-4">Last Sync</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-[var(--text-muted)] uppercase">Status</div>
                <div className={`text-sm font-semibold ${syncStatus.status === 'completed' ? 'text-green-600' : syncStatus.status === 'running' ? 'text-blue-600' : 'text-red-600'}`}>
                  {syncStatus.status === 'completed' && <CheckCircle className="w-4 h-4 inline mr-1" />}
                  {syncStatus.status === 'failed' && <XCircle className="w-4 h-4 inline mr-1" />}
                  {syncStatus.status === 'running' && <RefreshCw className="w-4 h-4 inline mr-1 animate-spin" />}
                  {syncStatus.status}
                </div>
              </div>
              <div>
                <div className="text-xs text-[var(--text-muted)] uppercase">Records</div>
                <div className="text-sm font-semibold">{syncStatus.records_processed?.toLocaleString() || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-[var(--text-muted)] uppercase">Started</div>
                <div className="text-sm">{syncStatus.started_at ? new Date(syncStatus.started_at).toLocaleString() : '—'}</div>
              </div>
              <div>
                <div className="text-xs text-[var(--text-muted)] uppercase">Completed</div>
                <div className="text-sm">{syncStatus.completed_at ? new Date(syncStatus.completed_at).toLocaleString() : '—'}</div>
              </div>
            </div>
            {syncStatus.error_message && (
              <div className="mt-3 p-3 bg-red-50 rounded-lg text-sm text-red-700">{syncStatus.error_message}</div>
            )}
          </div>
        )}

        {/* Sync Logs */}
        <div className="admin-card">
          <h3 className="text-base font-semibold mb-4">Recent Sync Logs</h3>
          {logs.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]">No sync logs yet</p>
          ) : (
            <div className="space-y-2">
              {logs.map((log: any, i: number) => (
                <div key={log.id || i} className="flex items-center justify-between p-3 bg-[var(--warm-white)] rounded-lg text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${log.status === 'completed' ? 'bg-green-500' : log.status === 'running' ? 'bg-blue-500' : 'bg-red-500'}`} />
                    <span className="font-medium">{log.sync_type || 'sync'}</span>
                  </div>
                  <div className="flex items-center gap-4 text-[var(--text-muted)]">
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
