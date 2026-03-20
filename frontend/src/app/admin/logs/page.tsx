'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, Activity, RefreshCw, Settings, Search, TrendingUp, BookOpen, Map as MapIcon , BarChart3 } from 'lucide-react';
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

        <div className="flex items-center justify-between" style={{ marginBottom: '1.25rem' }}>
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
