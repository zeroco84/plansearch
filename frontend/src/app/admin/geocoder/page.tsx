'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, RefreshCw, Play, Square,
  Settings, Search, TrendingUp, BookOpen, Map as MapIcon,
} from 'lucide-react';
import { startGeocoder, stopGeocoder, fetchGeocoderProgress } from '@/lib/api';

interface GeocoderProgress {
  running: boolean;
  geocoded_today: number;
  found_today: number;
  last_ref: string | null;
  started_at: string | null;
  error: string | null;
}

export default function GeocoderPage() {
  const [token, setToken] = useState('');
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState('');
  const [progress, setProgress] = useState<GeocoderProgress | null>(null);
  const [polling, setPolling] = useState(false);
  const pollingRef = useRef(false);

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      checkExistingProgress(saved);
    }
  }, []);

  useEffect(() => {
    pollingRef.current = polling;
    if (!polling || !token) return;

    const interval = setInterval(async () => {
      if (!pollingRef.current) return;
      try {
        const prog = await fetchGeocoderProgress(token) as GeocoderProgress;
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
      const prog = await fetchGeocoderProgress(t) as GeocoderProgress;
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
      await startGeocoder(token);
      setMessage('Geocoder started');
      setProgress({
        running: true, geocoded_today: 0, found_today: 0,
        last_ref: null, started_at: new Date().toISOString(), error: null,
      });
      setPolling(true);
    } catch {
      setMessage('Failed to start geocoder');
    } finally {
      setTriggering(false);
    }
  };

  const handleStop = async () => {
    try {
      await stopGeocoder(token);
      setMessage('Stop requested — geocoder will halt after current request');
      if (progress) setProgress({ ...progress, running: false });
      setPolling(false);
    } catch {
      setMessage('Failed to stop geocoder');
    }
  };

  const hitRate = progress && progress.geocoded_today > 0
    ? Math.round((progress.found_today / progress.geocoded_today) * 100)
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
            <Link href="/insights" className="nav-link"><BookOpen className="w-5 h-5" /><span className="hidden sm:inline">Insights</span></Link>
            <Link href="/admin" className="nav-link" style={{ color: 'var(--teal)' }}><Settings className="w-5 h-5" /><span className="hidden sm:inline">Admin</span></Link>
          </div>
        </div>
      </nav>

      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem 2rem 4rem' }}>
        <Link href="/admin" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.875rem', color: 'var(--text-muted)', textDecoration: 'none', marginBottom: '1.5rem' }}>
          <ArrowLeft style={{ width: '16px', height: '16px' }} /> Back to Admin
        </Link>

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '2rem', fontFamily: "'Playfair Display', serif" }}>Address Geocoder</h1>

        {message && (
          <div style={{ marginBottom: '1.25rem', padding: '0.75rem 1rem', background: '#ecfdf5', borderRadius: '8px', fontSize: '0.875rem', color: '#065f46', border: '1px solid #a7f3d0' }}>
            {message}
          </div>
        )}

        {progress?.error && (
          <div style={{ marginBottom: '1.25rem', padding: '0.75rem 1rem', background: '#fef2f2', borderRadius: '8px', fontSize: '0.875rem', color: '#b91c1c', border: '1px solid #fca5a5' }}>
            Geocoder error: {progress.error}
          </div>
        )}

        {/* Live Progress Counter */}
        {progress?.running && (
          <div style={{
            marginBottom: '1.25rem', padding: '1.25rem 1.5rem',
            background: '#ecfdf5', border: '1px solid #22c55e', borderRadius: '10px',
          }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <div style={{
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: '#22c55e', animation: 'geocodePulse 1.2s ease-in-out infinite',
                }} />
                <span style={{ fontSize: '0.9rem', fontWeight: '600', color: '#166534' }}>
                  Geocoder running continuously
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '1.5rem' }}>
                <div>
                  <div style={{ fontSize: '2rem', fontWeight: '700', color: '#22c55e', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                    {progress.found_today.toLocaleString()}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '2px' }}>
                    coordinates found
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#6b7280', lineHeight: 1.1 }}>
                    {progress.geocoded_today.toLocaleString()}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '2px' }}>
                    addresses checked ({hitRate}% hit rate)
                  </div>
                </div>
              </div>
              {progress.last_ref && (
                <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '8px' }}>
                  Last: {progress.last_ref}
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

        {/* Stopped banner */}
        {progress && !progress.running && progress.geocoded_today > 0 && (
          <div style={{
            marginBottom: '1.25rem', padding: '1rem 1.25rem',
            background: '#ecfdf5', border: '1px solid #22c55e', borderRadius: '10px',
          }}>
            <span style={{ color: '#166534', fontWeight: '600' }}>
              Geocoder stopped — {progress.found_today.toLocaleString()} coordinates found from {progress.geocoded_today.toLocaleString()} addresses
            </span>
          </div>
        )}

        {/* Main Card */}
        <div className="admin-card" style={{ marginBottom: '1.25rem', padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <MapIcon style={{ width: '18px', height: '18px', color: '#22c55e' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0 }}>OSM Nominatim Geocoder</h3>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Geocodes planning application addresses using OpenStreetMap Nominatim (free, no API key).
            Runs continuously at 1 request per second per OSM usage policy.
            Results are validated against the Ireland bounding box (51.2°N–55.5°N, 5.9°W–10.7°W).
          </p>
          <button
            className="btn-primary"
            onClick={progress?.running ? handleStop : handleStart}
            disabled={triggering}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
              background: progress?.running ? '#dc2626' : '#22c55e',
            }}
          >
            {triggering
              ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} />
              : progress?.running
                ? <Square style={{ width: '16px', height: '16px' }} />
                : <Play style={{ width: '16px', height: '16px' }} />
            }
            {triggering ? 'Starting...' : progress?.running ? 'Stop Geocoder' : 'Start Geocoder'}
          </button>
        </div>

        {/* How it works */}
        <div className="admin-card" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>How it works</h3>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: '1.7' }}>
            <ol style={{ paddingLeft: '1.25rem', margin: 0 }}>
              <li style={{ marginBottom: '0.5rem' }}>Finds applications with a text address but no map coordinates</li>
              <li style={{ marginBottom: '0.5rem' }}>Sends the address to OpenStreetMap Nominatim with country filter &quot;ie&quot;</li>
              <li style={{ marginBottom: '0.5rem' }}>Validates the returned lat/lng falls within Ireland&apos;s bounding box</li>
              <li style={{ marginBottom: '0.5rem' }}>Stores the PostGIS point geometry for map display</li>
              <li>Marks each address as processed (even if no result) to avoid retrying</li>
            </ol>
          </div>
          <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#ecfdf5', borderRadius: '8px', fontSize: '0.8rem', color: '#166534' }}>
            <strong>Rate:</strong> 1 request per 1.1 seconds = ~3,270/hour = ~78,500/day.
            Much faster than the applicant scraper since Nominatim allows higher throughput.
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes geocodePulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.3); }
        }
      `}</style>
    </main>
  );
}
