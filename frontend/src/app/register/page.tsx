'use client';

import { useState, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Database, UserPlus, Eye, EyeOff } from 'lucide-react';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get('next') || '/alerts';

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          company: company || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Registration failed');
      }

      const data = await res.json();
      localStorage.setItem('plansearch_token', data.access_token);
      localStorage.setItem('plansearch_user', JSON.stringify(data.user));
      router.push(next);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    width: '100%' as const,
    padding: '12px 14px',
    borderRadius: '10px',
    border: '1px solid rgba(255,255,255,0.1)',
    background: 'rgba(255,255,255,0.04)',
    color: 'white',
    fontSize: '0.9rem',
    outline: 'none',
    boxSizing: 'border-box' as const,
  };

  const labelStyle = {
    display: 'block' as const,
    color: '#94a3b8',
    fontSize: '0.8rem',
    fontWeight: 600 as const,
    marginBottom: '0.4rem',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  };

  return (
    <main style={{ minHeight: '100vh', background: '#0d1117', display: 'flex', flexDirection: 'column' }}>
      {/* Nav */}
      <nav style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '64px', padding: '0 2rem', maxWidth: '1200px', margin: '0 auto' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}>
            <Database style={{ width: 20, height: 20, color: '#2dd4bf' }} />
            <span style={{ color: 'white', fontSize: '1.125rem', fontWeight: 600, fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
            <Link href="/pricing" style={{ color: '#2dd4bf', textDecoration: 'none', fontSize: '0.875rem', fontWeight: 600 }}>Pricing</Link>
            <Link href="/" style={{ color: '#94a3b8', textDecoration: 'none', fontSize: '0.875rem' }}>Search</Link>
          </div>
        </div>
      </nav>

      {/* Form */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
        <div style={{ width: '100%', maxWidth: '420px' }}>
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <div style={{ width: 48, height: 48, borderRadius: 12, background: 'rgba(45,212,191,0.1)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
              <UserPlus style={{ width: 24, height: 24, color: '#2dd4bf' }} />
            </div>
            <h1 style={{ color: 'white', fontSize: '1.5rem', fontWeight: 700, margin: '0 0 0.5rem', fontFamily: "'Playfair Display', serif" }}>
              Create your free account
            </h1>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', margin: 0 }}>
              It&apos;s free to create an account. Subscriptions are only needed for email alerts.
            </p>
          </div>

          <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={labelStyle}>Full Name</label>
              <input type="text" value={fullName} onChange={e => setFullName(e.target.value)} required placeholder="John Murphy" style={inputStyle} />
            </div>

            <div>
              <label style={labelStyle}>Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="john@company.ie" style={inputStyle} />
            </div>

            <div>
              <label style={labelStyle}>Company <span style={{ fontWeight: 400, textTransform: 'none' }}>(optional)</span></label>
              <input type="text" value={company} onChange={e => setCompany(e.target.value)} placeholder="ACME Construction Ltd" style={inputStyle} />
            </div>

            <div>
              <label style={labelStyle}>Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  placeholder="Min 8 characters"
                  style={{ ...inputStyle, paddingRight: '42px' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  {showPassword
                    ? <EyeOff style={{ width: 18, height: 18, color: '#64748b' }} />
                    : <Eye style={{ width: 18, height: 18, color: '#64748b' }} />
                  }
                </button>
              </div>
            </div>

            {error && (
              <div style={{ color: '#ef4444', fontSize: '0.85rem', background: 'rgba(239,68,68,0.1)', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(239,68,68,0.2)' }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', padding: '12px', borderRadius: '10px', border: 'none',
                background: 'linear-gradient(135deg, #0d9488, #2dd4bf)',
                color: 'white', fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer',
                opacity: loading ? 0.6 : 1, transition: 'opacity 0.2s',
              }}
            >
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p style={{ textAlign: 'center', color: '#64748b', fontSize: '0.85rem', marginTop: '1.5rem' }}>
            Already have an account?{' '}
            <Link href={`/login?next=${encodeURIComponent(next)}`} style={{ color: '#2dd4bf', textDecoration: 'none', fontWeight: 600 }}>
              Sign in
            </Link>
          </p>

          <p style={{ textAlign: 'center', color: '#475569', fontSize: '0.75rem', marginTop: '1rem' }}>
            By creating an account you agree to our terms of service and privacy policy.
          </p>
          <p style={{ textAlign: 'center', marginTop: '0.75rem' }}>
            <Link href="/pricing" style={{ color: '#64748b', textDecoration: 'none', fontSize: '0.8rem' }}>View pricing plans →</Link>
          </p>
        </div>
      </div>
    </main>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: '#0d1117' }} />}>
      <RegisterForm />
    </Suspense>
  );
}
