'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, Key, Eye, EyeOff, Save, CheckCircle, Settings, Search, TrendingUp, BookOpen, Map as MapIcon } from 'lucide-react';
import { updateApiKey, getAdminConfig } from '@/lib/api';

export default function KeysPage() {
  const [token, setToken] = useState('');
  const [claudeKey, setClaudeKey] = useState('');
  const [croKey, setCroKey] = useState('');
  const [showClaude, setShowClaude] = useState(false);
  const [showCro, setShowCro] = useState(false);
  const [configs, setConfigs] = useState<any[]>([]);
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) { setToken(saved); loadConfigs(saved); }
  }, []);

  const loadConfigs = async (t: string) => {
    try {
      const data = await getAdminConfig(t);
      if (Array.isArray(data)) setConfigs(data);
    } catch {}
  };

  const handleSave = async (keyType: 'claude' | 'cro', value: string) => {
    if (!value.trim()) return;
    setSaving(true);
    try {
      await updateApiKey(token, keyType, value);
      setMessage(`${keyType.toUpperCase()} key updated successfully`);
      if (keyType === 'claude') setClaudeKey('');
      if (keyType === 'cro') setCroKey('');
      loadConfigs(token);
      setTimeout(() => setMessage(''), 3000);
    } catch {
      setMessage('Failed to update key');
    }
    setSaving(false);
  };

  const claudeConfig = configs.find((c: any) => c.key === 'claude_api_key');
  const croConfig = configs.find((c: any) => c.key === 'cro_api_key');

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

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '0.5rem', fontFamily: "'Playfair Display', serif" }}>API Key Management</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
          Keys are encrypted using Fernet (AES-128-CBC + HMAC) and stored in the database.
          The master encryption key is stored as a server environment variable only.
        </p>

        {message && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700 flex items-center gap-2" style={{ marginBottom: '1.25rem' }}>
            <CheckCircle className="w-4 h-4" /> {message}
          </div>
        )}

        {/* Claude API Key */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <div className="flex items-center gap-2 mb-4">
            <Key className="w-5 h-5 text-purple-500" />
            <h3 className="text-base font-semibold">Claude API Key</h3>
          </div>
          {claudeConfig && (
            <div className="mb-3 p-2 bg-[var(--warm-white)] rounded-lg text-sm font-mono">
              Current: {claudeConfig.value_masked}
              <span className="text-xs text-[var(--text-muted)] ml-2">
                Updated: {claudeConfig.updated_at ? new Date(claudeConfig.updated_at).toLocaleString() : '—'}
              </span>
            </div>
          )}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type={showClaude ? 'text' : 'password'}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--warm-white)] text-sm pr-10 focus:outline-none focus:border-[var(--teal)]"
                placeholder="sk-ant-..."
                value={claudeKey}
                onChange={(e) => setClaudeKey(e.target.value)}
              />
              <button
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                onClick={() => setShowClaude(!showClaude)}
              >
                {showClaude ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <button
              className="btn-primary"
              onClick={() => handleSave('claude', claudeKey)}
              disabled={saving || !claudeKey.trim()}
            >
              <Save className="w-4 h-4" /> Update
            </button>
          </div>
        </div>

        {/* CRO API Key */}
        <div className="admin-card">
          <div className="flex items-center gap-2 mb-4">
            <Key className="w-5 h-5 text-amber-500" />
            <h3 className="text-base font-semibold">CRO API Key</h3>
          </div>
          {croConfig && (
            <div className="mb-3 p-2 bg-[var(--warm-white)] rounded-lg text-sm font-mono">
              Current: {croConfig.value_masked}
            </div>
          )}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type={showCro ? 'text' : 'password'}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--warm-white)] text-sm pr-10 focus:outline-none focus:border-[var(--teal)]"
                placeholder="cro-api-key-..."
                value={croKey}
                onChange={(e) => setCroKey(e.target.value)}
              />
              <button
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                onClick={() => setShowCro(!showCro)}
              >
                {showCro ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <button
              className="btn-primary"
              onClick={() => handleSave('cro', croKey)}
              disabled={saving || !croKey.trim()}
            >
              <Save className="w-4 h-4" /> Update
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
