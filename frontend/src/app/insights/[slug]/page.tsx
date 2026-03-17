'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  getInsightsPost,
  formatDate,
  formatValue,
  TOPIC_LABELS,
  TONE_LABELS,
  TONE_COLORS,
  LIFECYCLE_STAGES,
  LIFECYCLE_COLORS,
  getDecisionColor,
  type InsightsPostDetail,
} from '@/lib/api';

export default function PostDetailPage() {
  const params = useParams();
  const slug = params?.slug as string;
  const [post, setPost] = useState<InsightsPostDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    getInsightsPost(slug)
      .then(setPost)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <div className="post-page">
        <div className="loading-state">
          <div className="spinner" />
          Loading...
        </div>
        <style jsx>{pageStyles}</style>
      </div>
    );
  }

  if (error || !post) {
    return (
      <div className="post-page">
        <div className="error-state">
          <Link href="/insights" className="back-link">← Back to Insights</Link>
          <h2>Post not found</h2>
          <p>{error || 'This article could not be loaded.'}</p>
        </div>
        <style jsx>{pageStyles}</style>
      </div>
    );
  }

  return (
    <div className="post-page">
      <header className="post-header">
        <Link href="/insights" className="back-link">← Insights</Link>

        <div className="post-meta">
          {post.tone && (
            <span
              className="tone-badge"
              style={{ backgroundColor: TONE_COLORS[post.tone] || '#6b7280' }}
            >
              {TONE_LABELS[post.tone] || post.tone}
            </span>
          )}
          <span className="date">{formatDate(post.published_at)}</span>
        </div>

        <h1>{post.title}</h1>
        {post.subtitle && <p className="subtitle">{post.subtitle}</p>}
      </header>

      {post.featured_image_url && (
        <div className="featured-image">
          <img src={post.featured_image_url} alt={post.title} />
        </div>
      )}

      <section className="post-content">
        <p className="excerpt">{post.excerpt}</p>

        {/* CTA — per spec 23.4: Excerpt + prominent CTA, never full post */}
        <a
          href={post.substack_url}
          target="_blank"
          rel="noopener noreferrer"
          className="cta-button"
        >
          Read the full post — free — on The Build ↗
        </a>
      </section>

      {/* Topics */}
      {post.topics && post.topics.length > 0 && (
        <section className="topics-section">
          <h3>Topics</h3>
          <div className="topic-tags">
            {post.topics.map((t) => (
              <Link key={t} href={`/insights/topic/${t}`} className="topic-tag">
                {TOPIC_LABELS[t] || t}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Related applications — per spec 23.4 */}
      {post.related_applications && post.related_applications.length > 0 && (
        <section className="related-apps">
          <h3>Related Planning Applications</h3>
          <p className="related-count">
            {post.related_applications.length} application{post.related_applications.length !== 1 ? 's' : ''} linked
          </p>

          <div className="app-list">
            {post.related_applications.map((app) => (
              <Link
                key={`${app.reg_ref}`}
                href={`/application/${encodeURIComponent(app.reg_ref)}`}
                className="app-card"
              >
                <div className="app-header">
                  <span className="app-ref">{app.reg_ref}</span>
                  {app.decision && (
                    <span
                      className="app-decision"
                      style={{ backgroundColor: getDecisionColor(app.decision) }}
                    >
                      {app.decision}
                    </span>
                  )}
                  {app.lifecycle_stage && (
                    <span
                      className="app-lifecycle"
                      style={{
                        backgroundColor: LIFECYCLE_COLORS[app.lifecycle_stage] || '#6b7280',
                      }}
                    >
                      {LIFECYCLE_STAGES[app.lifecycle_stage] || app.lifecycle_stage}
                    </span>
                  )}
                </div>
                {app.location && <p className="app-location">📍 {app.location}</p>}
                {app.proposal && (
                  <p className="app-proposal">
                    {app.proposal.substring(0, 150)}{app.proposal.length > 150 ? '...' : ''}
                  </p>
                )}
                <div className="app-footer">
                  {app.planning_authority && (
                    <span className="app-authority">{app.planning_authority}</span>
                  )}
                  {app.est_value_high && (
                    <span className="app-value">{formatValue(app.est_value_high)}</span>
                  )}
                  <span className="view-link">View details →</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <footer className="post-footer">
        <Link href="/insights" className="home-link">← More from The Build</Link>
        <a
          href="https://thebuildpod.substack.com?utm_source=plansearch&utm_medium=insights&utm_campaign=footer"
          target="_blank"
          rel="noopener noreferrer"
          className="subscribe-link"
        >
          Subscribe to The Build →
        </a>
      </footer>

      <style jsx>{pageStyles}</style>
    </div>
  );
}

const pageStyles = `
  .post-page {
    min-height: 100vh;
    background: linear-gradient(145deg, #0f0f23 0%, #1a1a3e 50%, #0d1b2a 100%);
    color: #e2e8f0;
    font-family: 'Inter', -apple-system, sans-serif;
    padding-bottom: 3rem;
  }

  .loading-state, .error-state {
    text-align: center;
    padding: 4rem 2rem;
    color: #94a3b8;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid rgba(96, 165, 250, 0.2);
    border-top-color: #60a5fa;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1rem;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .back-link {
    color: #60a5fa;
    text-decoration: none;
    font-size: 0.85rem;
  }

  .back-link:hover { text-decoration: underline; }

  .post-header {
    max-width: 700px;
    margin: 0 auto;
    padding: 2rem 1.5rem 1rem;
  }

  .post-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 1rem 0 0.5rem;
  }

  .tone-badge {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: white;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
  }

  .date {
    font-size: 0.8rem;
    color: #64748b;
  }

  h1 {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0.5rem 0;
    line-height: 1.3;
  }

  .subtitle {
    color: #94a3b8;
    font-size: 1rem;
    margin: 0;
    font-style: italic;
  }

  .featured-image {
    max-width: 700px;
    margin: 1rem auto;
    padding: 0 1.5rem;
  }

  .featured-image img {
    width: 100%;
    border-radius: 12px;
    object-fit: cover;
  }

  .post-content {
    max-width: 700px;
    margin: 0 auto;
    padding: 1rem 1.5rem 2rem;
  }

  .excerpt {
    font-size: 0.95rem;
    line-height: 1.8;
    color: #cbd5e1;
  }

  .cta-button {
    display: block;
    text-align: center;
    background: linear-gradient(135deg, #00c4b4, #0ea5e9);
    color: white;
    font-weight: 600;
    font-size: 1rem;
    padding: 1rem 2rem;
    border-radius: 12px;
    text-decoration: none;
    margin-top: 2rem;
    transition: all 0.2s;
  }

  .cta-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 196, 180, 0.3);
  }

  .topics-section, .related-apps {
    max-width: 700px;
    margin: 0 auto;
    padding: 1rem 1.5rem;
  }

  .topics-section h3, .related-apps h3 {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #64748b;
    font-weight: 600;
    margin: 0 0 0.75rem;
  }

  .topic-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .topic-tag {
    font-size: 0.75rem;
    background: rgba(96, 165, 250, 0.1);
    color: #93c5fd;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    text-decoration: none;
    transition: background 0.2s;
  }

  .topic-tag:hover { background: rgba(96, 165, 250, 0.2); }

  .related-count {
    color: #94a3b8;
    font-size: 0.85rem;
    margin: 0 0 1rem;
  }

  .app-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .app-card {
    display: block;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 1rem;
    text-decoration: none;
    color: #e2e8f0;
    transition: all 0.2s;
  }

  .app-card:hover {
    background: rgba(255,255,255,0.06);
    border-color: rgba(96, 165, 250, 0.2);
  }

  .app-header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
    margin-bottom: 0.4rem;
  }

  .app-ref {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #60a5fa;
    font-weight: 600;
  }

  .app-decision, .app-lifecycle {
    font-size: 0.6rem;
    font-weight: 600;
    text-transform: uppercase;
    color: white;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
  }

  .app-location {
    font-size: 0.8rem;
    color: #e2e8f0;
    margin: 0 0 0.25rem;
  }

  .app-proposal {
    font-size: 0.8rem;
    color: #94a3b8;
    margin: 0;
    line-height: 1.5;
  }

  .app-footer {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.5rem;
  }

  .app-authority {
    font-size: 0.7rem;
    background: rgba(96, 165, 250, 0.1);
    color: #93c5fd;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
  }

  .app-value {
    font-size: 0.75rem;
    color: #10b981;
    font-weight: 600;
  }

  .view-link {
    font-size: 0.75rem;
    color: #60a5fa;
    margin-left: auto;
  }

  .post-footer {
    max-width: 700px;
    margin: 2rem auto 0;
    padding: 1.5rem;
    border-top: 1px solid rgba(255,255,255,0.06);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .home-link, .subscribe-link {
    color: #60a5fa;
    text-decoration: none;
    font-size: 0.85rem;
  }

  .home-link:hover, .subscribe-link:hover {
    text-decoration: underline;
  }

  @media (max-width: 768px) {
    h1 { font-size: 1.4rem; }
    .post-footer { flex-direction: column; gap: 0.75rem; }
  }
`;
