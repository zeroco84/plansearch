'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, MapPin, Calendar, Building2, FileText, Scale,
  ExternalLink, Clock, CheckCircle, AlertCircle, XCircle,
  Database, Settings, Map as MapIcon, Download, Search,
  TrendingUp, BookOpen,
} from 'lucide-react';
import {
  getApplication, ApplicationDetail,
  CATEGORY_LABELS, formatDate, formatFileSize, formatValue, getPortalDocumentUrl,
} from '@/lib/api';


/* ── Decision helpers ────────────────────────────────────────────── */

function getDecisionClass(decision: string | null): string {
  if (!decision) return 'decision-pending';
  const upper = decision.toUpperCase();
  if (upper.includes('GRANT')) return 'decision-granted';
  if (upper.includes('REFUS')) return 'decision-refused';
  if (upper.includes('FURTHER') || upper.includes('INFO')) return 'decision-further-info';
  if (upper.includes('SPLIT')) return 'decision-split';
  if (upper.includes('WITHDRAW')) return 'decision-withdrawn';
  return 'decision-pending';
}

function getDecisionLabel(decision: string | null): string {
  if (!decision) return 'Pending';
  const upper = decision.toUpperCase();
  if (upper.includes('GRANT')) return 'Granted ✓';
  if (upper.includes('REFUS')) return 'Refused ✗';
  if (upper.includes('FURTHER') || upper.includes('INFO')) return 'Further Info';
  if (upper.includes('SPLIT')) return 'Split Decision';
  if (upper.includes('WITHDRAW')) return 'Withdrawn';
  return decision;
}


/* ── Document icon helper ────────────────────────────────────────── */

function getDocIcon(docName: string): string {
  const name = docName.toLowerCase();
  if (name.includes('plan') || name.includes('elevation') || name.includes('drawing')) return '📐';
  if (name.includes('report') || name.includes('decision') || name.includes('grant')) return '📋';
  if (name.includes('notice') || name.includes('newspaper')) return '📰';
  if (name.includes('observation') || name.includes('submission')) return '💬';
  if (name.includes('site')) return '🏠';
  return '📄';
}


/* ── Format long proposal text with structure ────────────────────── */

function formatProposal(text: string): React.ReactElement[] {
  if (!text) return [];

  const elements: React.ReactElement[] = [];

  // Split on common patterns that indicate list items or paragraph breaks
  // Patterns: "i.", "ii.", "iii.", "iv.", "(a)", "(b)", "(1)", "(2)", numbered "1.", "2."
  // Also split on double newlines, bullet chars, and "•"
  const lines = text
    .replace(/\r\n/g, '\n')
    // Insert line breaks before numbered items
    .replace(/(?<=[.;])\s+(?=(i{1,3}v?|vi{0,3}|[a-z])\.\s)/gi, '\n')
    .replace(/(?<=[.;])\s+(?=\([a-z0-9]+\)\s)/gi, '\n')
    .replace(/(?<=[.;])\s+(?=\d+\.\s)/g, '\n')
    .replace(/(?<=[.;])\s+(?=•\s)/g, '\n')
    .split('\n')
    .map(l => l.trim())
    .filter(Boolean);

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Check if it looks like a list item
    const isListItem =
      /^(i{1,3}v?|vi{0,3})\.\s/i.test(line) ||   // i. ii. iii. iv. v. vi.
      /^\([a-z0-9]+\)\s/i.test(line) ||              // (a) (b) (1) (2)
      /^\d+\.\s/.test(line) ||                        // 1. 2. 3.
      /^•\s/.test(line) ||                            // bullet
      /^[-–—]\s/.test(line);                          // dash

    if (isListItem) {
      elements.push(
        <div key={i} style={{
          paddingLeft: '1.25rem',
          position: 'relative',
          marginBottom: '0.35rem',
          fontSize: '0.875rem',
          lineHeight: '1.6',
          color: 'var(--text-secondary)',
        }}>
          <span style={{
            position: 'absolute',
            left: 0,
            color: 'var(--teal)',
            fontWeight: 600,
          }}>›</span>
          {line.replace(/^(i{1,3}v?|vi{0,3})\.\s/i, '')
            .replace(/^\([a-z0-9]+\)\s/i, '')
            .replace(/^\d+\.\s/, '')
            .replace(/^[•\-–—]\s/, '')}
        </div>
      );
    } else {
      elements.push(
        <p key={i} style={{
          fontSize: '0.875rem',
          lineHeight: '1.7',
          color: 'var(--text-secondary)',
          marginBottom: '0.5rem',
        }}>
          {line}
        </p>
      );
    }
  }

  return elements;
}


/* ── Shared Nav ──────────────────────────────────────────────────── */

function AppNav() {
  return (
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
          <Link href="/admin" className="nav-link"><Settings className="w-5 h-5" /><span className="hidden sm:inline">Admin</span></Link>
        </div>
      </div>
    </nav>
  );
}


/* ── Page Component ──────────────────────────────────────────────── */

export default function ApplicationPage() {
  const params = useParams();
  const regRef = typeof params?.ref === 'string' ? decodeURIComponent(params.ref) : '';

  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFullProposal, setShowFullProposal] = useState(false);

  useEffect(() => {
    if (!regRef) return;

    async function load() {
      try {
        const data = await getApplication(regRef);
        setApp(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load application');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [regRef]);

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', background: 'var(--warm-white)' }}>
        <AppNav />
        <div style={{ maxWidth: '56rem', margin: '0 auto', padding: '2rem 1rem' }}>
          <div className="skeleton" style={{ height: '2rem', width: '12rem', marginBottom: '1rem' }} />
          <div className="skeleton" style={{ height: '1.5rem', width: '24rem', marginBottom: '1rem' }} />
          <div className="skeleton" style={{ height: '8rem', width: '100%' }} />
        </div>
      </main>
    );
  }

  if (error || !app) {
    return (
      <main style={{ minHeight: '100vh', background: 'var(--warm-white)' }}>
        <AppNav />
        <div style={{ maxWidth: '56rem', margin: '0 auto', padding: '4rem 1rem', textAlign: 'center' }}>
          <AlertCircle style={{ width: '3rem', height: '3rem', color: '#f87171', margin: '0 auto 1rem' }} />
          <h2 style={{ fontSize: '1.25rem', fontFamily: "'Playfair Display', serif" }}>Application Not Found</h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>{error}</p>
          <Link href="/" className="btn-primary" style={{ display: 'inline-flex', marginTop: '1.5rem' }}>
            <ArrowLeft style={{ width: '1rem', height: '1rem' }} /> Back to Search
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: '100vh', background: 'var(--warm-white)' }}>
      <AppNav />

      <div style={{ maxWidth: '56rem', margin: '0 auto', padding: '1.5rem 1rem 3rem' }}>
        {/* Back link */}
        <Link
          href="/"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
            fontSize: '0.875rem', color: 'var(--text-muted)',
            textDecoration: 'none', marginBottom: '1rem',
          }}
        >
          <ArrowLeft style={{ width: '1rem', height: '1rem' }} /> Back to search
        </Link>

        {/* Header Card */}
        <div className="detail-section fade-in">
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'start', justifyContent: 'space-between', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span className="reg-ref-badge" style={{ fontSize: '0.9rem' }}>{app.reg_ref}</span>
              <span className={`decision-chip ${getDecisionClass(app.decision)}`} style={{ fontSize: '0.85rem' }}>
                {getDecisionLabel(app.decision)}
              </span>
              {app.planning_authority && (
                <span style={{
                  fontSize: '0.7rem', color: 'var(--text-muted)',
                  background: 'var(--warm-white)', padding: '0.2rem 0.5rem',
                  borderRadius: '4px', fontWeight: 500,
                }}>
                  {app.planning_authority}
                </span>
              )}
            </div>
            <a
              href={getPortalDocumentUrl(app.reg_ref, app.year)}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary"
              style={{ fontSize: '0.8rem', textDecoration: 'none', flexShrink: 0 }}
            >
              <ExternalLink style={{ width: '0.875rem', height: '0.875rem' }} />
              View on Portal
            </a>
          </div>

          {app.location && (
            <div style={{ display: 'flex', alignItems: 'start', gap: '0.5rem', marginTop: '0.75rem' }}>
              <MapPin style={{ width: '1rem', height: '1rem', color: 'var(--teal)', marginTop: '0.15rem', flexShrink: 0 }} />
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, lineHeight: 1.4, fontFamily: "'Playfair Display', serif", margin: 0 }}>
                {app.location}
              </h2>
            </div>
          )}

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginTop: '0.6rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <Calendar style={{ width: '0.875rem', height: '0.875rem' }} /> Applied: {formatDate(app.apn_date)}
            </span>
            {app.dec_date && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Scale style={{ width: '0.875rem', height: '0.875rem' }} /> Decided: {formatDate(app.dec_date)}
              </span>
            )}
            {app.app_type && (
              <span>Type: {app.app_type}</span>
            )}
          </div>
        </div>

        {/* Applicant & Company */}
        {(app.applicant_name || app.company) && (
          <div className="detail-section fade-in" style={{ animationDelay: '60ms' }}>
            <h3>APPLICANT</h3>
            {app.applicant_name && (
              <p style={{ fontSize: '0.95rem', fontWeight: 600, margin: '0 0 0.5rem' }}>{app.applicant_name}</p>
            )}
            {app.company && (
              <div style={{ padding: '0.75rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <Building2 style={{ width: '1rem', height: '1rem', color: 'var(--teal)' }} />
                  <span style={{ fontWeight: 600 }}>{app.company.company_name}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.35rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  <span>CRO: {app.company.cro_number}</span>
                  {app.company.company_status && <span>Status: {app.company.company_status}</span>}
                  {app.company.incorporation_date && <span>Registered: {formatDate(app.company.incorporation_date)}</span>}
                  {app.company.company_type && <span>Type: {app.company.company_type}</span>}
                </div>
                {app.company.registered_address && (
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>📍 {app.company.registered_address}</p>
                )}
                {app.company.directors && app.company.directors.length > 0 && (
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Directors: {app.company.directors.join(', ')}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Development Description */}
        <div className="detail-section fade-in" style={{ animationDelay: '120ms' }}>
          <h3>DEVELOPMENT DESCRIPTION</h3>
          {app.dev_category && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
              <span className="category-tag" style={{ fontSize: '0.8rem' }}>
                {CATEGORY_LABELS[app.dev_category] || app.dev_category}
              </span>
              {app.dev_subcategory && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>› {app.dev_subcategory}</span>
              )}
              {app.classification_confidence && (
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  ({(app.classification_confidence * 100).toFixed(0)}% confidence)
                </span>
              )}
            </div>
          )}

          {/* Show AI summary if available */}
          {app.proposal_summary && (
            <div style={{ marginBottom: '0.75rem' }}>
              <p style={{
                fontSize: '0.95rem',
                lineHeight: '1.65',
                color: 'var(--text-primary)',
                fontWeight: 500,
                margin: 0,
              }}>
                {app.proposal_summary}
              </p>
              <button
                onClick={() => setShowFullProposal(!showFullProposal)}
                style={{
                  marginTop: '0.5rem',
                  fontSize: '0.75rem',
                  color: 'var(--teal)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {showFullProposal ? '▲ Hide full description' : '▼ Show full planning description'}
              </button>
              {showFullProposal && (
                <div style={{
                  marginTop: '0.75rem',
                  borderLeft: '3px solid var(--border)',
                  paddingLeft: '1rem',
                }}>
                  {formatProposal(app.long_proposal || app.proposal || '')}
                </div>
              )}
            </div>
          )}

          {/* Fallback — no summary yet, show full proposal with formatting */}
          {!app.proposal_summary && (
            <div>
              {formatProposal(app.long_proposal || app.proposal || 'No description available')}
            </div>
          )}
        </div>

        {/* Key Facts — show NPAD fields if available */}
        {(app.area_of_site || app.num_residential_units || app.floor_area) && (
          <div className="detail-section fade-in" style={{ animationDelay: '150ms' }}>
            <h3>KEY FACTS</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
              {app.area_of_site && app.area_of_site > 0 && (app.area_of_site / 10000) <= 500 && (
                <div style={{ background: 'var(--warm-white)', padding: '0.75rem', borderRadius: '8px' }}>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal)' }}>
                    {(app.area_of_site / 10000) >= 0.01
                      ? `${(app.area_of_site / 10000).toFixed(2)} ha`
                      : `${Math.round(app.area_of_site).toLocaleString()} m²`}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Site Area</div>
                </div>
              )}
              {app.num_residential_units && (
                <div style={{ background: 'var(--warm-white)', padding: '0.75rem', borderRadius: '8px' }}>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal)' }}>{app.num_residential_units}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Residential Units</div>
                </div>
              )}
              {app.floor_area && (
                <div style={{ background: 'var(--warm-white)', padding: '0.75rem', borderRadius: '8px' }}>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal)' }}>{app.floor_area.toLocaleString()} m²</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Floor Area</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Estimated Construction Value */}
        {app.est_value_high && (
          <div className="detail-section fade-in" style={{ animationDelay: '165ms' }}>
            <h3>ESTIMATED CONSTRUCTION VALUE</h3>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', margin: '0.75rem 0' }}>
              <span style={{ fontSize: '1.75rem', fontWeight: '700', color: '#059669' }}>
                {formatValue(app.est_value_low)}
              </span>
              <span style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>—</span>
              <span style={{ fontSize: '1.75rem', fontWeight: '700', color: '#059669' }}>
                {formatValue(app.est_value_high)}
              </span>
            </div>
            {app.est_value_basis && (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                {app.est_value_basis}
              </div>
            )}
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
              Construction cost estimate based on{' '}
              <a
                href="https://mitchellmcdermott.com/infocards/"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--teal)' }}
              >
                Mitchell McDermott
              </a>
              {' '}benchmarks{app.est_value_type ? ` (${app.est_value_type})` : ''}.
              Construction cost only — excludes VAT, site acquisition, professional fees,
              development contributions and finance costs.
            </div>
          </div>
        )}

        {/* Timeline */}
        <div className="detail-section fade-in" style={{ animationDelay: '180ms' }}>
          <h3>TIMELINE</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <div className="timeline-item">
              <div className={`timeline-dot ${app.apn_date ? '' : 'inactive'}`} />
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>Submitted</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{formatDate(app.apn_date)}</div>
              </div>
            </div>
            <div className="timeline-item">
              <div className={`timeline-dot ${app.rgn_date ? '' : 'inactive'}`} />
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>Registered</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{formatDate(app.rgn_date)}</div>
              </div>
            </div>
            <div className="timeline-item">
              <div className={`timeline-dot ${app.dec_date ? '' : 'inactive'}`} />
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>Decided</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{formatDate(app.dec_date)}</div>
              </div>
            </div>
            {app.final_grant_date && (
              <div className="timeline-item">
                <div className="timeline-dot" />
                <div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>Final Grant</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{formatDate(app.final_grant_date)}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Appeals */}
        {app.bcms && (
          <div className="detail-section fade-in" style={{ animationDelay: '210ms' }}>
            <h3>BUILDING CONTROL</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {app.bcms.cn_commencement_date && (
                <div style={{ padding: '0.75rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Construction commenced</div>
                  <div style={{ fontWeight: 600 }}>{formatDate(app.bcms.cn_commencement_date)}</div>
                </div>
              )}
              {app.bcms.ccc_date_validated && (
                <div style={{ padding: '0.75rem', background: 'rgba(22, 163, 106, 0.05)', borderRadius: '8px', border: '1px solid rgba(22, 163, 106, 0.15)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Certificate of compliance</div>
                  <div style={{ fontWeight: 600, color: '#16a34a' }}>
                    ✓ Completed {formatDate(app.bcms.ccc_date_validated)}
                    {app.bcms.ccc_units_completed ? ` · ${app.bcms.ccc_units_completed} units` : ''}
                  </div>
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.5rem' }}>
                {app.bcms.cn_total_dwelling_units && app.bcms.cn_total_dwelling_units > 0 && (
                  <div style={{ padding: '0.75rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal)' }}>{app.bcms.cn_total_dwelling_units}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Dwelling Units</div>
                  </div>
                )}
                {app.bcms.cn_total_floor_area && app.bcms.cn_total_floor_area > 0 && (
                  <div style={{ padding: '0.75rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal)' }}>{app.bcms.cn_total_floor_area.toLocaleString()} m²</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Floor Area</div>
                  </div>
                )}
                {app.bcms.cn_total_apartments && app.bcms.cn_total_apartments > 0 && (
                  <div style={{ padding: '0.75rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal)' }}>{app.bcms.cn_total_apartments}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Apartments</div>
                  </div>
                )}
                {app.bcms.cn_number_stories_above && app.bcms.cn_number_stories_above > 0 && (
                  <div style={{ padding: '0.75rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal)' }}>{app.bcms.cn_number_stories_above}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Stories</div>
                  </div>
                )}
              </div>
            </div>
            <div style={{ marginTop: '0.5rem', fontSize: '0.65rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
              Source: Building Control Management System (BCMS)
            </div>
          </div>
        )}

        {/* Appeals */}
        {app.appeals.length > 0 && (
          <div className="detail-section fade-in" style={{ animationDelay: '240ms' }}>
            <h3>APPEALS ({app.appeals.length})</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {app.appeals.map(appeal => (
                <div key={appeal.id} style={{ padding: '0.75rem', background: 'var(--warm-white)', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', fontSize: '0.875rem' }}>
                    <span style={{ fontWeight: 500 }}>{appeal.appeal_ref || 'Appeal'}</span>
                    {appeal.appeal_decision && (
                      <span className={`decision-chip ${appeal.appeal_decision.includes('Grant') ? 'decision-granted' : 'decision-refused'}`}>
                        {appeal.appeal_decision}
                      </span>
                    )}
                  </div>
                  {appeal.appellant && <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>By: {appeal.appellant}</p>}
                  <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    <span>Filed: {formatDate(appeal.appeal_date)}</span>
                    {appeal.appeal_dec_date && <span>Decided: {formatDate(appeal.appeal_dec_date)}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Further Info */}
        {app.further_info.length > 0 && (
          <div className="detail-section fade-in" style={{ animationDelay: '300ms' }}>
            <h3>FURTHER INFORMATION ({app.further_info.length})</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {app.further_info.map(fi => (
                <div key={fi.id} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.5rem 0.75rem', background: 'var(--warm-white)', borderRadius: '8px',
                  fontSize: '0.875rem',
                }}>
                  <div>
                    <span style={{ fontWeight: 500 }}>{fi.fi_type || 'Request'}</span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem' }}>{formatDate(fi.fi_date)}</span>
                  </div>
                  {fi.fi_response_date && (
                    <span style={{ fontSize: '0.75rem', color: '#16a34a', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <CheckCircle style={{ width: '0.75rem', height: '0.75rem' }} />
                      Response: {formatDate(fi.fi_response_date)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Documents */}
        <div className="detail-section fade-in" style={{ animationDelay: '360ms' }}>
          <h3>DOCUMENTS {app.documents.length > 0 && `(${app.documents.length} files)`}</h3>
          {app.documents.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              {app.documents.map(doc => (
                <div key={doc.id} className="doc-item">
                  <div style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
                    <span className="doc-icon">{getDocIcon(doc.doc_name)}</span>
                    <div style={{ minWidth: 0 }}>
                      <p style={{ fontSize: '0.875rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: 0 }}>{doc.doc_name}</p>
                      {doc.doc_type && <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>{doc.doc_type}</p>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginLeft: '0.75rem' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{formatFileSize(doc.file_size_bytes)}</span>
                    {doc.direct_url ? (
                      <a
                        href={doc.direct_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--teal)', fontSize: '0.8rem', fontWeight: 500, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                      >
                        ↓ Open
                      </a>
                    ) : doc.portal_url ? (
                      <a
                        href={doc.portal_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--teal)', fontSize: '0.8rem', fontWeight: 500, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                      >
                        <ExternalLink style={{ width: '0.75rem', height: '0.75rem' }} /> Portal
                      </a>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
              <FileText style={{ width: '2rem', height: '2rem', color: 'var(--border)', margin: '0 auto 0.5rem' }} />
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', margin: '0 0 0.75rem' }}>Document metadata not yet scraped</p>
              <a
                href={getPortalDocumentUrl(app.reg_ref, app.year)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
                style={{ display: 'inline-flex', fontSize: '0.8rem', textDecoration: 'none' }}
              >
                <ExternalLink style={{ width: '1rem', height: '1rem' }} />
                View Documents on Portal →
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--border)', padding: '2rem 0', marginTop: '2rem' }}>
        <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '0 1rem', textAlign: 'center', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          <p style={{ margin: 0 }}>PlanSearch — National Planning Intelligence Platform</p>
          <p style={{ margin: '0.25rem 0 0' }}>Data: NPAD (National Planning Application Database) &amp; BCMS Open Data (CC BY 4.0)</p>
        </div>
      </footer>
    </main>
  );
}
