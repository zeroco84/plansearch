'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, Activity, RefreshCw } from 'lucide-react';
import { getAdminLogs } from '@/lib/api';

export default function LogsPage() {
  const [token, setToken] = useState('');
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) { setToken(saved); loadLogs(saved); }
  }, []);

  const loadLogs = async (t: string) => {
    setLoading(true);
    try {
      const data = await getAdminLogs(t, 100);
      if (Array.isArray(data)) setLogs(data);
    } catch {}
    setLoading(false);
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
          <span className="text-white/70 text-sm">System Logs</span>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-6">
        <Link href="/admin" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--teal)] mb-6 no-underline">
          <ArrowLeft className="w-4 h-4" /> Back to Admin
        </Link>

        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl" style={{ fontFamily: "'Playfair Display', serif" }}>System Logs</h1>
          <button className="btn-secondary" onClick={() => loadLogs(token)}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="admin-card">
          {logs.length === 0 ? (
            <div className="text-center py-12">
              <Activity className="w-10 h-10 text-[var(--border)] mx-auto mb-3" />
              <p className="text-sm text-[var(--text-muted)]">No log entries yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {logs.map((log: any, i: number) => (
                <div
                  key={log.id || i}
                  className="flex items-start justify-between p-3 bg-[var(--warm-white)] rounded-lg text-sm border border-transparent hover:border-[var(--border)] transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                      log.status === 'completed' ? 'bg-green-500' :
                      log.status === 'running' ? 'bg-blue-500 animate-pulse' :
                      'bg-red-500'
                    }`} />
                    <div>
                      <div className="font-medium">
                        {log.sync_type || 'Operation'}
                        <span className={`ml-2 text-xs ${
                          log.status === 'completed' ? 'text-green-600' :
                          log.status === 'running' ? 'text-blue-600' :
                          'text-red-600'
                        }`}>
                          {log.status}
                        </span>
                      </div>
                      {log.error_message && (
                        <div className="text-xs text-red-600 mt-1">{log.error_message}</div>
                      )}
                      <div className="text-xs text-[var(--text-muted)] mt-1 flex gap-3">
                        {log.records_processed != null && <span>{log.records_processed.toLocaleString()} records</span>}
                        {log.records_new != null && <span>{log.records_new} new</span>}
                        {log.records_updated != null && <span>{log.records_updated} updated</span>}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-[var(--text-muted)] text-right flex-shrink-0">
                    {log.started_at && <div>{new Date(log.started_at).toLocaleString()}</div>}
                    {log.completed_at && log.started_at && (
                      <div className="text-[var(--text-muted)]">
                        {Math.round((new Date(log.completed_at).getTime() - new Date(log.started_at).getTime()) / 1000)}s
                      </div>
                    )}
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
