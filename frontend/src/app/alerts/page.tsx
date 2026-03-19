'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Database, Search, Map as MapIcon, TrendingUp, BookOpen, Settings,
  Bell, Plus, Trash2, ToggleLeft, ToggleRight, ExternalLink,
  CreditCard, Clock, ChevronDown, X,
} from 'lucide-react';
import { CATEGORY_LABELS, IRISH_AUTHORITIES } from '@/lib/api';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

const TRIGGER_EVENTS = [
  { value: 'new_application', label: 'New Application' },
  { value: 'granted', label: 'Granted' },
  { value: 'refused', label: 'Refused' },
  { value: 'under_construction', label: 'Under Construction' },
  { value: 'complete', label: 'Completed' },
  { value: 'fsc_filed', label: 'FSC Filed' },
  { value: 'further_info', label: 'Further Info Requested' },
  { value: 'withdrawn', label: 'Withdrawn' },
];

const VALUE_OPTIONS = [
  { value: '', label: 'Any Value' },
  { value: '500000', label: '€500k+' },
  { value: '2000000', label: '€2m+' },
  { value: '5000000', label: '€5m+' },
  { value: '10000000', label: '€10m+' },
  { value: '50000000', label: '€50m+' },
];

interface AlertProfile {
  id: string;
  name: string;
  is_active: boolean;
  trigger_events: string[];
  planning_authorities: string[];
  dev_categories: string[];
  value_min: number | null;
  value_max: number | null;
  keywords: string | null;
  frequency: string;
  last_triggered_at: string | null;
}

interface DeliveryRecord {
  id: string;
  sent_at: string;
  application_count: number;
  email_subject: string | null;
  status: string;
}

export default function AlertsPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<Record<string, string> | null>(null);
  const [profiles, setProfiles] = useState<AlertProfile[]>([]);
  const [deliveries, setDeliveries] = useState<DeliveryRecord[]>([]);
  const [billing, setBilling] = useState<{ tier: string; status: string; max_profiles: number } | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);

  // Form state
  const [formName, setFormName] = useState('');
  const [formEvents, setFormEvents] = useState<string[]>(['new_application', 'granted']);
  const [formAuthorities, setFormAuthorities] = useState<string[]>([]);
  const [formCategories, setFormCategories] = useState<string[]>([]);
  const [formValueMin, setFormValueMin] = useState('');
  const [formKeywords, setFormKeywords] = useState('');
  const [formFrequency, setFormFrequency] = useState('daily');
  const [formError, setFormError] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);

  const authHeaders = useCallback(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token]);

  useEffect(() => {
    const t = localStorage.getItem('plansearch_token');
    const u = localStorage.getItem('plansearch_user');
    if (!t) {
      router.push('/login?next=/alerts');
      return;
    }
    setToken(t);
    if (u) setUser(JSON.parse(u));
  }, [router]);

  const fetchAll = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [profilesRes, historyRes, billingRes] = await Promise.all([
        fetch(`${API_BASE}/api/alerts/profiles`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => null),
        fetch(`${API_BASE}/api/alerts/history`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => null),
        fetch(`${API_BASE}/api/billing/status`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => null),
      ]);
      if (profilesRes?.ok) {
        const d = await profilesRes.json();
        setProfiles(d.profiles || []);
      }
      if (historyRes?.ok) {
        const d = await historyRes.json();
        setDeliveries((d.deliveries || []).slice(0, 10));
      }
      if (billingRes?.ok) {
        setBilling(await billingRes.json());
      }
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleManageBilling = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/billing/portal`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.portal_url) window.location.href = data.portal_url;
    } catch {}
  };

  const handleToggle = async (id: string) => {
    await fetch(`${API_BASE}/api/alerts/profiles/${id}/toggle`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}` },
    });
    fetchAll();
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this alert profile?')) return;
    await fetch(`${API_BASE}/api/alerts/profiles/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    fetchAll();
  };

  const handleLogout = () => {
    localStorage.removeItem('plansearch_token');
    localStorage.removeItem('plansearch_user');
    router.push('/');
  };

  const resetForm = () => {
    setFormName('');
    setFormEvents(['new_application', 'granted']);
    setFormAuthorities([]);
    setFormCategories([]);
    setFormValueMin('');
    setFormKeywords('');
    setFormFrequency('daily');
    setFormError('');
    setEditingId(null);
  };

  const openEdit = (p: AlertProfile) => {
    setFormName(p.name);
    setFormEvents(p.trigger_events);
    setFormAuthorities(p.planning_authorities);
    setFormCategories(p.dev_categories);
    setFormValueMin(p.value_min ? String(p.value_min) : '');
    setFormKeywords(p.keywords || '');
    setFormFrequency(p.frequency);
    setEditingId(p.id);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (!formName.trim()) { setFormError('Name is required'); return; }
    if (formEvents.length === 0) { setFormError('Select at least one trigger event'); return; }

    const body = {
      name: formName.trim(),
      trigger_events: formEvents,
      planning_authorities: formAuthorities,
      dev_categories: formCategories,
      value_min: formValueMin ? parseInt(formValueMin) : null,
      value_max: null,
      keywords: formKeywords.trim() || null,
      frequency: formFrequency,
    };

    try {
      const url = editingId
        ? `${API_BASE}/api/alerts/profiles/${editingId}`
        : `${API_BASE}/api/alerts/profiles`;
      const res = await fetch(url, {
        method: editingId ? 'PUT' : 'POST',
        headers: authHeaders(),
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to save profile');
      }
      setShowForm(false);
      resetForm();
      fetchAll();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Error');
    }
  };

  const toggleEvent = (ev: string) => {
    setFormEvents(prev => prev.includes(ev) ? prev.filter(e => e !== ev) : [...prev, ev]);
  };

  // Build flat authority list
  const allAuthorities: string[] = [];
  Object.values(IRISH_AUTHORITIES).forEach(section => {
    if (Array.isArray(section)) {
      section.forEach(a => allAuthorities.push(a));
    }
  });

  const tierColors: Record<string, string> = {
    free: '#64748b',
    starter: '#3b82f6',
    professional: '#0d9488',
    agency: '#8b5cf6',
  };

  const isSubscribed = billing?.status === 'active';

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
            <Link href="/alerts" className="nav-link" style={{ color: 'var(--teal)' }}><Bell className="w-5 h-5" /><span className="hidden sm:inline">Alerts</span></Link>
            <button onClick={handleLogout} className="nav-link" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: '0.85rem', padding: '8px 12px' }}>
              Logout
            </button>
          </div>
        </div>
      </nav>

      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem 2rem 4rem' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.25rem', fontFamily: "'Playfair Display', serif" }}>
              Planning Alerts
            </h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              {user?.full_name ? `Welcome, ${user.full_name}` : 'Manage your alert profiles'}
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {billing && (
              <span style={{
                background: `${tierColors[billing.tier] || '#64748b'}15`,
                color: tierColors[billing.tier] || '#64748b',
                fontSize: '0.75rem', fontWeight: 700, padding: '4px 12px',
                borderRadius: '999px', textTransform: 'uppercase',
                border: `1px solid ${tierColors[billing.tier] || '#64748b'}30`,
              }}>
                {billing.tier} · {billing.status}
              </span>
            )}
            {isSubscribed && (
              <button
                onClick={handleManageBilling}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                  background: 'none', border: '1px solid var(--border)', borderRadius: '8px',
                  padding: '6px 12px', fontSize: '0.8rem', color: 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                <CreditCard style={{ width: 14, height: 14 }} /> Manage Billing
              </button>
            )}
          </div>
        </div>

        {/* Not subscribed CTA */}
        {!loading && !isSubscribed && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(13,148,136,0.08), rgba(45,212,191,0.04))',
            border: '1px solid rgba(13,148,136,0.2)', borderRadius: '12px',
            padding: '2rem', textAlign: 'center', marginBottom: '1.5rem',
          }}>
            <Bell style={{ width: 32, height: 32, color: 'var(--teal)', margin: '0 auto 1rem' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>Subscribe to activate alerts</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.25rem', maxWidth: '500px', margin: '0 auto 1.25rem' }}>
              Choose a plan to start receiving planning intelligence alerts customised to your business.
            </p>
            <Link
              href="/pricing"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                background: 'var(--teal)', color: 'white', padding: '10px 24px',
                borderRadius: '8px', textDecoration: 'none', fontWeight: 600, fontSize: '0.9rem',
              }}
            >
              View Plans <ExternalLink style={{ width: 14, height: 14 }} />
            </Link>
          </div>
        )}

        {/* Alert Profiles */}
        {isSubscribed && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>
                Alert Profiles ({profiles.length}/{billing?.max_profiles ?? 0})
              </h2>
              <button
                onClick={() => { resetForm(); setShowForm(true); }}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                  background: 'var(--teal)', color: 'white', border: 'none',
                  padding: '8px 16px', borderRadius: '8px', fontSize: '0.85rem',
                  fontWeight: 600, cursor: 'pointer',
                }}
              >
                <Plus style={{ width: 16, height: 16 }} /> New Alert Profile
              </button>
            </div>

            {profiles.length === 0 && !showForm && (
              <div className="admin-card" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Bell style={{ width: 28, height: 28, margin: '0 auto 0.75rem', opacity: 0.4 }} />
                <p>No alert profiles yet. Create one to get started.</p>
              </div>
            )}

            {profiles.map(p => (
              <div key={p.id} className="admin-card" style={{ padding: '1rem 1.25rem', marginBottom: '0.75rem', opacity: p.is_active ? 1 : 0.6 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <button onClick={() => handleToggle(p.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                      {p.is_active
                        ? <ToggleRight style={{ width: 28, height: 28, color: 'var(--teal)' }} />
                        : <ToggleLeft style={{ width: 28, height: 28, color: '#d1d5db' }} />
                      }
                    </button>
                    <div>
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 600, margin: 0, cursor: 'pointer' }} onClick={() => openEdit(p)}>
                        {p.name}
                      </h3>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {p.frequency} · {p.trigger_events.length} events
                        {p.planning_authorities.length > 0 && ` · ${p.planning_authorities.length} councils`}
                        {p.value_min && ` · €${(p.value_min / 1000000).toFixed(0)}m+`}
                        {p.keywords && ` · "${p.keywords}"`}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button onClick={() => openEdit(p)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.8rem' }}>Edit</button>
                    <button onClick={() => handleDelete(p.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                      <Trash2 style={{ width: 16, height: 16, color: '#ef4444' }} />
                    </button>
                  </div>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {p.trigger_events.map(ev => (
                    <span key={ev} style={{ fontSize: '0.7rem', background: 'rgba(13,148,136,0.08)', color: 'var(--teal)', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                      {TRIGGER_EVENTS.find(t => t.value === ev)?.label || ev}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </>
        )}

        {/* New/Edit Profile Form Modal */}
        {showForm && (
          <div style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: '1rem',
          }}>
            <div style={{
              background: 'white', borderRadius: '16px', width: '100%', maxWidth: '560px',
              maxHeight: '90vh', overflow: 'auto', padding: '2rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 600, margin: 0 }}>
                  {editingId ? 'Edit Alert Profile' : 'New Alert Profile'}
                </h2>
                <button onClick={() => { setShowForm(false); resetForm(); }} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                  <X style={{ width: 20, height: 20, color: '#6b7280' }} />
                </button>
              </div>

              <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {/* Name */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.3rem' }}>Alert Name</label>
                  <input
                    type="text" value={formName} onChange={e => setFormName(e.target.value)}
                    placeholder="e.g. Large Dublin Residential"
                    style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '0.9rem', boxSizing: 'border-box' }}
                  />
                </div>

                {/* Trigger Events */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.5rem' }}>Trigger Events</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {TRIGGER_EVENTS.map(ev => (
                      <button
                        key={ev.value} type="button"
                        onClick={() => toggleEvent(ev.value)}
                        style={{
                          padding: '6px 12px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 500,
                          border: formEvents.includes(ev.value) ? '2px solid var(--teal)' : '1px solid #d1d5db',
                          background: formEvents.includes(ev.value) ? 'rgba(13,148,136,0.08)' : 'white',
                          color: formEvents.includes(ev.value) ? 'var(--teal)' : '#374151',
                          cursor: 'pointer',
                        }}
                      >
                        {ev.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Councils */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.3rem' }}>
                    Planning Authorities <span style={{ fontWeight: 400, color: '#9ca3af' }}>(leave empty for all Ireland)</span>
                  </label>
                  <select
                    multiple
                    value={formAuthorities}
                    onChange={e => setFormAuthorities(Array.from(e.target.selectedOptions, o => o.value))}
                    style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '0.85rem', minHeight: '120px', boxSizing: 'border-box' }}
                  >
                    {allAuthorities.map(a => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </div>

                {/* Dev Categories */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.3rem' }}>
                    Development Types <span style={{ fontWeight: 400, color: '#9ca3af' }}>(leave empty for all)</span>
                  </label>
                  <select
                    multiple
                    value={formCategories}
                    onChange={e => setFormCategories(Array.from(e.target.selectedOptions, o => o.value))}
                    style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '0.85rem', minHeight: '100px', boxSizing: 'border-box' }}
                  >
                    {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>

                {/* Value + Keywords */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.3rem' }}>Minimum Value</label>
                    <select
                      value={formValueMin} onChange={e => setFormValueMin(e.target.value)}
                      style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '0.85rem', boxSizing: 'border-box' }}
                    >
                      {VALUE_OPTIONS.map(v => (
                        <option key={v.value} value={v.value}>{v.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.3rem' }}>Keywords</label>
                    <input
                      type="text" value={formKeywords} onChange={e => setFormKeywords(e.target.value)}
                      placeholder="e.g. solar farm"
                      style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '0.85rem', boxSizing: 'border-box' }}
                    />
                  </div>
                </div>

                {/* Frequency */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: '0.5rem' }}>Delivery Frequency</label>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {[
                      { value: 'instant', label: 'Instant', desc: 'Every 30 min' },
                      { value: 'daily', label: 'Daily Digest', desc: '8am daily' },
                      { value: 'weekly', label: 'Weekly Digest', desc: 'Every Monday' },
                    ].map(f => (
                      <button
                        key={f.value} type="button"
                        onClick={() => setFormFrequency(f.value)}
                        style={{
                          flex: 1, padding: '10px 8px', borderRadius: '8px', cursor: 'pointer',
                          border: formFrequency === f.value ? '2px solid var(--teal)' : '1px solid #d1d5db',
                          background: formFrequency === f.value ? 'rgba(13,148,136,0.06)' : 'white',
                          textAlign: 'center',
                        }}
                      >
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: formFrequency === f.value ? 'var(--teal)' : '#374151' }}>{f.label}</div>
                        <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: 2 }}>{f.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {formError && (
                  <div style={{ color: '#ef4444', fontSize: '0.85rem', background: 'rgba(239,68,68,0.08)', padding: '10px 12px', borderRadius: '8px' }}>
                    {formError}
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                  <button type="button" onClick={() => { setShowForm(false); resetForm(); }} style={{ padding: '10px 20px', borderRadius: '8px', border: '1px solid #d1d5db', background: 'white', fontSize: '0.9rem', cursor: 'pointer' }}>
                    Cancel
                  </button>
                  <button type="submit" style={{
                    padding: '10px 24px', borderRadius: '8px', border: 'none',
                    background: 'var(--teal)', color: 'white', fontSize: '0.9rem',
                    fontWeight: 600, cursor: 'pointer',
                  }}>
                    {editingId ? 'Save Changes' : 'Create Alert'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Delivery History */}
        {isSubscribed && deliveries.length > 0 && (
          <div style={{ marginTop: '2rem' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              <Clock style={{ width: 18, height: 18, display: 'inline', verticalAlign: 'text-bottom', marginRight: '0.4rem' }} />
              Recent Deliveries
            </h2>
            {deliveries.map(d => (
              <div key={d.id} className="admin-card" style={{ padding: '0.75rem 1rem', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 500 }}>{d.email_subject || 'Alert delivery'}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {new Date(d.sent_at).toLocaleString()} · {d.application_count} matches
                    </div>
                  </div>
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 600, padding: '2px 8px', borderRadius: '4px',
                    background: d.status === 'sent' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                    color: d.status === 'sent' ? '#16a34a' : '#dc2626',
                  }}>
                    {d.status.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
