'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Database, Settings, RefreshCw, Key, FileText, Activity,
  BarChart3, Users, Building2, Zap, Clock, Shield,
  ChevronRight, Map as MapIcon
} from 'lucide-react';
import { getStats, StatsResponse, CATEGORY_LABELS } from '@/lib/api';

export default function AdminPage() {
  const [token, setToken] = useState('');
  const [authenticated, setAuthenticated] = useState(false);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      setAuthenticated(true);
    }
  }, []);

  useEffect(() => {
    if (authenticated) {
      loadStats();
    }
  }, [authenticated]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('plansearch_admin_token', token);
    setAuthenticated(true);
  };

  const loadStats = async () => {
    setLoading(true);
    try {
      const data = await getStats();
      setStats(data);
    } catch (err) {
      console.error('Stats error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (!authenticated) {
    return (
      <main className="min-h-screen hero-gradient flex items-center justify-center">
        <div className="bg-white rounded-xl p-8 w-full max-w-md shadow-2xl">
          <div className="flex items-center gap-2 mb-6">
            <Shield className="w-6 h-6 text-[var(--teal)]" />
            <h1 className="text-xl font-semibold" style={{ fontFamily: "'Playfair Display', serif" }}>Admin Access</h1>
          </div>
          <form onSubmit={handleLogin}>
            <label className="text-xs text-[var(--text-muted)] uppercase tracking-wider block mb-2">Admin Token</label>
            <input
              type="password"
              className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--warm-white)] mb-4 focus:outline-none focus:border-[var(--teal)]"
              placeholder="Enter admin bearer token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <button type="submit" className="btn-primary w-full">
              <Key className="w-4 h-4" />
              Authenticate
            </button>
          </form>
        </div>
      </main>
    );
  }

  const classifiedPct = stats ? Math.round((stats.total_classified / Math.max(stats.total_applications, 1)) * 100) : 0;
  const scrapedPct = stats ? Math.round((stats.total_applicants_scraped / Math.max(stats.total_applications, 1)) * 100) : 0;

  return (
    <main className="min-h-screen flex flex-col" style={{ background: '#f9f8f6' }}>
      {/* Nav — matches homepage */}
      <nav style={{ background: '#0d1117', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-7xl mx-auto px-8 flex items-center justify-between" style={{ height: '64px' }}>
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-2 text-white no-underline">
              <Database className="w-5 h-5 text-[var(--teal)]" />
              <span style={{ color: 'white', fontSize: '1.125rem', fontWeight: '600', letterSpacing: '-0.01em', fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
            </Link>
            <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
            <span className="flex items-center gap-1.5" style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.9rem' }}>
              <Settings className="w-4 h-4" /> Admin Centre
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Link href="/" className="nav-link">Search</Link>
            <Link href="/map" className="nav-link"><MapIcon className="w-5 h-5" /> Map</Link>
            <button
              onClick={() => { localStorage.removeItem('plansearch_admin_token'); setAuthenticated(false); }}
              className="nav-link"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      <div style={{ maxWidth: '1100px', margin: '0 auto', width: '100%', padding: '2rem 2rem 4rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontFamily: "'Playfair Display', serif", marginBottom: '2rem', color: '#1a1a2e' }}>Control Centre</h1>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="stat-card">
            <div className="stat-value">{stats?.total_applications.toLocaleString() || '—'}</div>
            <div className="stat-label">Total Applications</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats?.total_classified.toLocaleString() || '—'}</div>
            <div className="stat-label">AI Classified</div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${classifiedPct}%` }} />
            </div>
            <div className="text-xs text-white/40 mt-1">{classifiedPct}%</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats?.total_applicants_scraped.toLocaleString() || '—'}</div>
            <div className="stat-label">Applicant Names</div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${scrapedPct}%` }} />
            </div>
            <div className="text-xs text-white/40 mt-1">{scrapedPct}%</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats?.total_cro_enriched.toLocaleString() || '—'}</div>
            <div className="stat-label">CRO Enriched</div>
          </div>
        </div>

        {/* Category Breakdown */}
        {stats && Object.keys(stats.categories).length > 0 && (
          <div className="admin-card mb-6">
            <h3 style={{ fontSize: '1.1rem', fontFamily: "'Playfair Display', serif", marginBottom: '1rem' }}>Classification Breakdown</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              {Object.entries(stats.categories)
                .sort(([, a], [, b]) => b - a)
                .map(([cat, count]) => (
                  <div key={cat} style={{ padding: '0.75rem', background: '#f9f8f6', borderRadius: '8px' }}>
                    <div style={{ fontSize: '0.9rem', fontWeight: '600', color: 'var(--teal)' }}>{count.toLocaleString()}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{CATEGORY_LABELS[cat] || cat}</div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Admin Panels */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link href="/admin/sync" className="admin-card hover:border-[var(--teal)] transition-colors no-underline">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                  <RefreshCw className="w-5 h-5 text-blue-500" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-[var(--text-primary)]">Data Sync</h3>
                  <p className="text-xs text-[var(--text-muted)]">DCC CSV import & sync status</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--text-muted)]" />
            </div>
            {stats?.last_sync && (
              <div className="mt-3 flex items-center gap-1 text-xs text-green-600">
                <Clock className="w-3 h-3" />
                Last sync: {new Date(stats.last_sync).toLocaleString()}
              </div>
            )}
          </Link>

          <Link href="/admin/classify" className="admin-card hover:border-[var(--teal)] transition-colors no-underline">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-purple-50 rounded-lg flex items-center justify-center">
                  <Zap className="w-5 h-5 text-purple-500" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-[var(--text-primary)]">AI Classification</h3>
                  <p className="text-xs text-[var(--text-muted)]">Claude classification queue & controls</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--text-muted)]" />
            </div>
          </Link>

          <Link href="/admin/keys" className="admin-card hover:border-[var(--teal)] transition-colors no-underline">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-amber-50 rounded-lg flex items-center justify-center">
                  <Key className="w-5 h-5 text-amber-500" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-[var(--text-primary)]">API Keys</h3>
                  <p className="text-xs text-[var(--text-muted)]">Claude & CRO key management</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--text-muted)]" />
            </div>
          </Link>

          <Link href="/admin/logs" className="admin-card hover:border-[var(--teal)] transition-colors no-underline">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gray-50 rounded-lg flex items-center justify-center">
                  <Activity className="w-5 h-5 text-gray-500" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-[var(--text-primary)]">System Logs</h3>
                  <p className="text-xs text-[var(--text-muted)]">Operation logs & recent activity</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--text-muted)]" />
            </div>
          </Link>

          <Link href="/admin/docs" className="admin-card hover:border-[var(--teal)] transition-colors no-underline">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-teal-50 rounded-lg flex items-center justify-center">
                  <FileText className="w-5 h-5 text-teal-500" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-[var(--text-primary)]">Document Scraping</h3>
                  <p className="text-xs text-[var(--text-muted)]">Document metadata index & controls</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--text-muted)]" />
            </div>
          </Link>
        </div>
      </div>
    </main>
  );
}
