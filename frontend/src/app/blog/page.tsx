'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  getInsightsFeed,
  formatDate,
  type InsightsPost,
  type InsightsFeedResponse,
} from '@/lib/api';
import {
  Database, Settings, Map as MapIcon, TrendingUp, BookOpen, Search, Bell, UserCircle,
} from 'lucide-react';

const FALLBACK_POSTS = [
  { slug: 'stepping-aside', title: 'Stepping Aside', subtitle: 'How to spend 6 years and millions of Euro building absolutely nothing.', published_at: '2025-12-09', substack_url: 'https://thebuildpod.substack.com/p/stepping-aside', featured_image_url: null },
  { slug: 'judicially-review-this', title: 'Judicially Review THIS', subtitle: 'On reform of a truly mad system', published_at: '2025-10-24', substack_url: 'https://thebuildpod.substack.com/p/judicially-review-this', featured_image_url: null },
  { slug: 'the-past-can-hurt', title: 'The Past Can Hurt', subtitle: 'But you can either run from it, or learn from it', published_at: '2025-11-17', substack_url: 'https://thebuildpod.substack.com/p/the-past-can-hurt', featured_image_url: null },
  { slug: 'students-are-literally-the-future', title: 'Students are LITERALLY the future', subtitle: "I'm using literally correctly, unlike most people", published_at: '2025-09-13', substack_url: 'https://thebuildpod.substack.com/p/students-are-literally-the-future', featured_image_url: null },
  { slug: 'froschmausekrieg', title: 'Froschmäusekrieg', subtitle: 'The Government, once again, has flubbed it.', published_at: '2025-07-10', substack_url: 'https://thebuildpod.substack.com/p/froschmausekrieg', featured_image_url: null },
  { slug: 'manifesting', title: 'Manifesting', subtitle: 'If we believe really hard, maybe our housing wishes will come true.', published_at: '2025-06-15', substack_url: 'https://thebuildpod.substack.com/p/manifesting', featured_image_url: null },
];

export default function InsightsPage() {
  const [feed, setFeed] = useState<InsightsFeedResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setApiError(false);
    getInsightsFeed(page)
      .then(data => {
        if (data && data.posts && data.posts.length > 0) {
          setFeed(data);
        } else {
          setApiError(true);
        }
      })
      .catch(() => setApiError(true))
      .finally(() => setLoading(false));
  }, [page]);

  const posts = feed?.posts || [];
  const showFallback = !loading && (apiError || posts.length === 0);
  const displayPosts: Array<{
    slug: string;
    title: string;
    subtitle?: string;
    excerpt?: string;
    summary_one_line?: string;
    published_at: string;
    substack_url: string;
    featured_image_url: string | null;
  }> = showFallback
    ? FALLBACK_POSTS
    : posts.map(p => ({
        slug: p.slug,
        title: p.title,
        subtitle: p.summary_one_line || undefined,
        excerpt: p.excerpt || undefined,
        summary_one_line: p.summary_one_line || undefined,
        published_at: p.published_at || '',
        substack_url: p.substack_url,
        featured_image_url: p.featured_image_url || null,
      }));

  return (
    <div style={{ background: '#ffffff', minHeight: '100vh', fontFamily: "'Inter', -apple-system, sans-serif" }}>
      {/* NAV */}
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
            <Link href="/blog" className="nav-link" style={{ color: 'var(--teal)' }}><BookOpen className="w-5 h-5" /><span className="hidden sm:inline">Blog</span></Link>
            <Link href="/alerts" className="nav-link"><Bell className="w-5 h-5" /><span className="hidden sm:inline">Alerts</span></Link>
            <Link href="/login" className="nav-link"><UserCircle className="w-5 h-5" /><span className="hidden sm:inline">Login</span></Link>
          </div>
        </div>
      </nav>

      {/* Header */}
      <div style={{
        borderBottom: '1px solid #e5e5e5',
        padding: '3rem 1.5rem 2rem',
        textAlign: 'center',
        maxWidth: '680px',
        margin: '0 auto',
      }}>
        <div style={{
          width: '56px', height: '56px',
          borderRadius: '8px',
          margin: '0 auto 1rem',
          overflow: 'hidden',
          background: '#1a1a1a',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.5rem',
        }}>
          🏗️
        </div>

        <h1 style={{
          fontSize: '1.6rem', fontWeight: '700',
          color: '#1a1a1a', margin: '0 0 0.2rem',
          letterSpacing: '-0.02em',
          fontFamily: "'Playfair Display', serif",
        }}>
          The Build
        </h1>
        <p style={{ fontSize: '0.85rem', color: '#888', margin: '0 0 0.75rem' }}>
          by Rick Larkin
        </p>
        <p style={{
          fontSize: '0.9rem', color: '#555',
          maxWidth: '400px', margin: '0 auto 1.5rem',
          lineHeight: 1.6,
        }}>
          Analysis and opinion on Ireland&apos;s housing and planning system
          from a developer who has been through it.
        </p>

        <a
          href="https://thebuildpod.substack.com"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'inline-block',
            background: '#FF6719',
            color: '#fff',
            padding: '0.55rem 1.4rem',
            borderRadius: '9999px',
            fontSize: '0.85rem',
            fontWeight: '600',
            textDecoration: 'none',
            transition: 'opacity 0.15s',
          }}
          onMouseOver={e => (e.currentTarget.style.opacity = '0.9')}
          onMouseOut={e => (e.currentTarget.style.opacity = '1')}
        >
          Subscribe on Substack ↗
        </a>
      </div>

      {/* Posts list */}
      <div style={{ maxWidth: '680px', margin: '0 auto', padding: '0 1.5rem 4rem' }}>

        {showFallback && (
          <p style={{
            fontSize: '0.7rem', color: '#bbb',
            textAlign: 'center', padding: '1.25rem 0 0.25rem',
            letterSpacing: '0.08em', textTransform: 'uppercase',
            fontStyle: 'italic',
          }}>
            Posts shown directly from The Build on Substack
          </p>
        )}

        {!showFallback && (
          <p style={{
            fontSize: '0.7rem', color: '#bbb',
            textAlign: 'center', padding: '1.25rem 0 0.25rem',
            letterSpacing: '0.08em', textTransform: 'uppercase',
          }}>
            From The Build on Substack
          </p>
        )}

        {loading && (
          <div style={{ textAlign: 'center', padding: '3rem 0' }}>
            <div style={{
              width: '32px', height: '32px',
              border: '3px solid #e5e5e5',
              borderTopColor: '#1a1a1a',
              borderRadius: '50%',
              animation: 'insightsSpin 0.8s linear infinite',
              margin: '0 auto 1rem',
            }} />
            <p style={{ color: '#aaa', fontSize: '0.875rem' }}>Loading posts...</p>
          </div>
        )}

        {!loading && displayPosts.map((post) => (
          <a
            key={post.slug}
            href={post.substack_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ display: 'block', textDecoration: 'none', color: 'inherit' }}
          >
            <div
              style={{
                padding: '1.5rem 0',
                borderBottom: '1px solid #f0f0f0',
                display: 'flex',
                gap: '1.25rem',
                alignItems: 'flex-start',
                transition: 'background 0.15s',
              }}
              onMouseOver={e => (e.currentTarget.style.background = '#fafafa')}
              onMouseOut={e => (e.currentTarget.style.background = 'transparent')}
            >
              {/* Text content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  fontSize: '0.7rem', color: '#bbb',
                  margin: '0 0 0.4rem',
                  letterSpacing: '0.06em', textTransform: 'uppercase',
                }}>
                  {new Date(post.published_at).toLocaleDateString('en-IE', {
                    day: 'numeric', month: 'short', year: 'numeric',
                  })}
                </p>
                <h2 style={{
                  fontSize: '1.05rem', fontWeight: '700',
                  color: '#1a1a1a', margin: '0 0 0.35rem',
                  letterSpacing: '-0.01em', lineHeight: 1.3,
                }}>
                  {post.title}
                </h2>
                {(post.excerpt || post.subtitle) && (
                  <p style={{
                    fontSize: '0.875rem', color: '#666',
                    margin: '0 0 0.6rem', lineHeight: 1.5,
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical' as const,
                    overflow: 'hidden',
                  }}>
                    {post.excerpt || post.subtitle}
                  </p>
                )}
                <span style={{
                  fontSize: '0.78rem', color: '#0a8a63', fontWeight: '500',
                }}>
                  Read on Substack ↗
                </span>
              </div>

              {/* Post image */}
              {post.featured_image_url && (
                <div style={{
                  width: '100px', height: '72px',
                  flexShrink: 0,
                  borderRadius: '6px',
                  overflow: 'hidden',
                  background: '#f5f5f5',
                }}>
                  <img
                    src={post.featured_image_url}
                    alt={post.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={e => { (e.currentTarget.parentElement as HTMLElement).style.display = 'none'; }}
                  />
                </div>
              )}
            </div>
          </a>
        ))}

        {!loading && displayPosts.length === 0 && (
          <p style={{ textAlign: 'center', color: '#aaa', padding: '3rem 0' }}>
            No posts yet. Check back soon — The Build publishes 1-2 times per month.
          </p>
        )}
      </div>

      {/* Pagination */}
      {feed && feed.total_pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem', padding: '0 0 2rem', fontSize: '0.85rem' }}>
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            style={{
              padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid #e5e5e5',
              background: page <= 1 ? '#f5f5f5' : 'white', color: '#1a1a1a', cursor: page <= 1 ? 'default' : 'pointer',
              opacity: page <= 1 ? 0.4 : 1,
            }}
          >
            Previous
          </button>
          <span style={{ color: '#888' }}>Page {page} of {feed.total_pages}</span>
          <button
            disabled={page >= feed.total_pages}
            onClick={() => setPage(p => p + 1)}
            style={{
              padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid #e5e5e5',
              background: page >= feed.total_pages ? '#f5f5f5' : 'white', color: '#1a1a1a',
              cursor: page >= feed.total_pages ? 'default' : 'pointer',
              opacity: page >= feed.total_pages ? 0.4 : 1,
            }}
          >
            Next
          </button>
        </div>
      )}

      {/* Footer */}
      <footer style={{ textAlign: 'center', padding: '2rem', borderTop: '1px solid #f0f0f0' }}>
        <p style={{ fontSize: '0.75rem', color: '#aaa', maxWidth: '500px', margin: '0 auto', lineHeight: 1.6 }}>
          The Build is a newsletter by Rick Larkin about Ireland&apos;s broken housing
          and planning system. Posts here show excerpts only —{' '}
          <a href="https://thebuildpod.substack.com" target="_blank" rel="noopener noreferrer" style={{ color: '#0a8a63' }}>
            read the full articles on Substack
          </a>.
        </p>
      </footer>

      <style jsx>{`
        @keyframes insightsSpin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
