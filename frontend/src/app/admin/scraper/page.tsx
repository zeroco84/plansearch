'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, RefreshCw, Play, Square,
  Settings, Search, TrendingUp, BookOpen, Map as MapIcon, Users,
} from 'lucide-react';
import { startApplicantScraper, stopApplicantScraper, fetchApplicantScraperProgress } from '@/lib/api';

interface ScraperProgress {
  running: boolean;
  scraped_today: number;
  names_found_today: number;
  last_scraped_ref: string | null;
  started_at: string | null;
  error: string | null;
}

export default function ScraperPage() {
  const [token, setToken] = useState('');
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState('');
  const [progress, setProgress] = useState<ScraperProgress | null>(null);
  const [polling, setPolling] = useState(false);
  const pollingRef = useRef(false);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      checkExistingProgress(saved);
    }
  }, []);

  // Polling effect — every 10 seconds when running
  useEffect(() => {
    pollingRef.current = polling;
    if (!polling || !token) return;

    const interval = setInterval(async () => {
      if (!pollingRef.current) return;
      try {
        const prog = await fetchApplicantScraperProgress(token) as ScraperProgress;
        setProgress(prog);
        if (!prog.running) {
          setPolling(false);
          pollingRef.current = false;
        }
      } catch {
        setPolling(false);
        pollingRef.current = false;
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [polling, token]);

  const checkExistingProgress = async (t: string) => {
    try {
      const prog = await fetchApplicantScraperProgress(t) as ScraperProgress;
      setProgress(prog);
      if (prog.running) {
        setPolling(true);
      }
    } catch {}
  };

  const handleStart = async () => {
    setTriggering(true);
    setMessage('');
    try {
      await startApplicantScraper(token);
      setMessage('Scraper started');
      setProgress({
        running: true, scraped_today: 0, names_found_today: 0,
        last_scraped_ref: null, started_at: new Date().toISOString(), error: null,
      });
      setPolling(true);
    } catch {
      setMessage('Failed to start scraper');
    } finally {
      setTriggering(false);
    }
  };

  const handleStop = async () => {
    try {
      await stopApplicantScraper(token);
      setMessage('Stop requested — scraper will halt after current request');
      if (progress) setProgress({ ...progress, running: false });
      setPolling(false);
    } catch {
      setMessage('Failed to stop scraper');
    }
  };

  const successRate = progress && progress.scraped_today > 0
    ? Math.round((progress.names_found_today / progress.scraped_today) * 100)
    : 0;

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

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '2rem', fontFamily: "'Playfair Display', serif" }}>Applicant Name Scraper</h1>

        {message && (
          <div style={{ marginBottom: '1.25rem', padding: '0.75rem 1rem', background: '#ecfdf5', borderRadius: '8px', fontSize: '0.875rem', color: '#065f46', border: '1px solid #a7f3d0' }}>
            {message}
          </div>
        )}

        {progress?.error && (
          <div style={{ marginBottom: '1.25rem', padding: '0.75rem 1rem', background: '#fef2f2', borderRadius: '8px', fontSize: '0.875rem', color: '#b91c1c', border: '1px solid #fca5a5' }}>
            Scraper error: {progress.error}
          </div>
        )}

        {/* Live Progress Counter */}
        {progress?.running && (
          <div style={{
            marginBottom: '1.25rem', padding: '1.25rem 1.5rem',
            background: '#faf5ff', border: '1px solid #8b5cf6', borderRadius: '10px',
          }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <div style={{
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: '#8b5cf6', animation: 'scraperPulse 1.2s ease-in-out infinite',
                }} />
                <span style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5b21b6' }}>
                  Scraper running continuously
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '1.5rem' }}>
                <div>
                  <div style={{ fontSize: '2rem', fontWeight: '700', color: '#8b5cf6', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                    {progress.names_found_today.toLocaleString()}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '2px' }}>
                    names found
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#6b7280', lineHeight: 1.1 }}>
                    {progress.scraped_today.toLocaleString()}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '2px' }}>
                    pages scraped ({successRate}% hit rate)
                  </div>
                </div>
              </div>
              {progress.last_scraped_ref && (
                <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '8px' }}>
                  Last: {progress.last_scraped_ref}
                </div>
              )}
              {progress.started_at && (
                <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '2px' }}>
                  Started {new Date(progress.started_at).toLocaleTimeString('en-IE')}
                </div>
              )}
            </div>
            <button
              onClick={handleStop}
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

        {/* Completion/stopped banner */}
        {progress && !progress.running && progress.scraped_today > 0 && (
          <div style={{
            marginBottom: '1.25rem', padding: '1rem 1.25rem',
            background: '#faf5ff', border: '1px solid #8b5cf6', borderRadius: '10px',
          }}>
            <span style={{ color: '#5b21b6', fontWeight: '600' }}>
              Scraper stopped — {progress.names_found_today.toLocaleString()} names found from {progress.scraped_today.toLocaleString()} pages
            </span>
          </div>
        )}

        {/* Main Card */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Users style={{ width: '18px', height: '18px', color: '#8b5cf6' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0 }}>Continuous Applicant Scraper</h3>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Scrapes applicant names from ePlanning.ie and Agile Applications portals.
            Runs continuously at 1 request per 4 seconds (~900/hour, ~21,600/day).
            Starts with 2023+ applications, then works backwards through the full dataset.
          </p>
          <button
            className="btn-primary"
            onClick={progress?.running ? handleStop : handleStart}
            disabled={triggering}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
              background: progress?.running ? '#dc2626' : '#8b5cf6',
            }}
          >
            {triggering
              ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} />
              : progress?.running
                ? <Square style={{ width: '16px', height: '16px' }} />
                : <Play style={{ width: '16px', height: '16px' }} />
            }
            {triggering ? 'Starting...' : progress?.running ? 'Stop Scraper' : 'Start Scraper'}
          </button>
        </div>

        {/* Portal Coverage */}
        <div className="admin-card" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>Portal Coverage</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div style={{ padding: '1rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.5rem', color: '#8b5cf6' }}>ePlanning.ie</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.6' }}>
                Carlow, Clare, Donegal, Galway, Kerry, Kildare, Kilkenny, Laois, Leitrim,
                Limerick, Longford, Louth, Mayo, Meath, Monaghan, Offaly, Roscommon, Sligo,
                Tipperary, Waterford, Westmeath, Wexford, Wicklow, Cavan
              </div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.5rem', color: '#8b5cf6' }}>Agile Applications</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.6' }}>
                Dublin City Council, Fingal, Dún Laoghaire-Rathdown, South Dublin
              </div>
              <div style={{ fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.5rem', marginTop: '1rem', color: '#9ca3af' }}>Cork City — skipped</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Separate system, excluded from scraper
              </div>
            </div>
          </div>
          <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#faf5ff', borderRadius: '8px', fontSize: '0.8rem', color: '#5b21b6' }}>
            <strong>Rate:</strong> 1 request per 4 seconds = ~900/hour = ~21,600/day.
            The ~40,000 post-2023 records will complete in approximately 2 days of continuous running.
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes scraperPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.3); }
        }
      `}</style>
    </main>
  );
}
