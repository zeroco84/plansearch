"""PlanSearch — AI Content Linking Worker.

Links Build posts to planning applications using Claude Haiku to extract
structured metadata (topics, locations, planning refs, councils, tone).

Per spec Build Note #3: Content linking is a background job, never blocking.
Posts display without a related applications panel if linking hasn't run yet.
"""

import json
import logging
from typing import Optional

import httpx
from sqlalchemy import select, text, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.models import BuildPost, PostApplicationLink, Application, AdminConfig

logger = logging.getLogger(__name__)


CONTENT_LINKING_PROMPT = """
You are connecting a newsletter post about Irish housing/planning to
relevant planning applications in a database.

POST TITLE: {title}
POST EXCERPT: {excerpt}

Extract:
1. Any specific planning applications mentioned (reference numbers if visible)
2. Specific locations (addresses, estates, development names)
3. Key planning topics covered
4. Councils or authorities mentioned or relevant

Topics to choose from:
judicial_review, LRD, SHD, student_accommodation, build_to_rent,
social_housing, apartment_guidelines, planning_reform, ABP,
further_information, infrastructure, viability

Respond ONLY in valid JSON:
{{
  "planning_refs": [],
  "locations": [],
  "topics": [],
  "councils": [],
  "tone": "analysis|opinion|case_study|news",
  "summary_one_line": "One sentence summary of the post."
}}
"""


async def _get_claude_key(db: AsyncSession) -> Optional[str]:
    """Retrieve the Claude API key from admin configuration."""
    try:
        result = await db.execute(
            select(AdminConfig).where(AdminConfig.key == "claude_api_key")
        )
        config = result.scalar_one_or_none()
        if config:
            from app.utils.crypto import decrypt_value
            return decrypt_value(config.value)
    except Exception:
        pass

    settings = get_settings()
    return getattr(settings, "claude_api_key", None)


async def _classify_post(title: str, excerpt: str, api_key: str) -> dict:
    """Call Claude Haiku to extract structured metadata from a post."""
    prompt = CONTENT_LINKING_PROMPT.format(title=title, excerpt=excerpt)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )
        resp.raise_for_status()

    data = resp.json()
    content = data["content"][0]["text"]

    # Parse JSON, handling potential markdown wrapping
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0]

    return json.loads(content)


async def _find_application_by_ref(db: AsyncSession, ref: str) -> Optional[int]:
    """Find an application by reference number."""
    result = await db.execute(
        select(Application.id).where(Application.reg_ref == ref).limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def _search_applications_by_address(db: AsyncSession, location: str, limit: int = 5) -> list[int]:
    """Fuzzy search for applications by address/location."""
    result = await db.execute(
        select(Application.id)
        .where(
            Application.search_vector.op("@@")(
                func.plainto_tsquery("english", location)
            )
        )
        .limit(limit)
    )
    return [row[0] for row in result.fetchall()]


async def _link_post(
    db: AsyncSession, post_id: int, app_id: int, link_type: str, confidence: float
):
    """Upsert a post↔application link."""
    stmt = pg_insert(PostApplicationLink).values(
        post_id=post_id,
        application_id=app_id,
        link_type=link_type,
        confidence=confidence,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["post_id", "application_id"],
        set_={"link_type": link_type, "confidence": confidence},
    )
    await db.execute(stmt)


async def link_post_to_applications(db: AsyncSession, post: BuildPost, api_key: str):
    """Extract metadata from a Build post and link to planning applications.

    Steps:
    1. Claude extracts structured metadata (topics, locations, refs, councils)
    2. Store metadata on the post
    3. Match by explicit planning reference (confidence 1.0)
    4. Match by location fuzzy search (confidence 0.8)
    5. Match by topic + council (confidence 0.6)
    """
    try:
        result = await _classify_post(post.title, post.excerpt or "", api_key)
    except Exception as e:
        logger.error(f"Content linking: Claude error for post {post.slug}: {e}")
        return

    # Step 2: Store extracted metadata
    await db.execute(
        update(BuildPost)
        .where(BuildPost.id == post.id)
        .values(
            summary_one_line=result.get("summary_one_line"),
            topics=result.get("topics", []),
            mentioned_councils=result.get("councils", []),
            tone=result.get("tone"),
            updated_at=func.now(),
        )
    )

    link_count = 0

    # Step 3: Match by explicit planning reference
    for ref in result.get("planning_refs", []):
        app_id = await _find_application_by_ref(db, ref)
        if app_id:
            await _link_post(db, post.id, app_id, "mentioned", 1.0)
            link_count += 1

    # Step 4: Match by location (fuzzy address search)
    for location in result.get("locations", []):
        app_ids = await _search_applications_by_address(db, location, limit=5)
        for app_id in app_ids:
            await _link_post(db, post.id, app_id, "related_location", 0.8)
            link_count += 1

    # Step 5: Match by topic + council
    for topic in result.get("topics", []):
        for council in result.get("councils", []):
            # Search applications matching this council with relevant categories
            council_result = await db.execute(
                select(Application.id)
                .where(Application.planning_authority == council)
                .limit(10)
            )
            for row in council_result.fetchall():
                await _link_post(db, post.id, row[0], "related_topic", 0.6)
                link_count += 1

    await db.commit()
    logger.info(f"Content linking: {post.slug} → {link_count} links created")


async def link_unlinked_posts(db: AsyncSession):
    """Find Build posts without AI metadata and link them.

    Per spec: Run as --unlinked-only cron job 30 minutes after RSS ingest.
    """
    api_key = await _get_claude_key(db)
    if not api_key:
        logger.error("Content linking: No Claude API key configured")
        return

    # Find posts without topics (AI metadata not yet extracted)
    result = await db.execute(
        select(BuildPost)
        .where(BuildPost.topics == None)  # noqa: E711
        .order_by(BuildPost.published_at.desc())
        .limit(20)
    )
    unlinked = result.scalars().all()

    if not unlinked:
        logger.info("Content linking: No unlinked posts found")
        return

    logger.info(f"Content linking: Processing {len(unlinked)} unlinked posts")
    for post in unlinked:
        await link_post_to_applications(db, post, api_key)
