'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Database, ArrowLeft, Key, Eye, EyeOff, Save, CheckCircle } from 'lucide-react';
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
    <main className="min-h-screen bg-[var(--warm-white)]">
      <nav className="hero-gradient" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2 text-white no-underline">
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <span className="text-white/30">|</span>
          <span className="text-white/70 text-sm">API Keys</span>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-6">
        <Link href="/admin" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--teal)] mb-6 no-underline">
          <ArrowLeft className="w-4 h-4" /> Back to Admin
        </Link>

        <h1 className="text-2xl mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>API Key Management</h1>
        <p className="text-sm text-[var(--text-muted)] mb-6">
          Keys are encrypted using Fernet (AES-128-CBC + HMAC) and stored in the database.
          The master encryption key is stored as a server environment variable only.
        </p>

        {message && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-6 text-sm text-green-700 flex items-center gap-2">
            <CheckCircle className="w-4 h-4" /> {message}
          </div>
        )}

        {/* Claude API Key */}
        <div className="admin-card mb-6">
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
