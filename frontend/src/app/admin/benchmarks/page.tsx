'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Database, ArrowLeft, RefreshCw, Play, DollarSign,
  Settings, Search, TrendingUp, BookOpen, Map as MapIcon, ExternalLink,
, BarChart3 } from 'lucide-react';
import { triggerBenchmarkScrape, getBenchmarks } from '@/lib/api';

const BUILDING_TYPE_LABELS: Record<string, string> = {
  residential_new_build: 'Residential (New Build)',
  residential_extension: 'Residential Extension',
  hotel_accommodation: 'Hotel / Accommodation',
  commercial_office: 'Commercial Office',
  commercial_retail: 'Commercial Retail',
  industrial_warehouse: 'Industrial / Warehouse',
  student_accommodation: 'Student Accommodation',
  data_centre: 'Data Centre',
};

export default function BenchmarksPage() {
  const [token, setToken] = useState('');
  const [benchmarks, setBenchmarks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [scraping, setScraping] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('plansearch_admin_token');
    if (saved) {
      setToken(saved);
      loadBenchmarks(saved);
    }
  }, []);

  const loadBenchmarks = async (t: string) => {
    setLoading(true);
    try {
      const data = await getBenchmarks(t) as any;
      setBenchmarks(data.benchmarks || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleScrape = async () => {
    setScraping(true);
    setMessage('');
    try {
      await triggerBenchmarkScrape(token);
      setMessage('Benchmark scrape triggered — Claude is extracting from PDFs...');
      setTimeout(() => loadBenchmarks(token), 30000);
    } catch (err) {
      setMessage('Failed to trigger benchmark scrape');
    } finally {
      setScraping(false);
    }
  };

  const formatCurrency = (val: number | null) => {
    if (!val) return '—';
    return `€${val.toLocaleString()}`;
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

      <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '2rem 2rem 4rem' }}>
        <Link href="/admin" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.875rem', color: 'var(--text-muted)', textDecoration: 'none', marginBottom: '1.5rem' }}>
          <ArrowLeft style={{ width: '16px', height: '16px' }} /> Back to Admin
        </Link>

        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '0.5rem', fontFamily: "'Playfair Display', serif" }}>
          Cost Benchmarks
        </h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.5rem', lineHeight: '1.5' }}>
          Sourced from{' '}
          <a
            href="https://mitchellmcdermott.com/infocards/"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--teal)', textDecoration: 'none' }}
          >
            Mitchell McDermott InfoCards
            <ExternalLink style={{ width: '12px', height: '12px', display: 'inline', marginLeft: '3px', verticalAlign: 'middle' }} />
          </a>
          . Published annually in January. Extracted via Claude AI.
        </p>

        {message && (
          <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', background: '#ecfdf5', borderRadius: '8px', fontSize: '0.875rem', color: '#065f46', border: '1px solid #a7f3d0' }}>
            {message}
          </div>
        )}

        {/* Scrape Control */}
        <div className="admin-card" style={{ marginBottom: '1.5rem', padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <DollarSign style={{ width: '18px', height: '18px', color: '#059669' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: '600', margin: 0 }}>
              Extract from{' '}
              <a href="https://mitchellmcdermott.com/infocards/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--teal)', textDecoration: 'none' }}>
                Mitchell McDermott
              </a>
            </h3>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.5' }}>
            Downloads InfoCard PDFs and uses Claude to extract structured cost benchmarks.
            Covers residential, hotel, office, industrial, student accommodation, and data centres.
          </p>
          <button
            className="btn-primary"
            onClick={handleScrape}
            disabled={scraping}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            {scraping ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Play style={{ width: '16px', height: '16px' }} />}
            {scraping ? 'Extracting...' : 'Scrape InfoCard PDFs'}
          </button>
        </div>

        {/* Benchmarks Table */}
        <div className="admin-card" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>
            Current Benchmarks ({benchmarks.length})
          </h3>

          {loading ? (
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Loading...</p>
          ) : benchmarks.length === 0 ? (
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              No benchmarks stored yet. Trigger a scrape from{' '}
              <a href="https://mitchellmcdermott.com/infocards/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--teal)' }}>
                Mitchell McDermott
              </a>
              {' '}above.
            </p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                    <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.7rem', textTransform: 'uppercase' }}>Type</th>
                    <th style={{ textAlign: 'right', padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.7rem', textTransform: 'uppercase' }}>€/m² Low</th>
                    <th style={{ textAlign: 'right', padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.7rem', textTransform: 'uppercase' }}>€/m² High</th>
                    <th style={{ textAlign: 'right', padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.7rem', textTransform: 'uppercase' }}>€/unit Low</th>
                    <th style={{ textAlign: 'right', padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.7rem', textTransform: 'uppercase' }}>€/unit High</th>
                    <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.7rem', textTransform: 'uppercase' }}>Source</th>
                    <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.7rem', textTransform: 'uppercase' }}>Valid From</th>
                  </tr>
                </thead>
                <tbody>
                  {benchmarks.map((b: any, i: number) => (
                    <tr key={b.id || i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '0.5rem 0.75rem', fontWeight: '500' }}>
                        {BUILDING_TYPE_LABELS[b.building_type] || b.building_type}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', textAlign: 'right', color: '#059669', fontWeight: '600' }}>
                        {formatCurrency(b.cost_per_sqm_low)}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', textAlign: 'right', color: '#059669', fontWeight: '600' }}>
                        {formatCurrency(b.cost_per_sqm_high)}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', textAlign: 'right' }}>
                        {formatCurrency(b.cost_per_unit_low)}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', textAlign: 'right' }}>
                        {formatCurrency(b.cost_per_unit_high)}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {b.infocard_name || 'Mitchell McDermott'}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {b.valid_from || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Exclusions disclaimer */}
          {benchmarks.length > 0 && benchmarks[0]?.exclusions && (
            <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#fffbeb', borderRadius: '8px', border: '1px solid #fde68a' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#92400e', marginBottom: '0.25rem' }}>
                ⚠ Exclusions (not included in above costs):
              </div>
              <div style={{ fontSize: '0.75rem', color: '#92400e', lineHeight: '1.5' }}>
                {benchmarks[0].exclusions.join(' • ')}
              </div>
            </div>
          )}

          <div style={{ marginTop: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Cost benchmarks sourced from{' '}
            <a href="https://mitchellmcdermott.com/infocards/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--teal)', textDecoration: 'none' }}>
              Mitchell McDermott InfoCards
            </a>
            . Published annually in January.
          </div>
        </div>
      </div>
    </main>
  );
}
