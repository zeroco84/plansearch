'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  getInsightsByTopic,
  formatDate,
  type InsightsFeedResponse,
  TOPIC_LABELS,
  TONE_LABELS,
  TONE_COLORS,
} from '@/lib/api';

export default function TopicPage() {
  const params = useParams();
  const topic = params?.topic as string;
  const [feed, setFeed] = useState<InsightsFeedResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!topic) return;
    setLoading(true);
    getInsightsByTopic(topic)
      .then(setFeed)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [topic]);

  return (
    <div className="topic-page">
      <header className="topic-header">
        <Link href="/insights" className="back-link">← Insights</Link>
        <h1>
          {TOPIC_LABELS[topic] || topic}
        </h1>
        <p className="subtitle">
          Posts from The Build covering {(TOPIC_LABELS[topic] || topic).toLowerCase()}
        </p>
      </header>

      <section className="posts-section">
        {loading && (
          <div className="loading-state">
            <div className="spinner" />
            Loading...
          </div>
        )}

        {!loading && feed?.posts.map((post) => (
          <Link key={post.id} href={`/insights/${post.slug}`} className="post-card">
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
            <h3>{post.title}</h3>
            {post.summary_one_line && <p className="summary">{post.summary_one_line}</p>}
            {post.related_app_count > 0 && (
              <span className="app-count">
                🏗️ {post.related_app_count} application{post.related_app_count !== 1 ? 's' : ''}
              </span>
            )}
          </Link>
        ))}

        {!loading && feed && feed.posts.length === 0 && (
          <div className="empty-state">
            <p>No posts found for this topic yet.</p>
            <Link href="/insights">← Back to all insights</Link>
          </div>
        )}
      </section>

      <style jsx>{`
        .topic-page {
          min-height: 100vh;
          background: linear-gradient(145deg, #0f0f23 0%, #1a1a3e 50%, #0d1b2a 100%);
          color: #e2e8f0;
          font-family: 'Inter', -apple-system, sans-serif;
        }

        .topic-header {
          text-align: center;
          padding: 2.5rem 2rem 1.5rem;
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
          font-size: 1.75rem;
          font-weight: 700;
          margin: 0;
          background: linear-gradient(135deg, #60a5fa, #a78bfa);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .subtitle {
          color: #64748b;
          font-size: 0.85rem;
          margin: 0.5rem 0 0;
        }

        .posts-section {
          max-width: 700px;
          margin: 1.5rem auto;
          padding: 0 1rem;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .loading-state, .empty-state {
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

        .post-card {
          display: block;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 12px;
          padding: 1.25rem;
          text-decoration: none;
          color: #e2e8f0;
          transition: all 0.2s;
        }

        .post-card:hover {
          background: rgba(255,255,255,0.06);
          border-color: rgba(96, 165, 250, 0.2);
          transform: translateY(-1px);
        }

        .post-meta {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-bottom: 0.5rem;
        }

        .tone-badge {
          font-size: 0.6rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: white;
          padding: 0.1rem 0.4rem;
          border-radius: 3px;
        }

        .date { font-size: 0.75rem; color: #64748b; }

        h3 {
          font-size: 1rem;
          font-weight: 600;
          margin: 0 0 0.25rem;
          line-height: 1.3;
        }

        .summary {
          font-size: 0.85rem;
          color: #94a3b8;
          margin: 0;
          line-height: 1.5;
        }

        .app-count {
          display: inline-block;
          margin-top: 0.5rem;
          font-size: 0.7rem;
          color: #94a3b8;
        }

        .empty-state a { color: #60a5fa; }
      `}</style>
    </div>
  );
}
