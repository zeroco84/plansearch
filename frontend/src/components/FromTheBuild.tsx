'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getRelatedPosts, formatDate, TONE_LABELS, TONE_COLORS, type BuildRelatedPost } from '@/lib/api';

/**
 * "From The Build" panel — per spec 23.5.
 * Appears on application detail pages when related posts exist.
 * UTM: medium=related_app, campaign=detail (per Build Note #7).
 */
export default function FromTheBuild({ regRef }: { regRef: string }) {
  const [posts, setPosts] = useState<BuildRelatedPost[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!regRef) return;
    getRelatedPosts(regRef)
      .then((res) => setPosts(res.posts || []))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [regRef]);

  // Per spec Build Note #3: Don't show anything while loading or if no links
  if (!loaded || posts.length === 0) return null;

  return (
    <section className="from-build">
      <h3 className="build-heading">From The Build</h3>
      <p className="build-subtitle">
        Rick Larkin&apos;s perspective on this type of development
      </p>

      <div className="build-posts">
        {posts.map((post) => (
          <a
            key={post.slug}
            href={post.substack_url}
            target="_blank"
            rel="noopener noreferrer"
            className="build-card"
          >
            <div className="build-meta">
              {post.tone && (
                <span
                  className="build-tone"
                  style={{ backgroundColor: TONE_COLORS[post.tone] || '#6b7280' }}
                >
                  {TONE_LABELS[post.tone] || post.tone}
                </span>
              )}
              <span className="build-date">{formatDate(post.published_at)}</span>
            </div>
            <h4 className="build-title">{post.title}</h4>
            {post.excerpt && (
              <p className="build-excerpt">
                {post.excerpt.substring(0, 150)}{post.excerpt.length > 150 ? '...' : ''}
              </p>
            )}
            <span className="build-cta">Read on Substack ↗</span>
          </a>
        ))}
      </div>

      <Link href="/insights" className="build-all-link">
        More from The Build →
      </Link>

      <style jsx>{`
        .from-build {
          margin-top: 2rem;
          padding: 1.25rem;
          background: rgba(167, 139, 250, 0.05);
          border: 1px solid rgba(167, 139, 250, 0.12);
          border-radius: 12px;
        }

        .build-heading {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-weight: 600;
          color: #c4b5fd;
          margin: 0 0 0.15rem;
        }

        .build-subtitle {
          font-size: 0.75rem;
          color: #94a3b8;
          margin: 0 0 1rem;
        }

        .build-posts {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .build-card {
          display: block;
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 8px;
          padding: 1rem;
          text-decoration: none;
          color: #e2e8f0;
          transition: all 0.2s;
        }

        .build-card:hover {
          background: rgba(255,255,255,0.05);
          border-color: rgba(167, 139, 250, 0.2);
        }

        .build-meta {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          margin-bottom: 0.35rem;
        }

        .build-tone {
          font-size: 0.55rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: white;
          padding: 0.1rem 0.35rem;
          border-radius: 3px;
        }

        .build-date {
          font-size: 0.7rem;
          color: #64748b;
        }

        .build-title {
          font-size: 0.9rem;
          font-weight: 600;
          margin: 0 0 0.25rem;
          line-height: 1.3;
        }

        .build-excerpt {
          font-size: 0.8rem;
          color: #94a3b8;
          margin: 0;
          line-height: 1.5;
        }

        .build-cta {
          display: inline-block;
          margin-top: 0.5rem;
          font-size: 0.75rem;
          color: #60a5fa;
        }

        .build-all-link {
          display: inline-block;
          margin-top: 0.75rem;
          font-size: 0.8rem;
          color: #c4b5fd;
          text-decoration: none;
        }

        .build-all-link:hover { text-decoration: underline; }
      `}</style>
    </section>
  );
}
