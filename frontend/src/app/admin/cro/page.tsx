'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, RefreshCw, Play, Square,
  Settings, Search, TrendingUp, BookOpen, Map as MapIcon, Building2,
} from 'lucide-react';
import { triggerCroEnrichment, fetchCroProgress, stopCroEnrichment } from '@/lib/api';

interface CroProgress {
  running: boolean;
  processed: number;
  total: number;
  errors: number;
  started_at: string | null;
  source: string | null;
}

export default function CroPage() {
  const [token, setToken] = useState('');
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState('');
  const [progress, setProgress] = useState<CroProgress | null>(null);
  const [polling, setPolling] = useState(false);
  const pollingRef = useRef(false);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      checkExistingProgress(saved);
    }
  }, []);

  // Polling effect
  useEffect(() => {
    pollingRef.current = polling;
    if (!polling || !token) return;

    const interval = setInterval(async () => {
      if (!pollingRef.current) return;
      try {
        const prog = await fetchCroProgress(token) as CroProgress;
        setProgress(prog);
        if (!prog.running) {
          setPolling(false);
          pollingRef.current = false;
        }
      } catch {
        setPolling(false);
        pollingRef.current = false;
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [polling, token]);

  const checkExistingProgress = async (t: string) => {
    try {
      const prog = await fetchCroProgress(t) as CroProgress;
      if (prog.running) {
        setProgress(prog);
        setPolling(true);
      }
    } catch {}
  };

  const handleTrigger = async () => {
    setTriggering(true);
    setMessage('');
    try {
      await triggerCroEnrichment(token);
      setMessage('CRO enrichment triggered');
      setProgress({
        running: true, processed: 0, total: 0, errors: 0,
        started_at: new Date().toISOString(), source: 'cro',
      });
      setPolling(true);
    } catch {
      setMessage('Failed to trigger CRO enrichment');
    } finally {
      setTriggering(false);
    }
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
          <ArrowLeft style={{ width: '16px', height: '16px' }} /> Back to Admin
        </Link>

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '2rem', fontFamily: "'Playfair Display', serif" }}>CRO Company Enrichment</h1>

        {message && (
          <div style={{ marginBottom: '1.25rem', padding: '0.75rem 1rem', background: '#ecfdf5', borderRadius: '8px', fontSize: '0.875rem', color: '#065f46', border: '1px solid #a7f3d0' }}>
            {message}
          </div>
        )}

        {/* Live Progress Counter */}
        {progress?.running && (
          <div style={{
            marginBottom: '1.25rem', padding: '1.25rem 1.5rem',
            background: '#eff6ff', border: '1px solid #3b82f6', borderRadius: '10px',
          }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <div style={{
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: '#3b82f6', animation: 'croPulse 1.2s ease-in-out infinite',
                }} />
                <span style={{ fontSize: '0.9rem', fontWeight: '600', color: '#1e40af' }}>
                  CRO enrichment running...
                </span>
              </div>
              <div style={{ fontSize: '2rem', fontWeight: '700', color: '#3b82f6', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                {progress.processed.toLocaleString()}
                {progress.total > 0 && (
                  <span style={{ fontSize: '1rem', color: '#6b7280', fontWeight: '400' }}>
                    {' '}/ {progress.total.toLocaleString()}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '4px' }}>
                applicants checked
                {progress.errors > 0 && (
                  <span style={{ color: '#dc2626', marginLeft: '12px' }}>
                    {progress.errors.toLocaleString()} errors
                  </span>
                )}
              </div>
              {progress.started_at && (
                <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '6px' }}>
                  Started {new Date(progress.started_at).toLocaleTimeString('en-IE')}
                </div>
              )}
            </div>
            <button
              onClick={async () => {
                try {
                  await stopCroEnrichment(token);
                  setMessage('Stop requested — enrichment will halt after current batch');
                } catch {}
              }}
              style={{
                padding: '0.5rem 1rem', background: '#dc2626', color: 'white',
                border: 'none', borderRadius: '8px', cursor: 'pointer',
                fontSize: '0.8rem', fontWeight: '600',
                display: 'flex', alignItems: 'center', gap: '0.35rem',
                flexShrink: 0,
              }}
            >
              <Square style={{ width: '14px', height: '14px' }} />
              Stop
            </button>
          </div>
          </div>
        )}

        {/* Completion banner */}
        {progress && !progress.running && progress.processed > 0 && (
          <div style={{
            marginBottom: '1.25rem', padding: '1rem 1.25rem',
            background: '#eff6ff', border: '1px solid #3b82f6', borderRadius: '10px',
          }}>
            <span style={{ color: '#1e40af', fontWeight: '600' }}>
              ✓ Enrichment complete — {progress.processed.toLocaleString()} applicants checked
            </span>
          </div>
        )}

        {/* CRO Enrichment Card */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Building2 style={{ width: '18px', height: '18px', color: '#3b82f6' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0 }}>CRO — Companies Registration Office</h3>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Look up company details from the Companies Registration Office for applicants
            that appear to be companies (Ltd, DAC, plc, CLG, Teoranta).
            Enriches applicant data with CRO registration numbers for corporate transparency.
          </p>
          <button
            className="btn-primary"
            onClick={handleTrigger}
            disabled={triggering || (progress?.running ?? false)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: '#3b82f6' }}
          >
            {triggering
              ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} />
              : <Play style={{ width: '16px', height: '16px' }} />
            }
            {triggering ? 'Starting...' : progress?.running ? 'Running...' : 'Run CRO Enrichment'}
          </button>
        </div>

        {/* How it works */}
        <div className="admin-card" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>How it works</h3>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: '1.7' }}>
            <ol style={{ paddingLeft: '1.25rem', margin: 0 }}>
              <li style={{ marginBottom: '0.5rem' }}>Finds applications where the applicant hasn&apos;t been checked yet</li>
              <li style={{ marginBottom: '0.5rem' }}>Filters for company-like names (containing Ltd, DAC, plc, CLG, Teoranta, etc.)</li>
              <li style={{ marginBottom: '0.5rem' }}>Looks up each company on the CRO register via API</li>
              <li style={{ marginBottom: '0.5rem' }}>Stores the CRO registration number against the application</li>
              <li>Marks non-company applicants as checked so they aren&apos;t retried</li>
            </ol>
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes croPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.3); }
        }
      `}</style>
    </main>
  );
}
