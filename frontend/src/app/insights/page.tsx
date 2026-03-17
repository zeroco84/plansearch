'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Script from 'next/script';
import {
  getInsightsFeed,
  formatDate,
  type InsightsPost,
  type InsightsFeedResponse,
  TOPIC_LABELS,
  TONE_LABELS,
  TONE_COLORS,
} from '@/lib/api';

export default function InsightsPage() {
  const [feed, setFeed] = useState<InsightsFeedResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getInsightsFeed(page)
      .then(setFeed)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page]);

  const featured = feed?.posts?.[0];
  const rest = feed?.posts?.slice(1) || [];

  return (
    <div className="insights-page">
      <header className="insights-header">
        <div className="header-content">
          <Link href="/" className="back-link">← PlanSearch</Link>
          <h1>Insights</h1>
          <p className="byline">
            from <strong>The Build</strong> · by Rick Larkin
          </p>
          <p className="subtitle">
            Analysis and opinion on Ireland&apos;s housing and planning system
            from a developer who has been through it.
          </p>

          {/* Substack subscribe widget — per spec 23.6 */}
          <div id="substack-embed" className="subscribe-embed" />
        </div>
      </header>

      {/* Featured post */}
      {featured && !loading && (
        <section className="featured-section">
          <h2 className="section-label">Featured</h2>
          <Link href={`/insights/${featured.slug}`} className="featured-card">
            {featured.featured_image_url && (
              <div className="featured-image">
                <img
                  src={featured.featured_image_url}
                  alt={featured.title}
                  loading="lazy"
                />
              </div>
            )}
            <div className="featured-body">
              <div className="post-meta">
                {featured.tone && (
                  <span
                    className="tone-badge"
                    style={{ backgroundColor: TONE_COLORS[featured.tone] || '#6b7280' }}
                  >
                    {TONE_LABELS[featured.tone] || featured.tone}
                  </span>
                )}
                <span className="post-date">{formatDate(featured.published_at)}</span>
              </div>
              <h3>{featured.title}</h3>
              {featured.summary_one_line && (
                <p className="one-line">{featured.summary_one_line}</p>
              )}
              <p className="excerpt">{featured.excerpt}</p>
              <div className="post-footer">
                {featured.related_app_count > 0 && (
                  <span className="app-count">
                    🏗️ {featured.related_app_count} related application{featured.related_app_count !== 1 ? 's' : ''}
                  </span>
                )}
                <a
                  href={featured.substack_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="read-link"
                  onClick={(e) => e.stopPropagation()}
                >
                  Read on Substack ↗
                </a>
              </div>
              {featured.topics && featured.topics.length > 0 && (
                <div className="topic-tags">
                  {featured.topics.slice(0, 4).map((t) => (
                    <Link key={t} href={`/insights/topic/${t}`} className="topic-tag">
                      {TOPIC_LABELS[t] || t}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </Link>
        </section>
      )}

      {/* Post grid */}
      <section className="posts-grid">
        {loading && (
          <div className="loading-state">
            <div className="spinner" />
            <span>Loading insights...</span>
          </div>
        )}

        {!loading && rest.map((post) => (
          <PostCard key={post.id} post={post} />
        ))}

        {!loading && feed && feed.posts.length === 0 && (
          <div className="empty-state">
            <p>No posts yet. Check back soon — The Build publishes 1-2 times per month.</p>
          </div>
        )}
      </section>

      {/* Pagination */}
      {feed && feed.total_pages > 1 && (
        <div className="pagination">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
          >
            Previous
          </button>
          <span>Page {page} of {feed.total_pages}</span>
          <button
            disabled={page >= feed.total_pages}
            onClick={() => setPage(p => p + 1)}
          >
            Next
          </button>
        </div>
      )}

      <footer className="insights-footer">
        <p>
          The Build is a newsletter by Rick Larkin about Ireland&apos;s broken housing
          and planning system. Posts here show excerpts only —{' '}
          <a href="https://thebuildpod.substack.com?utm_source=plansearch&utm_medium=insights&utm_campaign=footer" target="_blank" rel="noopener noreferrer">
            read the full articles on Substack
          </a>.
        </p>
      </footer>

      {/* Substack widget script — per spec 23.6 */}
      <Script
        id="substack-widget-config"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
            window.CustomSubstackWidget = {
              substackUrl: "thebuildpod.substack.com",
              placeholder: "Enter your email",
              buttonText: "Subscribe to The Build",
              theme: "custom",
              colors: { primary: "#00c4b4", input: "#1a1f2e", email: "#ffffff", text: "#ffffff" }
            };
          `,
        }}
      />
      <Script
        src="https://substackapi.com/widget.js"
        strategy="afterInteractive"
      />

      <style jsx>{`
        .insights-page {
          min-height: 100vh;
          background: linear-gradient(145deg, #0f0f23 0%, #1a1a3e 50%, #0d1b2a 100%);
          color: #e2e8f0;
          font-family: 'Inter', -apple-system, sans-serif;
        }

        .insights-header {
          text-align: center;
          padding: 2.5rem 2rem 2rem;
          background: rgba(255,255,255,0.03);
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }

        .back-link {
          color: #60a5fa;
          text-decoration: none;
          font-size: 0.85rem;
          display: inline-block;
          margin-bottom: 0.75rem;
        }

        h1 {
          font-size: 2rem;
          font-weight: 700;
          margin: 0;
          background: linear-gradient(135deg, #60a5fa, #a78bfa);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .byline {
          color: #94a3b8;
          font-size: 0.9rem;
          margin: 0.25rem 0;
        }

        .byline strong { color: #e2e8f0; }

        .subtitle {
          color: #64748b;
          font-size: 0.85rem;
          max-width: 500px;
          margin: 0.5rem auto 1.5rem;
          line-height: 1.5;
        }

        .subscribe-embed {
          max-width: 400px;
          margin: 0 auto;
        }

        .section-label {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: #64748b;
          font-weight: 600;
          margin-bottom: 0.75rem;
        }

        .featured-section {
          max-width: 900px;
          margin: 1.5rem auto;
          padding: 0 1rem;
        }

        .featured-card {
          display: flex;
          gap: 1.5rem;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 12px;
          padding: 1.5rem;
          text-decoration: none;
          color: #e2e8f0;
          transition: all 0.2s;
        }

        .featured-card:hover {
          background: rgba(255,255,255,0.06);
          border-color: rgba(96, 165, 250, 0.2);
        }

        .featured-image {
          min-width: 200px;
          max-width: 280px;
          border-radius: 8px;
          overflow: hidden;
          flex-shrink: 0;
        }

        .featured-image img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          border-radius: 8px;
        }

        .featured-body { flex: 1; min-width: 0; }

        .featured-body h3 {
          font-size: 1.25rem;
          margin: 0.5rem 0;
          font-weight: 700;
          line-height: 1.3;
        }

        .one-line {
          color: #94a3b8;
          font-size: 0.9rem;
          font-style: italic;
          margin: 0.25rem 0 0.5rem;
        }

        .excerpt {
          font-size: 0.85rem;
          color: #94a3b8;
          line-height: 1.6;
          margin: 0;
        }

        .post-meta {
          display: flex;
          align-items: center;
          gap: 0.5rem;
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

        .post-date {
          font-size: 0.75rem;
          color: #64748b;
        }

        .post-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-top: 0.75rem;
        }

        .app-count {
          font-size: 0.8rem;
          color: #94a3b8;
        }

        .read-link {
          color: #60a5fa;
          text-decoration: none;
          font-size: 0.85rem;
          font-weight: 500;
        }

        .read-link:hover { text-decoration: underline; }

        .topic-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
          margin-top: 0.75rem;
        }

        .topic-tag {
          font-size: 0.7rem;
          background: rgba(96, 165, 250, 0.1);
          color: #93c5fd;
          padding: 0.15rem 0.5rem;
          border-radius: 4px;
          text-decoration: none;
        }

        .topic-tag:hover {
          background: rgba(96, 165, 250, 0.2);
        }

        .posts-grid {
          max-width: 900px;
          margin: 1.5rem auto;
          padding: 0 1rem;
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 1rem;
        }

        .loading-state, .empty-state {
          grid-column: 1 / -1;
          text-align: center;
          padding: 3rem;
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

        .pagination {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 1rem;
          padding: 2rem;
          color: #94a3b8;
          font-size: 0.85rem;
        }

        .pagination button {
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.1);
          color: #e2e8f0;
          padding: 0.5rem 1rem;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .pagination button:hover:not(:disabled) {
          background: rgba(255,255,255,0.1);
        }

        .pagination button:disabled {
          opacity: 0.4;
          cursor: default;
        }

        .insights-footer {
          text-align: center;
          padding: 2rem;
          border-top: 1px solid rgba(255,255,255,0.06);
          margin-top: 2rem;
        }

        .insights-footer p {
          font-size: 0.75rem;
          color: #475569;
          max-width: 500px;
          margin: 0 auto;
          line-height: 1.6;
        }

        .insights-footer a { color: #60a5fa; }

        @media (max-width: 768px) {
          .featured-card { flex-direction: column; }
          .featured-image { max-width: 100%; min-width: 0; }
          .posts-grid { grid-template-columns: 1fr; }
          h1 { font-size: 1.5rem; }
        }
      `}</style>
    </div>
  );
}

function PostCard({ post }: { post: InsightsPost }) {
  return (
    <Link href={`/insights/${post.slug}`} className="post-card-link">
      <article className="post-card">
        {post.featured_image_url && (
          <div className="card-image">
            <img src={post.featured_image_url} alt={post.title} loading="lazy" />
          </div>
        )}
        <div className="card-body">
          <div className="card-meta">
            {post.tone && (
              <span
                className="card-tone"
                style={{ backgroundColor: TONE_COLORS[post.tone] || '#6b7280' }}
              >
                {TONE_LABELS[post.tone] || post.tone}
              </span>
            )}
            <span className="card-date">{formatDate(post.published_at)}</span>
          </div>
          <h4 className="card-title">{post.title}</h4>
          {post.summary_one_line && (
            <p className="card-summary">{post.summary_one_line}</p>
          )}
          {post.related_app_count > 0 && (
            <span className="card-app-count">
              🏗️ {post.related_app_count} application{post.related_app_count !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        <style jsx>{`
          .post-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.2s;
            height: 100%;
          }

          .post-card:hover {
            background: rgba(255,255,255,0.06);
            border-color: rgba(96, 165, 250, 0.2);
            transform: translateY(-2px);
          }

          .card-image {
            height: 140px;
            overflow: hidden;
          }

          .card-image img {
            width: 100%;
            height: 100%;
            object-fit: cover;
          }

          .card-body {
            padding: 1rem;
          }

          .card-meta {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
          }

          .card-tone {
            font-size: 0.6rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: white;
            padding: 0.1rem 0.4rem;
            border-radius: 3px;
          }

          .card-date {
            font-size: 0.7rem;
            color: #64748b;
          }

          .card-title {
            font-size: 0.95rem;
            font-weight: 600;
            margin: 0 0 0.35rem;
            color: #e2e8f0;
            line-height: 1.3;
          }

          .card-summary {
            font-size: 0.8rem;
            color: #94a3b8;
            line-height: 1.5;
            margin: 0;
          }

          .card-app-count {
            display: inline-block;
            margin-top: 0.5rem;
            font-size: 0.7rem;
            color: #94a3b8;
          }
        `}</style>
      </article>
    </Link>
  );
}
