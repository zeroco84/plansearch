"""PlanSearch — Insights API routes (/insights section).

Public endpoints for The Build integration:
- GET /api/insights          → Paginated feed of Build posts
- GET /api/insights/{slug}   → Individual post with related applications
- GET /api/insights/topic/{topic} → Posts filtered by topic
- GET /api/insights/council/{council} → Posts relevant to a council
- GET /api/insights/related/{reg_ref} → Build posts related to an application

Per spec Build Note #6: Cache rendered pages with 24h TTL.
Per spec Build Note #10: Primary KPI is Substack subscribers from PlanSearch.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import BuildPost, PostApplicationLink, Application

router = APIRouter(prefix="/api/insights", tags=["insights"])


# ── Schemas ──────────────────────────────────────────────────────────

class PostSummary(BaseModel):
    id: int
    slug: str
    title: str
    subtitle: Optional[str] = None
    excerpt: Optional[str] = None
    featured_image_url: Optional[str] = None
    substack_url: str
    published_at: Optional[str] = None
    summary_one_line: Optional[str] = None
    topics: Optional[list[str]] = None
    mentioned_councils: Optional[list[str]] = None
    tone: Optional[str] = None
    related_app_count: int = 0

    class Config:
        from_attributes = True


class LinkedApplication(BaseModel):
    id: int
    reg_ref: str
    proposal: Optional[str] = None
    location: Optional[str] = None
    decision: Optional[str] = None
    planning_authority: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    est_value_high: Optional[float] = None
    link_type: str
    confidence: float


class PostDetail(PostSummary):
    related_applications: list[LinkedApplication] = []


class InsightsFeedResponse(BaseModel):
    posts: list[PostSummary]
    total: int
    page: int
    total_pages: int


# ── UTM helpers ──────────────────────────────────────────────────────

def add_utm(url: str, medium: str = "insights", campaign: str = "post") -> str:
    """Add UTM tracking parameters to Substack URLs.

    Per spec Build Note #7: Apply UTM parameters to every outbound link.
    """
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}utm_source=plansearch&utm_medium={medium}&utm_campaign={campaign}"


# ── Feed endpoint ────────────────────────────────────────────────────

@router.get("", response_model=InsightsFeedResponse)
async def get_insights_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Paginated feed of Build posts, newest first."""
    # Count
    count_result = await db.execute(select(func.count(BuildPost.id)))
    total = count_result.scalar() or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    # Fetch posts
    result = await db.execute(
        select(BuildPost)
        .order_by(desc(BuildPost.published_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = result.scalars().all()

    # Get related app counts
    summaries = []
    for post in posts:
        link_count = await db.execute(
            select(func.count(PostApplicationLink.application_id))
            .where(PostApplicationLink.post_id == post.id)
        )
        count = link_count.scalar() or 0

        summaries.append(PostSummary(
            id=post.id,
            slug=post.slug,
            title=post.title,
            subtitle=post.subtitle,
            excerpt=post.excerpt,
            featured_image_url=post.featured_image_url,
            substack_url=add_utm(post.substack_url),
            published_at=post.published_at.isoformat() if post.published_at else None,
            summary_one_line=post.summary_one_line,
            topics=post.topics or [],
            mentioned_councils=post.mentioned_councils or [],
            tone=post.tone,
            related_app_count=count,
        ))

    return InsightsFeedResponse(
        posts=summaries, total=total, page=page, total_pages=total_pages
    )


# ── Individual post with related applications ────────────────────────

@router.get("/{slug}", response_model=PostDetail)
async def get_post_detail(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a single Build post with its linked planning applications."""
    result = await db.execute(
        select(BuildPost).where(BuildPost.slug == slug)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Fetch related applications
    links_result = await db.execute(
        select(PostApplicationLink, Application)
        .join(Application, PostApplicationLink.application_id == Application.id)
        .where(PostApplicationLink.post_id == post.id)
        .order_by(desc(PostApplicationLink.confidence))
        .limit(20)
    )
    linked_apps = []
    for link, app in links_result.fetchall():
        linked_apps.append(LinkedApplication(
            id=app.id,
            reg_ref=app.reg_ref,
            proposal=app.proposal,
            location=app.location,
            decision=app.decision,
            planning_authority=app.planning_authority,
            lifecycle_stage=app.lifecycle_stage,
            est_value_high=float(app.est_value_high) if app.est_value_high else None,
            link_type=link.link_type or "",
            confidence=link.confidence or 0.0,
        ))

    # Get link count
    link_count = len(linked_apps)

    return PostDetail(
        id=post.id,
        slug=post.slug,
        title=post.title,
        subtitle=post.subtitle,
        excerpt=post.excerpt,
        featured_image_url=post.featured_image_url,
        substack_url=add_utm(post.substack_url),
        published_at=post.published_at.isoformat() if post.published_at else None,
        summary_one_line=post.summary_one_line,
        topics=post.topics or [],
        mentioned_councils=post.mentioned_councils or [],
        tone=post.tone,
        related_app_count=link_count,
        related_applications=linked_apps,
    )


# ── Topic filter ──────────────────────────────────────────────────────

@router.get("/topic/{topic}", response_model=InsightsFeedResponse)
async def get_posts_by_topic(
    topic: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Posts filtered by topic (GIN array search)."""
    filter_clause = BuildPost.topics.any(topic)

    count_result = await db.execute(
        select(func.count(BuildPost.id)).where(filter_clause)
    )
    total = count_result.scalar() or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    result = await db.execute(
        select(BuildPost)
        .where(filter_clause)
        .order_by(desc(BuildPost.published_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = result.scalars().all()

    summaries = []
    for post in posts:
        summaries.append(PostSummary(
            id=post.id,
            slug=post.slug,
            title=post.title,
            subtitle=post.subtitle,
            excerpt=post.excerpt,
            featured_image_url=post.featured_image_url,
            substack_url=add_utm(post.substack_url),
            published_at=post.published_at.isoformat() if post.published_at else None,
            summary_one_line=post.summary_one_line,
            topics=post.topics or [],
            mentioned_councils=post.mentioned_councils or [],
            tone=post.tone,
            related_app_count=0,
        ))

    return InsightsFeedResponse(
        posts=summaries, total=total, page=page, total_pages=total_pages
    )


# ── Council filter ────────────────────────────────────────────────────

@router.get("/council/{council}", response_model=InsightsFeedResponse)
async def get_posts_by_council(
    council: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Posts relevant to a specific council."""
    filter_clause = BuildPost.mentioned_councils.any(council)

    count_result = await db.execute(
        select(func.count(BuildPost.id)).where(filter_clause)
    )
    total = count_result.scalar() or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    result = await db.execute(
        select(BuildPost)
        .where(filter_clause)
        .order_by(desc(BuildPost.published_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = result.scalars().all()

    summaries = [
        PostSummary(
            id=p.id, slug=p.slug, title=p.title, subtitle=p.subtitle,
            excerpt=p.excerpt, featured_image_url=p.featured_image_url,
            substack_url=add_utm(p.substack_url),
            published_at=p.published_at.isoformat() if p.published_at else None,
            summary_one_line=p.summary_one_line, topics=p.topics or [],
            mentioned_councils=p.mentioned_councils or [], tone=p.tone,
            related_app_count=0,
        )
        for p in posts
    ]

    return InsightsFeedResponse(
        posts=summaries, total=total, page=page, total_pages=total_pages
    )


# ── Reverse integration: posts related to an application ─────────────

@router.get("/related/{reg_ref}")
async def get_related_posts(reg_ref: str, db: AsyncSession = Depends(get_db)):
    """Build posts related to a given planning application.

    Per spec 23.5: 'From The Build' panel on application detail pages.
    UTM: medium=related_app, campaign=detail (per Build Note #7).
    """
    # Find application
    app_result = await db.execute(
        select(Application.id).where(Application.reg_ref == reg_ref).limit(1)
    )
    app_id = app_result.scalar_one_or_none()
    if not app_id:
        return {"posts": []}

    # Fetch linked posts
    links_result = await db.execute(
        select(BuildPost, PostApplicationLink.link_type, PostApplicationLink.confidence)
        .join(PostApplicationLink, PostApplicationLink.post_id == BuildPost.id)
        .where(PostApplicationLink.application_id == app_id)
        .order_by(desc(PostApplicationLink.confidence))
        .limit(5)
    )

    posts = []
    for post, link_type, confidence in links_result.fetchall():
        posts.append({
            "slug": post.slug,
            "title": post.title,
            "excerpt": post.excerpt,
            "tone": post.tone,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "substack_url": add_utm(post.substack_url, medium="related_app", campaign="detail"),
            "link_type": link_type,
            "confidence": confidence,
        })

    return {"posts": posts}
