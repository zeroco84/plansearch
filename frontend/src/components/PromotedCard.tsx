'use client';

import { useEffect, useState } from 'react';
import { getContextualAd, recordAdClick, type AdDisplay } from '@/lib/api';

/**
 * Promoted card — per spec 24.5 and Build Note #5:
 * - Visually distinct but not jarring
 * - Slightly lighter background
 * - Small "Promoted" label in top-left
 * - Advertiser logo, headline, body, CTA button
 * - No images beyond the logo
 */
export default function PromotedCard({
  devCategory,
  council,
  lifecycleStage,
  pagePath = '/search',
}: {
  devCategory?: string;
  council?: string;
  lifecycleStage?: string;
  pagePath?: string;
}) {
  const [ad, setAd] = useState<AdDisplay | null>(null);

  useEffect(() => {
    getContextualAd({
      dev_category: devCategory,
      council: council,
      lifecycle_stage: lifecycleStage,
      page_path: pagePath,
    }).then(setAd);
  }, [devCategory, council, lifecycleStage, pagePath]);

  if (!ad) return null;

  const handleClick = () => {
    recordAdClick(ad.campaign_id);
  };

  return (
    <div className="promoted-card">
      <span className="promoted-label">Promoted</span>

      <div className="promoted-body">
        <div className="promoted-header">
          {ad.logo_url && (
            <img src={ad.logo_url} alt={ad.advertiser} className="promoted-logo" />
          )}
          <span className="promoted-advertiser">{ad.advertiser}</span>
        </div>

        {ad.headline && <h4 className="promoted-headline">{ad.headline}</h4>}
        {ad.body_text && <p className="promoted-text">{ad.body_text}</p>}

        {ad.cta_url && (
          <a
            href={ad.cta_url}
            target="_blank"
            rel="noopener noreferrer"
            className="promoted-cta"
            onClick={handleClick}
          >
            {ad.cta_text || 'Learn more'}
          </a>
        )}
      </div>

      <style jsx>{`
        .promoted-card {
          position: relative;
          padding: 1.25rem;
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          transition: all 0.2s;
        }

        .promoted-card:hover {
          border-color: rgba(255, 255, 255, 0.12);
        }

        .promoted-label {
          position: absolute;
          top: 0.5rem;
          left: 0.75rem;
          font-size: 0.6rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #94a3b8;
          background: rgba(255, 255, 255, 0.06);
          padding: 0.1rem 0.4rem;
          border-radius: 3px;
        }

        .promoted-body {
          margin-top: 0.75rem;
        }

        .promoted-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-bottom: 0.5rem;
        }

        .promoted-logo {
          width: 28px;
          height: 28px;
          border-radius: 6px;
          object-fit: contain;
          background: white;
          padding: 2px;
        }

        .promoted-advertiser {
          font-size: 0.75rem;
          color: #94a3b8;
          font-weight: 500;
        }

        .promoted-headline {
          font-size: 0.95rem;
          font-weight: 600;
          color: #e2e8f0;
          margin: 0 0 0.35rem;
          line-height: 1.3;
        }

        .promoted-text {
          font-size: 0.8rem;
          color: #94a3b8;
          line-height: 1.5;
          margin: 0 0 0.75rem;
        }

        .promoted-cta {
          display: inline-block;
          font-size: 0.8rem;
          font-weight: 600;
          color: #00c4b4;
          text-decoration: none;
          border: 1px solid rgba(0, 196, 180, 0.3);
          padding: 0.35rem 1rem;
          border-radius: 6px;
          transition: all 0.2s;
        }

        .promoted-cta:hover {
          background: rgba(0, 196, 180, 0.1);
          border-color: rgba(0, 196, 180, 0.5);
        }
      `}</style>
    </div>
  );
}
