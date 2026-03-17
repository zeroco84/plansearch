'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, MapPin, Calendar, Building2, FileText, Scale,
  ExternalLink, Clock, CheckCircle, AlertCircle, XCircle,
  Database, Settings, Map as MapIcon, Download
} from 'lucide-react';
import {
  getApplication, ApplicationDetail,
  CATEGORY_LABELS, formatDate, formatFileSize, getPortalDocumentUrl,
} from '@/lib/api';

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

function getDocIcon(docName: string): string {
  const name = docName.toLowerCase();
  if (name.includes('plan') || name.includes('elevation') || name.includes('drawing')) return '📐';
  if (name.includes('report') || name.includes('decision') || name.includes('grant')) return '📋';
  if (name.includes('notice') || name.includes('newspaper')) return '📰';
  if (name.includes('observation') || name.includes('submission')) return '💬';
  if (name.includes('site')) return '🏠';
  return '📄';
}

export default function ApplicationPage() {
  const params = useParams();
  const regRef = typeof params?.ref === 'string' ? decodeURIComponent(params.ref) : '';

  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      <main className="min-h-screen bg-[var(--warm-white)]">
        <nav className="hero-gradient" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 text-white no-underline">
              <Database className="w-5 h-5 text-[var(--teal)]" />
              <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
            </Link>
          </div>
        </nav>
        <div className="max-w-4xl mx-auto px-4 py-8 space-y-4">
          <div className="skeleton h-8 w-48" />
          <div className="skeleton h-6 w-96" />
          <div className="skeleton h-32 w-full" />
        </div>
      </main>
    );
  }

  if (error || !app) {
    return (
      <main className="min-h-screen bg-[var(--warm-white)]">
        <nav className="hero-gradient" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="max-w-7xl mx-auto px-4 py-3">
            <Link href="/" className="flex items-center gap-2 text-white no-underline">
              <Database className="w-5 h-5 text-[var(--teal)]" />
              <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
            </Link>
          </div>
        </nav>
        <div className="max-w-4xl mx-auto px-4 py-16 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl" style={{ fontFamily: "'Playfair Display', serif" }}>Application Not Found</h2>
          <p className="text-sm text-[var(--text-muted)] mt-2">{error}</p>
          <Link href="/" className="btn-primary mt-6 inline-flex">
            <ArrowLeft className="w-4 h-4" /> Back to Search
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--warm-white)]">
      {/* Nav */}
      <nav className="hero-gradient" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-white no-underline">
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <div className="flex items-center gap-1">
            <Link href="/map" className="nav-link"><MapIcon className="w-4 h-4" /><span className="hidden sm:inline">Map</span></Link>
            <Link href="/admin" className="nav-link"><Settings className="w-4 h-4" /><span className="hidden sm:inline">Admin</span></Link>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Back link */}
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--teal)] mb-6 no-underline">
          <ArrowLeft className="w-4 h-4" /> Back to search
        </Link>

        {/* Header Card */}
        <div className="detail-section fade-in">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <span className="reg-ref-badge text-base">{app.reg_ref}</span>
              <span className={`decision-chip ${getDecisionClass(app.decision)} ml-3 text-sm`}>{getDecisionLabel(app.decision)}</span>
            </div>
            <a
              href={getPortalDocumentUrl(app.reg_ref, app.year)}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary text-sm no-underline"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View on Portal
            </a>
          </div>

          {app.location && (
            <div className="flex items-start gap-2 mt-4">
              <MapPin className="w-4 h-4 text-[var(--teal)] mt-0.5 flex-shrink-0" />
              <h2 className="text-lg font-semibold" style={{ fontFamily: "'Playfair Display', serif" }}>{app.location}</h2>
            </div>
          )}

          <div className="flex flex-wrap gap-4 mt-3 text-sm text-[var(--text-muted)]">
            <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> Applied: {formatDate(app.apn_date)}</span>
            {app.dec_date && <span className="flex items-center gap-1"><Scale className="w-3.5 h-3.5" /> Decided: {formatDate(app.dec_date)}</span>}
            {app.app_type && <span className="flex items-center gap-1">Type: {app.app_type}</span>}
          </div>
        </div>

        {/* Applicant & Company */}
        {(app.applicant_name || app.company) && (
          <div className="detail-section fade-in" style={{ animationDelay: '60ms' }}>
            <h3>APPLICANT</h3>
            {app.applicant_name && (
              <p className="text-base font-semibold">{app.applicant_name}</p>
            )}
            {app.company && (
              <div className="mt-3 p-3 bg-[var(--warm-white)] rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Building2 className="w-4 h-4 text-[var(--teal)]" />
                  <span className="font-semibold">{app.company.company_name}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm text-[var(--text-secondary)]">
                  <span>CRO: {app.company.cro_number}</span>
                  {app.company.company_status && <span>Status: {app.company.company_status}</span>}
                  {app.company.incorporation_date && <span>Registered: {formatDate(app.company.incorporation_date)}</span>}
                  {app.company.company_type && <span>Type: {app.company.company_type}</span>}
                </div>
                {app.company.registered_address && (
                  <p className="text-sm text-[var(--text-muted)] mt-2">📍 {app.company.registered_address}</p>
                )}
                {app.company.directors && app.company.directors.length > 0 && (
                  <p className="text-sm text-[var(--text-muted)] mt-1">
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
            <div className="flex items-center gap-2 mb-3">
              <span className="category-tag text-sm">
                {CATEGORY_LABELS[app.dev_category] || app.dev_category}
              </span>
              {app.dev_subcategory && (
                <span className="text-sm text-[var(--text-muted)]">› {app.dev_subcategory}</span>
              )}
              {app.classification_confidence && (
                <span className="text-xs text-[var(--text-muted)]">
                  ({(app.classification_confidence * 100).toFixed(0)}% confidence)
                </span>
              )}
            </div>
          )}
          <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
            {app.long_proposal || app.proposal || 'No description available'}
          </p>
        </div>

        {/* Timeline */}
        <div className="detail-section fade-in" style={{ animationDelay: '180ms' }}>
          <h3>TIMELINE</h3>
          <div className="space-y-0">
            <div className="timeline-item">
              <div className={`timeline-dot ${app.apn_date ? '' : 'inactive'}`} />
              <div>
                <div className="text-sm font-medium">Submitted</div>
                <div className="text-xs text-[var(--text-muted)]">{formatDate(app.apn_date)}</div>
              </div>
            </div>
            <div className="timeline-item">
              <div className={`timeline-dot ${app.rgn_date ? '' : 'inactive'}`} />
              <div>
                <div className="text-sm font-medium">Registered</div>
                <div className="text-xs text-[var(--text-muted)]">{formatDate(app.rgn_date)}</div>
              </div>
            </div>
            <div className="timeline-item">
              <div className={`timeline-dot ${app.dec_date ? '' : 'inactive'}`} />
              <div>
                <div className="text-sm font-medium">Decided</div>
                <div className="text-xs text-[var(--text-muted)]">{formatDate(app.dec_date)}</div>
              </div>
            </div>
            {app.final_grant_date && (
              <div className="timeline-item">
                <div className="timeline-dot" />
                <div>
                  <div className="text-sm font-medium">Final Grant</div>
                  <div className="text-xs text-[var(--text-muted)]">{formatDate(app.final_grant_date)}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Appeals */}
        {app.appeals.length > 0 && (
          <div className="detail-section fade-in" style={{ animationDelay: '240ms' }}>
            <h3>APPEALS ({app.appeals.length})</h3>
            <div className="space-y-3">
              {app.appeals.map(appeal => (
                <div key={appeal.id} className="p-3 bg-[var(--warm-white)] rounded-lg">
                  <div className="flex justify-between items-start text-sm">
                    <span className="font-medium">{appeal.appeal_ref || 'Appeal'}</span>
                    {appeal.appeal_decision && (
                      <span className={`decision-chip ${appeal.appeal_decision.includes('Grant') ? 'decision-granted' : 'decision-refused'}`}>
                        {appeal.appeal_decision}
                      </span>
                    )}
                  </div>
                  {appeal.appellant && <p className="text-xs text-[var(--text-muted)] mt-1">By: {appeal.appellant}</p>}
                  <div className="flex gap-3 mt-1 text-xs text-[var(--text-muted)]">
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
            <div className="space-y-2">
              {app.further_info.map(fi => (
                <div key={fi.id} className="flex justify-between items-center p-2 bg-[var(--warm-white)] rounded-lg text-sm">
                  <div>
                    <span className="font-medium">{fi.fi_type || 'Request'}</span>
                    <span className="text-[var(--text-muted)] ml-2">{formatDate(fi.fi_date)}</span>
                  </div>
                  {fi.fi_response_date && (
                    <span className="text-xs text-green-600">
                      <CheckCircle className="w-3 h-3 inline mr-1" />
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
            <div className="space-y-1">
              {app.documents.map(doc => (
                <div key={doc.id} className="doc-item">
                  <div className="flex items-center flex-1 min-w-0">
                    <span className="doc-icon">{getDocIcon(doc.doc_name)}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{doc.doc_name}</p>
                      {doc.doc_type && <p className="text-xs text-[var(--text-muted)]">{doc.doc_type}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 ml-3">
                    <span className="text-xs text-[var(--text-muted)]">{formatFileSize(doc.file_size_bytes)}</span>
                    {doc.direct_url ? (
                      <a
                        href={doc.direct_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--teal)] text-sm font-medium hover:underline no-underline flex items-center gap-1"
                      >
                        ↓ Open
                      </a>
                    ) : doc.portal_url ? (
                      <a
                        href={doc.portal_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--teal)] text-sm font-medium hover:underline no-underline flex items-center gap-1"
                      >
                        <ExternalLink className="w-3 h-3" /> Portal
                      </a>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6">
              <FileText className="w-8 h-8 text-[var(--border)] mx-auto mb-2" />
              <p className="text-sm text-[var(--text-muted)]">Document metadata not yet scraped</p>
              <a
                href={getPortalDocumentUrl(app.reg_ref, app.year)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary mt-3 inline-flex text-sm no-underline"
              >
                <ExternalLink className="w-4 h-4" />
                View Documents on Portal →
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-[var(--text-muted)]">
          <p>PlanSearch — Dublin Planning Intelligence Platform</p>
          <p className="mt-1">Data: Dublin City Council Open Data (CC BY 4.0)</p>
        </div>
      </footer>
    </main>
  );
}
