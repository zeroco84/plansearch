'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Database, Search, Map as MapIcon, TrendingUp, BookOpen,
  Bell, Key, Plus, Trash2, Copy, Check, ExternalLink,
  Code, BarChart3, Webhook, Activity, Shield,
  ChevronDown, ChevronRight, CreditCard, UserCircle,
  AlertCircle, Eye, EyeOff,
} from 'lucide-react';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

interface ApiKeyData {
  id: string;
  name: string;
  key_prefix: string;
  environment: string;
  tier: string;
  is_active: boolean;
  calls_this_month: number;
  monthly_quota: number;
  rate_limit_per_minute: number;
  created_at: string;
  last_used_at: string | null;
}

interface WebhookData {
  id: string;
  url: string;
  events: string[];
  filters: Record<string, unknown>;
  is_active: boolean;
  failure_count: number;
  created_at: string;
  last_delivered_at: string | null;
}

interface UsageData {
  total_calls_this_month: number;
  monthly_quota: number;
  quota_percent: number;
  keys_count: number;
  tier: string;
  top_endpoints: Array<{ endpoint: string; count: number; avg_response_ms: number | null }>;
}

interface DailyData {
  date: string;
  calls: number;
}

const WEBHOOK_EVENTS = [
  { value: 'application.new', label: 'New Application', color: '#3b82f6' },
  { value: 'application.granted', label: 'Granted', color: '#22c55e' },
  { value: 'application.refused', label: 'Refused', color: '#ef4444' },
  { value: 'application.commenced', label: 'Commenced', color: '#f59e0b' },
  { value: 'application.completed', label: 'Completed', color: '#8b5cf6' },
  { value: 'application.fsc_filed', label: 'FSC Filed', color: '#06b6d4' },
  { value: 'application.withdrawn', label: 'Withdrawn', color: '#64748b' },
];

export default function DeveloperPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Data state
  const [apiKeys, setApiKeys] = useState<ApiKeyData[]>([]);
  const [webhooks, setWebhooks] = useState<WebhookData[]>([]);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [daily, setDaily] = useState<DailyData[]>([]);
  const [newKeySecret, setNewKeySecret] = useState<string | null>(null);
  const [newWebhookSecret, setNewWebhookSecret] = useState<string | null>(null);

  // Form state
  const [showKeyForm, setShowKeyForm] = useState(false);
  const [keyName, setKeyName] = useState('');
  const [keyEnv, setKeyEnv] = useState<'live' | 'test'>('live');

  const [showWebhookForm, setShowWebhookForm] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookEvents, setWebhookEvents] = useState<string[]>([]);

  // UI state
  const [activeSection, setActiveSection] = useState<'keys' | 'usage' | 'webhooks' | 'docs'>('keys');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const authHeaders = useCallback(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token]);

  useEffect(() => {
    const t = localStorage.getItem('plansearch_token');
    if (!t) {
      router.push('/login?next=/developer');
      return;
    }
    setToken(t);
  }, [router]);

  const fetchAll = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [keysRes, usageRes, dailyRes] = await Promise.all([
        fetch(`${API_BASE}/v1/keys`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => null),
        fetch(`${API_BASE}/v1/developer/usage`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => null),
        fetch(`${API_BASE}/v1/developer/usage/daily`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => null),
      ]);

      if (keysRes?.ok) {
        const d = await keysRes.json();
        setApiKeys(d.data?.keys || []);

        // If we have API keys, fetch webhooks using the first active key
        const firstKey = d.data?.keys?.find((k: ApiKeyData) => k.is_active);
        if (firstKey) {
          // Webhooks require API key auth, so we need to call via the key prefix
          // Since we don't have the raw key, list via a separate endpoint
          try {
            const whRes = await fetch(`${API_BASE}/v1/developer/webhooks`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (whRes?.ok) {
              const whData = await whRes.json();
              setWebhooks(whData.data?.webhooks || []);
            }
          } catch {}
        }
      }
      if (usageRes?.ok) {
        const d = await usageRes.json();
        setUsage(d.data || null);
      }
      if (dailyRes?.ok) {
        const d = await dailyRes.json();
        setDaily(d.data?.daily || []);
      }
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleCreateKey = async () => {
    setError('');
    if (!keyName.trim()) { setError('Key name is required'); return; }
    try {
      const res = await fetch(`${API_BASE}/v1/keys`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ name: keyName, environment: keyEnv }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create key');
      setNewKeySecret(data.data?.key || null);
      setShowKeyForm(false);
      setKeyName('');
      fetchAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error');
    }
  };

  const handleRevokeKey = async (id: string) => {
    if (!confirm('Revoke this API key? This cannot be undone.')) return;
    try {
      await fetch(`${API_BASE}/v1/keys/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchAll();
    } catch {}
  };

  const handleCreateWebhook = async () => {
    setError('');
    if (!webhookUrl.trim()) { setError('Webhook URL is required'); return; }
    if (!webhookUrl.startsWith('http')) { setError('URL must start with https://'); return; }
    try {
      const res = await fetch(`${API_BASE}/v1/developer/webhooks`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ url: webhookUrl, events: webhookEvents }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error?.message || data.detail || 'Failed');
      setNewWebhookSecret(data.data?.webhook_secret || null);
      setShowWebhookForm(false);
      setWebhookUrl('');
      setWebhookEvents([]);
      fetchAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error');
    }
  };

  const handleDeleteWebhook = async (id: string) => {
    if (!confirm('Delete this webhook?')) return;
    try {
      await fetch(`${API_BASE}/v1/developer/webhooks/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchAll();
    } catch {}
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleWebhookEvent = (ev: string) => {
    setWebhookEvents(prev => prev.includes(ev) ? prev.filter(e => e !== ev) : [...prev, ev]);
  };

  const tierColors: Record<string, string> = {
    developer: '#64748b',
    starter: '#f59e0b',
    professional: '#0d9488',
    enterprise: '#8b5cf6',
  };

  const handleLogout = () => {
    localStorage.removeItem('plansearch_token');
    localStorage.removeItem('plansearch_user');
    router.push('/');
  };

  // Chart rendering
  const maxCalls = Math.max(1, ...daily.map(d => d.calls));
  const chartDays = daily.length > 0 ? daily.slice(-30) : [];

  const navItems = [
    { id: 'keys', label: 'API Keys', icon: Key },
    { id: 'usage', label: 'Usage', icon: BarChart3 },
    { id: 'webhooks', label: 'Webhooks', icon: Webhook },
    { id: 'docs', label: 'Quickstart', icon: Code },
  ] as const;

  return (
    <main style={{ minHeight: '100vh', background: '#f9f8f6' }}>
      {/* Nav */}
      <nav style={{ background: '#0d1117', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '64px', padding: '0 2rem', width: '100%' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}>
            <Database style={{ width: 20, height: 20, color: '#2dd4bf' }} />
            <span style={{ color: 'white', fontSize: '1.125rem', fontWeight: 600, fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Link href="/" className="nav-link"><Search className="w-5 h-5" /><span className="hidden sm:inline">Search</span></Link>
            <Link href="/map" className="nav-link"><MapIcon className="w-5 h-5" /><span className="hidden sm:inline">Map</span></Link>
            <Link href="/significant" className="nav-link"><TrendingUp className="w-5 h-5" /><span className="hidden sm:inline">Significant</span></Link>
            <Link href="/alerts" className="nav-link"><Bell className="w-5 h-5" /><span className="hidden sm:inline">Alerts</span></Link>
            <Link href="/developer" className="nav-link" style={{ color: 'var(--teal)' }}><Code className="w-5 h-5" /><span className="hidden sm:inline">API</span></Link>
            <button onClick={handleLogout} className="nav-link" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: '0.85rem', padding: '8px 12px' }}>
              Logout
            </button>
          </div>
        </div>
      </nav>

      <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '2rem 2rem 4rem' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.25rem', fontFamily: "'Playfair Display', serif" }}>
              Developer Portal
            </h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Manage your API keys, webhooks, and monitor usage
            </p>
          </div>
          {usage && (
            <span style={{
              background: `${tierColors[usage.tier] || '#64748b'}15`,
              color: tierColors[usage.tier] || '#64748b',
              fontSize: '0.75rem', fontWeight: 700, padding: '4px 12px',
              borderRadius: '999px', textTransform: 'uppercase',
              border: `1px solid ${tierColors[usage.tier] || '#64748b'}30`,
            }}>
              {usage.tier} tier
            </span>
          )}
        </div>

        {/* Section tabs */}
        <div style={{ display: 'flex', gap: '4px', marginBottom: '2rem', background: 'white', borderRadius: '12px', padding: '4px', border: '1px solid var(--border)' }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeSection === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveSection(item.id)}
                style={{
                  flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
                  padding: '10px 16px', borderRadius: '10px', border: 'none',
                  background: active ? 'var(--teal)' : 'transparent',
                  color: active ? 'white' : 'var(--text-secondary)',
                  fontSize: '0.85rem', fontWeight: active ? 600 : 500, cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <Icon style={{ width: 16, height: 16 }} />
                <span className="hidden sm:inline">{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* ═══ API Keys Section ═══ */}
        {activeSection === 'keys' && (
          <div>
            {/* New key secret banner */}
            {newKeySecret && (
              <div style={{
                background: 'linear-gradient(135deg, rgba(34,197,94,0.1), rgba(34,197,94,0.02))',
                border: '1px solid rgba(34,197,94,0.3)', borderRadius: '12px',
                padding: '1.25rem', marginBottom: '1.5rem',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <AlertCircle style={{ width: 18, height: 18, color: '#22c55e' }} />
                  <strong style={{ color: '#166534', fontSize: '0.9rem' }}>API Key Generated — Copy Now!</strong>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#166534', marginBottom: '0.75rem' }}>
                  This key will not be shown again. Store it securely.
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <code style={{
                    flex: 1, background: 'rgba(0,0,0,0.05)', padding: '10px 14px',
                    borderRadius: '8px', fontSize: '0.85rem', fontFamily: 'monospace',
                    wordBreak: 'break-all', color: '#1e293b',
                  }}>
                    {newKeySecret}
                  </code>
                  <button
                    onClick={() => copyToClipboard(newKeySecret)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '4px',
                      background: '#22c55e', color: 'white', border: 'none',
                      padding: '10px 16px', borderRadius: '8px', fontSize: '0.85rem',
                      fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
                    }}
                  >
                    {copied ? <Check style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <button
                  onClick={() => setNewKeySecret(null)}
                  style={{ fontSize: '0.75rem', color: '#166534', background: 'none', border: 'none', cursor: 'pointer', marginTop: '0.75rem', textDecoration: 'underline' }}
                >
                  Dismiss
                </button>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
                <Key style={{ width: 18, height: 18, display: 'inline', verticalAlign: '-3px', marginRight: 6, color: 'var(--teal)' }} />
                API Keys ({apiKeys.length}/5)
              </h2>
              <button
                onClick={() => setShowKeyForm(true)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                  background: 'var(--teal)', color: 'white', border: 'none',
                  padding: '8px 16px', borderRadius: '8px', fontSize: '0.85rem',
                  fontWeight: 600, cursor: 'pointer',
                }}
              >
                <Plus style={{ width: 16, height: 16 }} /> New Key
              </button>
            </div>

            {/* Create form */}
            {showKeyForm && (
              <div className="admin-card" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
                <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.75rem' }}>
                  <input
                    type="text"
                    value={keyName}
                    onChange={e => setKeyName(e.target.value)}
                    placeholder="Key name (e.g. Production, Dev)"
                    style={{ flex: 1, padding: '10px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '0.9rem' }}
                  />
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {(['live', 'test'] as const).map(env => (
                      <button
                        key={env}
                        onClick={() => setKeyEnv(env)}
                        style={{
                          padding: '8px 14px', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 600,
                          border: keyEnv === env ? '2px solid var(--teal)' : '1px solid #d1d5db',
                          background: keyEnv === env ? 'rgba(13,148,136,0.08)' : 'white',
                          color: keyEnv === env ? 'var(--teal)' : '#374151',
                          cursor: 'pointer', textTransform: 'uppercase',
                        }}
                      >
                        {env}
                      </button>
                    ))}
                  </div>
                </div>
                {error && <div style={{ color: '#ef4444', fontSize: '0.8rem', marginBottom: '0.5rem' }}>{error}</div>}
                <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                  <button onClick={() => { setShowKeyForm(false); setError(''); }} style={{ padding: '8px 14px', borderRadius: '8px', border: '1px solid #d1d5db', background: 'white', fontSize: '0.85rem', cursor: 'pointer' }}>Cancel</button>
                  <button onClick={handleCreateKey} style={{ padding: '8px 18px', borderRadius: '8px', border: 'none', background: 'var(--teal)', color: 'white', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}>Generate Key</button>
                </div>
              </div>
            )}

            {/* Keys list */}
            {apiKeys.length === 0 && !showKeyForm && (
              <div className="admin-card" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Key style={{ width: 28, height: 28, margin: '0 auto 0.75rem', opacity: 0.4 }} />
                <p>No API keys yet. Generate one to get started.</p>
              </div>
            )}

            {apiKeys.map((k) => (
              <div
                key={k.id}
                className="admin-card"
                style={{ padding: '1rem 1.25rem', marginBottom: '0.75rem', opacity: k.is_active ? 1 : 0.5 }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '4px' }}>
                      <strong style={{ fontSize: '0.95rem' }}>{k.name}</strong>
                      <span style={{
                        fontSize: '0.65rem', fontWeight: 700, padding: '2px 8px',
                        borderRadius: '4px', textTransform: 'uppercase',
                        background: k.environment === 'live' ? 'rgba(34,197,94,0.1)' : 'rgba(59,130,246,0.1)',
                        color: k.environment === 'live' ? '#16a34a' : '#3b82f6',
                      }}>
                        {k.environment}
                      </span>
                      {!k.is_active && (
                        <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', background: 'rgba(239,68,68,0.1)', color: '#dc2626' }}>REVOKED</span>
                      )}
                    </div>
                    <code style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                      {k.key_prefix}••••••••
                    </code>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      {k.calls_this_month.toLocaleString()}/{k.monthly_quota.toLocaleString()} calls · {k.rate_limit_per_minute}/min
                      {k.last_used_at && ` · Last used ${new Date(k.last_used_at).toLocaleDateString()}`}
                    </div>
                  </div>
                  {k.is_active && (
                    <button
                      onClick={() => handleRevokeKey(k.id)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                      title="Revoke key"
                    >
                      <Trash2 style={{ width: 16, height: 16, color: '#ef4444' }} />
                    </button>
                  )}
                </div>
                {/* Quota progress bar */}
                {k.is_active && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <div style={{
                      width: '100%', height: 4, borderRadius: 2,
                      background: 'rgba(0,0,0,0.06)',
                    }}>
                      <div style={{
                        width: `${Math.min(100, (k.calls_this_month / k.monthly_quota) * 100)}%`,
                        height: '100%', borderRadius: 2,
                        background: (k.calls_this_month / k.monthly_quota) > 0.9
                          ? '#ef4444'
                          : (k.calls_this_month / k.monthly_quota) > 0.7
                          ? '#f59e0b'
                          : '#22c55e',
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ═══ Usage Section ═══ */}
        {activeSection === 'usage' && (
          <div>
            {/* Quota overview */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
              <div className="admin-card" style={{ padding: '1.25rem' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>Calls This Month</div>
                <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#1e293b' }}>
                  {(usage?.total_calls_this_month || 0).toLocaleString()}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  of {(usage?.monthly_quota || 0).toLocaleString()} quota
                </div>
                <div style={{ marginTop: '0.75rem' }}>
                  <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'rgba(0,0,0,0.06)' }}>
                    <div style={{
                      width: `${Math.min(100, usage?.quota_percent || 0)}%`,
                      height: '100%', borderRadius: 3,
                      background: (usage?.quota_percent || 0) > 90 ? '#ef4444' : (usage?.quota_percent || 0) > 70 ? '#f59e0b' : 'var(--teal)',
                      transition: 'width 0.5s ease',
                    }} />
                  </div>
                </div>
              </div>
              <div className="admin-card" style={{ padding: '1.25rem' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>Active Keys</div>
                <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#1e293b' }}>{usage?.keys_count || 0}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>of 5 max</div>
              </div>
              <div className="admin-card" style={{ padding: '1.25rem' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>Quota Used</div>
                <div style={{ fontSize: '1.75rem', fontWeight: 700, color: (usage?.quota_percent || 0) > 90 ? '#ef4444' : '#1e293b' }}>
                  {(usage?.quota_percent || 0).toFixed(1)}%
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  <Link href="/pricing" style={{ color: 'var(--teal)', textDecoration: 'none', fontWeight: 600 }}>Upgrade</Link> for more
                </div>
              </div>
            </div>

            {/* Daily calls chart */}
            <div className="admin-card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1rem' }}>
                <Activity style={{ width: 16, height: 16, display: 'inline', verticalAlign: '-2px', marginRight: 6, color: 'var(--teal)' }} />
                Daily API Calls (Last 30 Days)
              </h3>
              {chartDays.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  No API calls recorded yet. Make your first request!
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 120 }}>
                  {chartDays.map((d, i) => (
                    <div
                      key={i}
                      title={`${d.date}: ${d.calls} calls`}
                      style={{
                        flex: 1,
                        height: `${Math.max(4, (d.calls / maxCalls) * 100)}%`,
                        background: 'linear-gradient(180deg, var(--teal), rgba(13,148,136,0.4))',
                        borderRadius: '3px 3px 0 0',
                        minWidth: 4,
                        cursor: 'pointer',
                        transition: 'opacity 0.15s',
                      }}
                    />
                  ))}
                </div>
              )}
              {chartDays.length > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{chartDays[0]?.date}</span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{chartDays[chartDays.length - 1]?.date}</span>
                </div>
              )}
            </div>

            {/* Top endpoints */}
            {usage?.top_endpoints && usage.top_endpoints.length > 0 && (
              <div className="admin-card" style={{ padding: '1.5rem' }}>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1rem' }}>Top Endpoints</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {usage.top_endpoints.map((ep, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: i < usage.top_endpoints.length - 1 ? '1px solid var(--border)' : 'none' }}>
                      <code style={{ fontSize: '0.82rem', color: '#1e293b', fontFamily: 'monospace' }}>{ep.endpoint}</code>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        <span>{ep.count.toLocaleString()} calls</span>
                        {ep.avg_response_ms && <span>{ep.avg_response_ms}ms avg</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══ Webhooks Section ═══ */}
        {activeSection === 'webhooks' && (
          <div>
            {/* New webhook secret banner */}
            {newWebhookSecret && (
              <div style={{
                background: 'linear-gradient(135deg, rgba(34,197,94,0.1), rgba(34,197,94,0.02))',
                border: '1px solid rgba(34,197,94,0.3)', borderRadius: '12px',
                padding: '1.25rem', marginBottom: '1.5rem',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <Shield style={{ width: 18, height: 18, color: '#22c55e' }} />
                  <strong style={{ color: '#166534', fontSize: '0.9rem' }}>Webhook Secret — Copy Now!</strong>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#166534', marginBottom: '0.75rem' }}>
                  Use this to verify incoming webhook signatures. It will not be shown again.
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <code style={{
                    flex: 1, background: 'rgba(0,0,0,0.05)', padding: '10px 14px',
                    borderRadius: '8px', fontSize: '0.82rem', fontFamily: 'monospace',
                    wordBreak: 'break-all', color: '#1e293b',
                  }}>
                    {newWebhookSecret}
                  </code>
                  <button
                    onClick={() => copyToClipboard(newWebhookSecret)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '4px',
                      background: '#22c55e', color: 'white', border: 'none',
                      padding: '10px 16px', borderRadius: '8px', fontSize: '0.85rem',
                      fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
                    }}
                  >
                    {copied ? <Check style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <button
                  onClick={() => setNewWebhookSecret(null)}
                  style={{ fontSize: '0.75rem', color: '#166534', background: 'none', border: 'none', cursor: 'pointer', marginTop: '0.75rem', textDecoration: 'underline' }}
                >
                  Dismiss
                </button>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
                <Webhook style={{ width: 18, height: 18, display: 'inline', verticalAlign: '-3px', marginRight: 6, color: 'var(--teal)' }} />
                Webhooks
              </h2>
              <button
                onClick={() => setShowWebhookForm(true)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                  background: 'var(--teal)', color: 'white', border: 'none',
                  padding: '8px 16px', borderRadius: '8px', fontSize: '0.85rem',
                  fontWeight: 600, cursor: 'pointer',
                }}
              >
                <Plus style={{ width: 16, height: 16 }} /> New Webhook
              </button>
            </div>

            {/* Create webhook form */}
            {showWebhookForm && (
              <div className="admin-card" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
                <div style={{ marginBottom: '0.75rem' }}>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.3rem' }}>Endpoint URL</label>
                  <input
                    type="url"
                    value={webhookUrl}
                    onChange={e => setWebhookUrl(e.target.value)}
                    placeholder="https://yourapp.com/webhooks/plansearch"
                    style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '0.9rem', boxSizing: 'border-box' }}
                  />
                </div>
                <div style={{ marginBottom: '0.75rem' }}>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.5rem' }}>
                    Events <span style={{ fontWeight: 400, color: '#9ca3af' }}>(leave empty for all)</span>
                  </label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {WEBHOOK_EVENTS.map(ev => (
                      <button
                        key={ev.value}
                        type="button"
                        onClick={() => toggleWebhookEvent(ev.value)}
                        style={{
                          padding: '5px 10px', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 500,
                          border: webhookEvents.includes(ev.value) ? `2px solid ${ev.color}` : '1px solid #d1d5db',
                          background: webhookEvents.includes(ev.value) ? `${ev.color}10` : 'white',
                          color: webhookEvents.includes(ev.value) ? ev.color : '#374151',
                          cursor: 'pointer',
                        }}
                      >
                        {ev.label}
                      </button>
                    ))}
                  </div>
                </div>
                {error && <div style={{ color: '#ef4444', fontSize: '0.8rem', marginBottom: '0.5rem' }}>{error}</div>}
                <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                  <button onClick={() => { setShowWebhookForm(false); setError(''); }} style={{ padding: '8px 14px', borderRadius: '8px', border: '1px solid #d1d5db', background: 'white', fontSize: '0.85rem', cursor: 'pointer' }}>Cancel</button>
                  <button onClick={handleCreateWebhook} style={{ padding: '8px 18px', borderRadius: '8px', border: 'none', background: 'var(--teal)', color: 'white', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}>Create Webhook</button>
                </div>
              </div>
            )}

            {/* Webhooks list */}
            {webhooks.length === 0 && !showWebhookForm && (
              <div className="admin-card" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Webhook style={{ width: 28, height: 28, margin: '0 auto 0.75rem', opacity: 0.4 }} />
                <p>No webhooks configured. Create one to receive real-time planning events.</p>
              </div>
            )}

            {webhooks.map(wh => (
              <div key={wh.id} className="admin-card" style={{ padding: '1rem 1.25rem', marginBottom: '0.75rem', opacity: wh.is_active ? 1 : 0.5 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <div>
                    <code style={{ fontSize: '0.85rem', fontFamily: 'monospace', color: '#1e293b' }}>{wh.url}</code>
                    {wh.failure_count > 0 && (
                      <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: 'rgba(239,68,68,0.1)', color: '#dc2626', marginLeft: 8 }}>
                        {wh.failure_count} failures
                      </span>
                    )}
                  </div>
                  <button onClick={() => handleDeleteWebhook(wh.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
                    <Trash2 style={{ width: 16, height: 16, color: '#ef4444' }} />
                  </button>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '0.25rem' }}>
                  {wh.events.map(ev => {
                    const evConfig = WEBHOOK_EVENTS.find(e => e.value === ev);
                    return (
                      <span key={ev} style={{ fontSize: '0.68rem', background: `${evConfig?.color || '#64748b'}15`, color: evConfig?.color || '#64748b', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                        {evConfig?.label || ev}
                      </span>
                    );
                  })}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Created {new Date(wh.created_at).toLocaleDateString()}
                  {wh.last_delivered_at && ` · Last delivery ${new Date(wh.last_delivered_at).toLocaleDateString()}`}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ═══ Quickstart Docs Section ═══ */}
        {activeSection === 'docs' && (
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.5rem' }}>
              <Code style={{ width: 18, height: 18, display: 'inline', verticalAlign: '-3px', marginRight: 6, color: 'var(--teal)' }} />
              Quickstart Guide
            </h2>

            {/* Base URL */}
            <div className="admin-card" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>Base URL</h3>
              <code style={{ fontSize: '0.85rem', fontFamily: 'monospace', color: 'var(--teal)', background: 'rgba(13,148,136,0.06)', padding: '8px 12px', display: 'block', borderRadius: '6px' }}>
                https://api.plansearch.cc/v1
              </code>
            </div>

            {/* Authentication */}
            <div className="admin-card" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>Authentication</h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                Pass your API key via the <code style={{ background: 'rgba(0,0,0,0.04)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.82rem' }}>X-API-Key</code> header:
              </p>
              <pre style={{
                background: '#1e293b', color: '#e2e8f0', padding: '1rem',
                borderRadius: '8px', fontSize: '0.82rem', overflow: 'auto',
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              }}>
{`curl -H "X-API-Key: psk_live_your_key" \\
  https://api.plansearch.cc/v1/applications?category=residential_new_build`}
              </pre>
            </div>

            {/* Python example */}
            <div className="admin-card" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>Python</h3>
              <pre style={{
                background: '#1e293b', color: '#e2e8f0', padding: '1rem',
                borderRadius: '8px', fontSize: '0.82rem', overflow: 'auto',
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              }}>
{`import requests

API_KEY = "psk_live_your_key"
BASE = "https://api.plansearch.cc/v1"
HDRS = {"X-API-Key": API_KEY}

# Search for granted apartment schemes >€10m in Dublin
r = requests.get(f"{BASE}/applications", headers=HDRS, params={
    "authority": "Dublin City Council",
    "category": "residential_new_build",
    "keywords": "apartments",
    "decision": "granted",
    "value_min": 10_000_000,
    "year_from": 2024,
    "page_size": 50,
})

for app in r.json()["data"]["results"]:
    print(f'{app["reg_ref"]} €{app["est_value_high"]:,} {app["location"]}')`}
              </pre>
            </div>

            {/* JavaScript example */}
            <div className="admin-card" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>JavaScript / Node.js</h3>
              <pre style={{
                background: '#1e293b', color: '#e2e8f0', padding: '1rem',
                borderRadius: '8px', fontSize: '0.82rem', overflow: 'auto',
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              }}>
{`const API_KEY = "psk_live_your_key";
const BASE = "https://api.plansearch.cc/v1";
const headers = { "X-API-Key": API_KEY };

// Nearby search — 500m radius of Dublin city centre
const res = await fetch(
  \`\${BASE}/applications/nearby?lat=53.3498&lng=-6.2603&radius_m=500\`,
  { headers }
);
const { data } = await res.json();
console.log(\`\${data.total} applications nearby\`);

// Register a webhook
const wh = await fetch(\`\${BASE}/webhooks\`, {
  method: "POST",
  headers: { ...headers, "Content-Type": "application/json" },
  body: JSON.stringify({
    url: "https://yourapp.com/hook",
    events: ["application.granted", "application.commenced"],
    filters: { value_min: 1000000 },
  }),
});
const { data: webhook } = await wh.json();
console.log("Save this secret:", webhook.webhook_secret);`}
              </pre>
            </div>

            {/* Webhook verification */}
            <div className="admin-card" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>Verifying Webhook Signatures</h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                Every webhook delivery includes an <code style={{ background: 'rgba(0,0,0,0.04)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.82rem' }}>X-PlanSearch-Signature</code> header. Verify it like this:
              </p>
              <pre style={{
                background: '#1e293b', color: '#e2e8f0', padding: '1rem',
                borderRadius: '8px', fontSize: '0.82rem', overflow: 'auto',
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              }}>
{`import hmac, hashlib, json

def verify_signature(payload, signature_header, secret):
    """Verify X-PlanSearch-Signature on incoming webhook."""
    parts = dict(p.split("=", 1) for p in signature_header.split(","))
    timestamp = parts["t"]
    received_sig = parts["v1"]

    payload_json = json.dumps(payload, separators=(",", ":"))
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.{payload_json}".encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, received_sig)`}
              </pre>
            </div>

            {/* Endpoints reference */}
            <div className="admin-card" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.75rem' }}>Endpoint Reference</h3>
              <div style={{ fontSize: '0.82rem' }}>
                {[
                  { method: 'GET', path: '/v1/applications', desc: 'Search with AI + filters' },
                  { method: 'GET', path: '/v1/applications/nearby', desc: 'PostGIS proximity search' },
                  { method: 'GET', path: '/v1/applications/address', desc: 'Address/eircode lookup' },
                  { method: 'GET', path: '/v1/applications/{reg_ref}', desc: 'Full application detail' },
                  { method: 'GET', path: '/v1/stats', desc: 'Aggregate statistics' },
                  { method: 'GET', path: '/v1/authorities', desc: 'All 43 planning authorities' },
                  { method: 'GET', path: '/v1/export', desc: 'Bulk export (Enterprise)' },
                  { method: 'POST', path: '/v1/webhooks', desc: 'Create webhook' },
                  { method: 'GET', path: '/v1/webhooks', desc: 'List webhooks' },
                  { method: 'DELETE', path: '/v1/webhooks/{id}', desc: 'Delete webhook' },
                ].map((ep, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '0.75rem',
                    padding: '8px 0',
                    borderBottom: i < 9 ? '1px solid var(--border)' : 'none',
                  }}>
                    <span style={{
                      fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px',
                      borderRadius: '4px', fontFamily: 'monospace',
                      background: ep.method === 'GET' ? 'rgba(59,130,246,0.1)' : ep.method === 'POST' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                      color: ep.method === 'GET' ? '#3b82f6' : ep.method === 'POST' ? '#16a34a' : '#dc2626',
                      minWidth: 44, textAlign: 'center',
                    }}>
                      {ep.method}
                    </span>
                    <code style={{ fontFamily: 'monospace', color: '#1e293b', flex: 1 }}>{ep.path}</code>
                    <span style={{ color: 'var(--text-muted)' }}>{ep.desc}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Response format */}
            <div className="admin-card" style={{ padding: '1.25rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem' }}>Response Format</h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                All responses follow a consistent envelope:
              </p>
              <pre style={{
                background: '#1e293b', color: '#e2e8f0', padding: '1rem',
                borderRadius: '8px', fontSize: '0.82rem', overflow: 'auto',
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              }}>
{`{
  "data": {
    "results": [...],
    "total": 1234,
    "page": 1,
    "page_size": 25,
    "total_pages": 50
  },
  "meta": {
    "request_id": "req_abc123def456",
    "timestamp": "2026-03-20T10:00:00Z",
    "version": "1.0"
  }
}`}
              </pre>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
