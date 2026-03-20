'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Database, Search, Map as MapIcon, TrendingUp, BookOpen,
  Check, Zap, Star, Crown, ArrowRight, Bell, UserCircle,
  Code, Rocket, Building2, Globe,
} from 'lucide-react';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

// ── Alert subscription tiers ──
const alertTiers = [
  {
    id: 'starter',
    name: 'Starter',
    price: 29,
    icon: Zap,
    color: '#3b82f6',
    profiles: 5,
    popular: false,
    features: [
      'Up to 5 alert profiles',
      'All 30+ Irish councils + NI',
      'AI-classified categories',
      'Value estimates',
      'Lifecycle event tracking',
      'Email alerts (instant, daily, weekly)',
    ],
  },
  {
    id: 'professional',
    name: 'Professional',
    price: 79,
    icon: Star,
    color: '#0d9488',
    profiles: 25,
    popular: true,
    features: [
      'Up to 25 alert profiles',
      'All 30+ Irish councils + NI',
      'AI-classified categories',
      'Value estimates',
      'Lifecycle event tracking',
      'Email alerts (instant, daily, weekly)',
      'Priority support',
    ],
  },
  {
    id: 'agency',
    name: 'Agency',
    price: 199,
    icon: Crown,
    color: '#8b5cf6',
    profiles: 999,
    popular: false,
    features: [
      'Unlimited alert profiles',
      'All 30+ Irish councils + NI',
      'AI-classified categories',
      'Value estimates',
      'Lifecycle event tracking',
      'Email alerts (instant, daily, weekly)',
      'Priority support',
      'API access included',
    ],
  },
];

// ── API tiers ──
const apiTiers = [
  {
    id: 'api_developer',
    name: 'Developer',
    price: 0,
    priceLabel: 'Free',
    icon: Code,
    color: '#64748b',
    popular: false,
    features: [
      '1,000 calls/month',
      '10 requests/minute',
      '1 webhook',
      'All endpoints',
      'Real data (not mock)',
      'Community support',
    ],
  },
  {
    id: 'api_starter',
    name: 'Starter',
    price: 99,
    icon: Rocket,
    color: '#f59e0b',
    popular: false,
    features: [
      '10,000 calls/month',
      '60 requests/minute',
      '3 webhooks',
      'All endpoints',
      'Best-effort SLA',
      'Email support',
    ],
  },
  {
    id: 'api_professional',
    name: 'Professional',
    price: 299,
    icon: Building2,
    color: '#0d9488',
    popular: true,
    features: [
      '100,000 calls/month',
      '300 requests/minute',
      '10 webhooks',
      'All endpoints',
      '99.5% uptime SLA',
      'Priority support',
    ],
  },
  {
    id: 'api_enterprise',
    name: 'Enterprise',
    price: 999,
    icon: Globe,
    color: '#8b5cf6',
    popular: false,
    features: [
      '1,000,000 calls/month',
      '1,000 requests/minute',
      'Unlimited webhooks',
      'Bulk export (JSON/CSV/GeoJSON)',
      '99.9% uptime + SLA',
      'Dedicated support',
    ],
  },
];

export default function PricingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'alerts' | 'api'>('alerts');

  useEffect(() => {
    setToken(localStorage.getItem('plansearch_token'));
  }, []);

  const handleSubscribe = async (tierId: string) => {
    if (!token) {
      router.push(`/login?next=/pricing`);
      return;
    }
    setLoading(tierId);
    try {
      const res = await fetch(`${API_BASE}/api/billing/checkout?tier=${tierId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        alert(data.detail || 'Error creating checkout session');
      }
    } catch {
      alert('Failed to create checkout session');
    } finally {
      setLoading(null);
    }
  };

  const handleApiContact = (tierId: string) => {
    if (tierId === 'api_developer') {
      if (!token) {
        router.push('/login?next=/developer');
      } else {
        router.push('/developer');
      }
      return;
    }
    window.location.href = 'mailto:api@plansearch.cc?subject=PlanSearch API - ' + tierId;
  };

  const tabStyle = (active: boolean) => ({
    padding: '10px 28px',
    borderRadius: '999px',
    border: 'none',
    background: active ? 'rgba(45,212,191,0.15)' : 'transparent',
    color: active ? '#2dd4bf' : '#64748b',
    fontSize: '0.9rem',
    fontWeight: active ? 700 : 500,
    cursor: 'pointer' as const,
    transition: 'all 0.2s',
  });

  return (
    <main style={{ minHeight: '100vh', background: '#0d1117' }}>
      {/* Nav */}
      <nav style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '64px', padding: '0 2rem', width: '100%' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}>
            <Database style={{ width: 20, height: 20, color: '#2dd4bf' }} />
            <span style={{ color: 'white', fontSize: '1.125rem', fontWeight: 600, fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Link href="/" className="nav-link"><Search style={{ width: 20, height: 20 }} /><span className="hidden sm:inline">Search</span></Link>
            <Link href="/map" className="nav-link"><MapIcon style={{ width: 20, height: 20 }} /><span className="hidden sm:inline">Map</span></Link>
            <Link href="/significant" className="nav-link"><TrendingUp style={{ width: 20, height: 20 }} /><span className="hidden sm:inline">Significant</span></Link>
            <Link href="/insights" className="nav-link"><BookOpen style={{ width: 20, height: 20 }} /><span className="hidden sm:inline">Insights</span></Link>
            <Link href="/alerts" className="nav-link"><Bell style={{ width: 20, height: 20 }} /><span className="hidden sm:inline">Alerts</span></Link>
            {token ? (
              <Link href="/alerts" className="nav-link" style={{ color: 'var(--teal)' }}><UserCircle style={{ width: 20, height: 20 }} /><span className="hidden sm:inline">Account</span></Link>
            ) : (
              <Link href="/login" className="nav-link"><UserCircle style={{ width: 20, height: 20 }} /><span className="hidden sm:inline">Login</span></Link>
            )}
          </div>
        </div>
      </nav>

      {/* Hero */}
      <div style={{ textAlign: 'center', padding: '4rem 2rem 2rem', maxWidth: '800px', margin: '0 auto' }}>
        <h1 style={{ color: 'white', fontSize: '2.5rem', fontWeight: 700, marginBottom: '1rem', fontFamily: "'Playfair Display', serif", lineHeight: 1.2 }}>
          Planning intelligence<br />for every need
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '1.1rem', lineHeight: 1.6, maxWidth: '600px', margin: '0 auto 1.5rem' }}>
          Email alerts for your inbox, or a full REST API for your product.
          Search, map, and explore is always free.
        </p>

        {/* Tab switcher */}
        <div style={{ display: 'inline-flex', gap: '4px', background: 'rgba(255,255,255,0.04)', borderRadius: '999px', padding: '4px', marginBottom: '0.5rem' }}>
          <button onClick={() => setActiveTab('alerts')} style={tabStyle(activeTab === 'alerts')}>
            <Bell style={{ width: 14, height: 14, display: 'inline', verticalAlign: '-2px', marginRight: 6 }} />
            Email Alerts
          </button>
          <button onClick={() => setActiveTab('api')} style={tabStyle(activeTab === 'api')}>
            <Code style={{ width: 14, height: 14, display: 'inline', verticalAlign: '-2px', marginRight: 6 }} />
            API Access
          </button>
        </div>
      </div>

      {/* ── Alert Pricing Cards ── */}
      {activeTab === 'alerts' && (
        <>
          <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
            <p style={{ color: '#64748b', fontSize: '0.85rem' }}>
              Already used by contractors, QSs and architects across Ireland
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', maxWidth: '1050px', margin: '0 auto', padding: '0 2rem 4rem' }}>
            {alertTiers.map((tier) => {
              const Icon = tier.icon;
              return (
                <div
                  key={tier.id}
                  style={{
                    background: tier.popular ? 'linear-gradient(135deg, rgba(13,148,136,0.15), rgba(45,212,191,0.05))' : 'rgba(255,255,255,0.03)',
                    border: tier.popular ? '2px solid rgba(45,212,191,0.4)' : '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '16px',
                    padding: '2rem',
                    position: 'relative',
                    transition: 'transform 0.2s ease, border-color 0.2s ease',
                  }}
                >
                  {tier.popular && (
                    <div style={{
                      position: 'absolute', top: '-12px', left: '50%', transform: 'translateX(-50%)',
                      background: 'linear-gradient(135deg, #0d9488, #2dd4bf)',
                      color: 'white', fontSize: '0.7rem', fontWeight: 700,
                      padding: '4px 16px', borderRadius: '999px', letterSpacing: '0.05em',
                    }}>
                      MOST POPULAR
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                    <div style={{ width: 40, height: 40, borderRadius: 10, background: `${tier.color}20`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Icon style={{ width: 20, height: 20, color: tier.color }} />
                    </div>
                    <h3 style={{ color: 'white', fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>{tier.name}</h3>
                  </div>
                  <div style={{ marginBottom: '1.5rem' }}>
                    <span style={{ color: 'white', fontSize: '2.5rem', fontWeight: 700 }}>€{tier.price}</span>
                    <span style={{ color: '#64748b', fontSize: '0.9rem' }}>/month</span>
                  </div>
                  <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                    {tier.profiles === 999 ? 'Unlimited' : `Up to ${tier.profiles}`} alert profiles
                  </p>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 2rem' }}>
                    {tier.features.map((f, i) => (
                      <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', marginBottom: '0.6rem' }}>
                        <Check style={{ width: 16, height: 16, color: '#2dd4bf', marginTop: 2, flexShrink: 0 }} />
                        <span style={{ color: '#cbd5e1', fontSize: '0.85rem' }}>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={() => handleSubscribe(tier.id)}
                    disabled={loading === tier.id}
                    style={{
                      width: '100%', padding: '12px', borderRadius: '10px', border: 'none',
                      background: tier.popular ? 'linear-gradient(135deg, #0d9488, #2dd4bf)' : 'rgba(255,255,255,0.08)',
                      color: 'white', fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                      transition: 'opacity 0.2s',
                      opacity: loading === tier.id ? 0.6 : 1,
                    }}
                  >
                    {loading === tier.id ? 'Redirecting…' : 'Subscribe'}
                    <ArrowRight style={{ width: 16, height: 16 }} />
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ── API Pricing Cards ── */}
      {activeTab === 'api' && (
        <>
          <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
            <p style={{ color: '#64748b', fontSize: '0.85rem' }}>
              REST API for proptech, planning consultancies, estate agents & construction firms
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem', maxWidth: '1100px', margin: '0 auto', padding: '0 2rem 4rem' }}>
            {apiTiers.map((tier) => {
              const Icon = tier.icon;
              return (
                <div
                  key={tier.id}
                  style={{
                    background: tier.popular ? 'linear-gradient(135deg, rgba(13,148,136,0.15), rgba(45,212,191,0.05))' : 'rgba(255,255,255,0.03)',
                    border: tier.popular ? '2px solid rgba(45,212,191,0.4)' : '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '16px',
                    padding: '1.75rem',
                    position: 'relative',
                    transition: 'transform 0.2s ease, border-color 0.2s ease',
                  }}
                >
                  {tier.popular && (
                    <div style={{
                      position: 'absolute', top: '-12px', left: '50%', transform: 'translateX(-50%)',
                      background: 'linear-gradient(135deg, #0d9488, #2dd4bf)',
                      color: 'white', fontSize: '0.7rem', fontWeight: 700,
                      padding: '4px 16px', borderRadius: '999px', letterSpacing: '0.05em',
                    }}>
                      MOST POPULAR
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                    <div style={{ width: 40, height: 40, borderRadius: 10, background: `${tier.color}20`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Icon style={{ width: 20, height: 20, color: tier.color }} />
                    </div>
                    <h3 style={{ color: 'white', fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>{tier.name}</h3>
                  </div>
                  <div style={{ marginBottom: '1.5rem' }}>
                    {tier.price === 0 ? (
                      <span style={{ color: '#2dd4bf', fontSize: '2rem', fontWeight: 700 }}>Free</span>
                    ) : (
                      <>
                        <span style={{ color: 'white', fontSize: '2rem', fontWeight: 700 }}>€{tier.price}</span>
                        <span style={{ color: '#64748b', fontSize: '0.85rem' }}>/month</span>
                      </>
                    )}
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 1.75rem' }}>
                    {tier.features.map((f, i) => (
                      <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', marginBottom: '0.55rem' }}>
                        <Check style={{ width: 15, height: 15, color: '#2dd4bf', marginTop: 2, flexShrink: 0 }} />
                        <span style={{ color: '#cbd5e1', fontSize: '0.82rem' }}>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={() => handleApiContact(tier.id)}
                    style={{
                      width: '100%', padding: '12px', borderRadius: '10px', border: 'none',
                      background: tier.popular ? 'linear-gradient(135deg, #0d9488, #2dd4bf)' : tier.price === 0 ? 'rgba(45,212,191,0.15)' : 'rgba(255,255,255,0.08)',
                      color: tier.price === 0 ? '#2dd4bf' : 'white',
                      fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                      transition: 'opacity 0.2s',
                    }}
                  >
                    {tier.price === 0 ? 'Get Free API Key' : 'Contact Sales'}
                    <ArrowRight style={{ width: 16, height: 16 }} />
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* FAQ / footer */}
      <div style={{ maxWidth: '700px', margin: '0 auto', padding: '2rem 2rem 4rem', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <h3 style={{ color: '#e2e8f0', fontSize: '1.1rem', fontWeight: 600, textAlign: 'center', marginBottom: '1.5rem' }}>
          Frequently Asked Questions
        </h3>
        {[
          { q: 'What data is provided?', a: 'We provide all planning application data from all 31 Republic of Ireland councils (via NPAD), all 11 Northern Ireland councils, and Cork County Council — over 600,000 applications. We also include Disability Access Certificate (DAC) and Fire Safety Certificate (FSC) applications.' },
          { q: 'How fast are instant alerts?', a: 'Instant alerts are checked every 30 minutes. New applications typically appear within 1 hour of being published.' },
          { q: 'What does the API include?', a: 'Full REST API with search, proximity search, address/eircode lookup, single application detail, bulk export (Enterprise), and real-time webhooks for events like granted, refused, commenced, and completed.' },
          { q: 'Can I cancel anytime?', a: 'Yes. Cancel via the billing portal at any time. Your alerts and API access remain active until the end of your billing period.' },
          { q: 'What payment methods are accepted?', a: 'Visa, Mastercard, and all major cards via Stripe. Secure PCI-compliant checkout.' },
        ].map((faq, i) => (
          <div key={i} style={{ marginBottom: '1.25rem' }}>
            <h4 style={{ color: '#e2e8f0', fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.25rem' }}>{faq.q}</h4>
            <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: 0, lineHeight: 1.5 }}>{faq.a}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
