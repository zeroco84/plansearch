"""PlanSearch — Substack RSS Ingest Worker.

Fetches posts from The Build (thebuildpod.substack.com) via public RSS feed.
Upserts into build_posts table. No Substack API key needed.

Uses feedparser which handles CDATA wrapping automatically (per spec Build Note #2).
"""

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import BuildPost

logger = logging.getLogger(__name__)

SUBSTACK_FEED = "https://thebuildpod.substack.com/feed"


def extract_slug(url: str) -> str:
    """Extract slug from Substack URL like /p/stepping-aside."""
    if "/p/" in url:
        return url.split("/p/")[-1].rstrip("/").split("?")[0]
    return url.rstrip("/").split("/")[-1]


def parse_rfc822_date(date_str: str) -> Optional[datetime]:
    """Parse RSS published date (RFC 822 format)."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None


def extract_plain_text_excerpt(entry, max_chars: int = 400) -> str:
    """Strip HTML from RSS content to get plain text excerpt.

    Per spec Build Note #1: Never reproduce full post content.
    Use excerpt (max 400 chars plain text) and link through to Substack.
    """
    content = ""
    # feedparser handles CDATA automatically
    content_entries = getattr(entry, "content", [{}]) or [{}]
    if isinstance(content_entries, list) and len(content_entries) > 0:
        content = content_entries[0].get("value", "")
    if not content:
        content = getattr(entry, "summary", "")
    if not content:
        return ""

    text = BeautifulSoup(content, "html.parser").get_text(" ", strip=True)
    return (text[:max_chars] + "...") if len(text) > max_chars else text


def extract_featured_image(entry) -> str:
    """Get featured image from RSS enclosure or first img tag in content."""
    # Check enclosures first
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image"):
            return enc.get("href", "")

    # Fall back to first image in content HTML
    content_entries = getattr(entry, "content", [{}]) or [{}]
    if isinstance(content_entries, list) and len(content_entries) > 0:
        content = content_entries[0].get("value", "")
        if content:
            img = BeautifulSoup(content, "html.parser").find("img")
            if img:
                return img.get("src", "")

    return ""


async def ingest_substack_posts(db: AsyncSession) -> dict:
    """Fetch latest posts from The Build RSS and upsert to build_posts table."""
    logger.info("Substack: Fetching The Build RSS feed...")

    feed = feedparser.parse(SUBSTACK_FEED)

    if feed.bozo:
        logger.warning(f"Substack: Feed parse warning: {feed.bozo_exception}")

    stats = {"new": 0, "updated": 0, "total": len(feed.entries)}

    for entry in feed.entries:
        url = getattr(entry, "link", "")
        if not url:
            continue

        slug = extract_slug(url)
        if not slug:
            continue

        post_data = {
            "slug": slug,
            "title": getattr(entry, "title", "Untitled"),
            "subtitle": getattr(entry, "summary", "")[:200] if hasattr(entry, "summary") else "",
            "published_at": parse_rfc822_date(getattr(entry, "published", "")),
            "substack_url": url,
            "excerpt": extract_plain_text_excerpt(entry, max_chars=400),
            "featured_image_url": extract_featured_image(entry),
        }

        stmt = pg_insert(BuildPost).values(**post_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={
                "title": post_data["title"],
                "subtitle": post_data["subtitle"],
                "excerpt": post_data["excerpt"],
                "featured_image_url": post_data["featured_image_url"],
                "updated_at": datetime.utcnow(),
            },
        )

        result = await db.execute(stmt)
        if result.rowcount > 0:
            stats["new"] += 1
        else:
            stats["updated"] += 1

    await db.commit()
    logger.info(f"Substack: Ingested {stats['new']} new, {stats['updated']} updated from {stats['total']} entries")
    return stats
