"""PlanSearch — Concurrent Claude AI Classification Worker.

Classifies planning applications into development categories
using Claude Haiku with asyncio.Semaphore-controlled parallelism.
20 concurrent requests with exponential backoff on rate limits.
Reads API key from encrypted admin_config.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from anthropic import AsyncAnthropic
from sqlalchemy import select, text, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Application, AdminConfig
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)
settings = get_settings()

CONCURRENT_REQUESTS = 20
COMMIT_EVERY = 500

CLASSIFICATION_PROMPT = """You are classifying Irish planning applications.
Given the description and location below, classify into exactly one category.

CATEGORIES:
residential_new_build | residential_extension | residential_conversion |
hotel_accommodation | student_accommodation | commercial_retail |
commercial_office | industrial_warehouse | data_centre | mixed_use |
protected_structure | telecommunications | renewable_energy | signage |
change_of_use | demolition | other

Notes:
- student_accommodation: purpose-built student accommodation (PBSA), student beds, student housing
- data_centre: data centres, server facilities, colocation facilities
- hotel_accommodation: hotels, hostels, apart-hotels, guesthouses (NOT student accommodation)
- industrial_warehouse: warehouses, factories, logistics (NOT data centres)

Also provide a subcategory (e.g. "apartment block", "PBSA",
"data centre", "house extension") and confidence score 0.0–1.0.

REF: {reg_ref}
LOCATION: {location}
SHORT: {proposal}

Respond ONLY with valid JSON:
{{"category": "...", "subcategory": "...", "confidence": 0.0}}"""

CATEGORY_LABELS = {
    "residential_new_build": "New Residential",
    "residential_extension": "Extension / Renovation",
    "residential_conversion": "Residential Conversion",
    "hotel_accommodation": "Hotel & Accommodation",
    "student_accommodation": "Student Accommodation",
    "commercial_retail": "Retail & Food",
    "commercial_office": "Office",
    "industrial_warehouse": "Industrial / Warehouse",
    "data_centre": "Data Centre",
    "mixed_use": "Mixed Use",
    "protected_structure": "Protected Structure",
    "telecommunications": "Telecoms",
    "renewable_energy": "Renewable Energy",
    "signage": "Signage",
    "change_of_use": "Change of Use",
    "demolition": "Demolition",
    "other": "Other",
}


async def get_claude_api_key(db: AsyncSession) -> Optional[str]:
    """Retrieve the Claude API key from encrypted admin_config."""
    result = await db.execute(
        select(AdminConfig).where(AdminConfig.key == "claude_api_key")
    )
    config = result.scalar_one_or_none()

    if not config:
        logger.warning("Claude API key not found in admin_config")
        return None

    if config.encrypted:
        return decrypt_value(config.value)
    return config.value


async def call_claude_classify(
    client: AsyncAnthropic, proposal: str, location: str = "", reg_ref: str = "",
    retries: int = 3,
) -> Optional[dict]:
    """Call Claude Haiku to classify a single planning proposal.

    Retries up to `retries` times with exponential backoff on 429 rate limits.
    """
    for attempt in range(retries):
        try:
            prompt = CLASSIFICATION_PROMPT.format(
                reg_ref=reg_ref or "",
                location=location or "Not specified",
                proposal=(proposal or "Not specified")[:500],
            )

            message = await client.messages.create(
                model=settings.classifier_model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text.strip()

            # Handle markdown code fences
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1].lstrip("json").strip()

            result = json.loads(response_text)

            category = result.get("category", "other")
            if category not in CATEGORY_LABELS:
                category = "other"

            return {
                "category": category,
                "subcategory": result.get("subcategory", ""),
                "confidence": min(1.0, max(0.0, float(result.get("confidence", 0.5)))),
            }

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response for {reg_ref}")
            return None
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    f"Rate limited on {reg_ref}, waiting {wait}s "
                    f"(retry {attempt + 1}/{retries})"
                )
                await asyncio.sleep(wait)
                continue
            logger.error(f"Classification error for {reg_ref}: {e}")
            return None

    logger.error(f"All {retries} retries exhausted for {reg_ref}")
    return None


async def classify_all(
    db: AsyncSession,
    progress: Optional[dict] = None,
    limit: Optional[int] = None,
) -> dict:
    """Classify all unclassified applications concurrently.

    Uses asyncio.Semaphore to control parallelism at 20 concurrent requests.
    Updates the shared progress dict for the live admin UI counter.
    """
    # Get Claude API key
    api_key = await get_claude_api_key(db)
    if not api_key:
        if progress:
            progress["running"] = False
        return {"error": "Claude API key not configured. Set it via the admin UI."}

    # Fetch all unclassified records (just the columns we need)
    result = await db.execute(
        select(
            Application.id,
            Application.reg_ref,
            Application.proposal,
            Application.location,
        )
        .where(
            and_(
                Application.dev_category.is_(None),
                Application.proposal.isnot(None),
                Application.proposal != "",
            )
        )
        .order_by(Application.id)
        .limit(limit or 999999)
    )
    records = result.all()

    total = len(records)
    logger.info(
        f"Classifying {total} unclassified records with "
        f"{CONCURRENT_REQUESTS} concurrent requests"
    )

    if progress:
        progress["total"] = total

    stats = {"classified": 0, "errors": 0, "total": total}
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    client = AsyncAnthropic(api_key=api_key)
    lock = asyncio.Lock()

    async def classify_one(record) -> bool:
        async with semaphore:
            # Check for stop signal
            if progress and progress.get("stop_requested"):
                return False

            try:
                result = await call_claude_classify(
                    client,
                    proposal=record.proposal or "",
                    location=record.location or "",
                    reg_ref=record.reg_ref or "",
                )

                if result:
                    async with lock:
                        await db.execute(text("SAVEPOINT classify_upsert"))
                        try:
                            await db.execute(
                                text("""
                                    UPDATE applications
                                    SET dev_category = :category,
                                        dev_subcategory = :subcategory,
                                        classification_confidence = :confidence,
                                        classified_at = NOW()
                                    WHERE id = :id
                                """),
                                {
                                    "category": result["category"],
                                    "subcategory": result.get("subcategory", ""),
                                    "confidence": result.get("confidence", 0.8),
                                    "id": record.id,
                                },
                            )
                            await db.execute(text("RELEASE SAVEPOINT classify_upsert"))
                        except Exception as db_err:
                            await db.execute(
                                text("ROLLBACK TO SAVEPOINT classify_upsert")
                            )
                            logger.error(
                                f"DB error for {record.reg_ref}: {db_err}"
                            )
                            stats["errors"] += 1
                            if progress:
                                progress["errors"] += 1
                            return False

                        stats["classified"] += 1
                        if progress:
                            progress["processed"] += 1

                        # Commit periodically
                        if stats["classified"] % COMMIT_EVERY == 0:
                            await db.commit()
                            logger.info(
                                f"Classified {stats['classified']}/{total}..."
                            )
                    return True
                else:
                    stats["errors"] += 1
                    if progress:
                        progress["errors"] += 1
                    return False

            except Exception as e:
                logger.error(f"Error classifying {record.reg_ref}: {e}")
                stats["errors"] += 1
                if progress:
                    progress["errors"] += 1
                return False

    # Run all concurrently, controlled by semaphore
    tasks = [classify_one(r) for r in records]
    await asyncio.gather(*tasks)
    await db.commit()

    if progress:
        progress["running"] = False
        progress["stop_requested"] = False

    logger.info(f"Classification complete: {stats}")
    return stats


# Legacy function kept for backward compatibility
async def run_classification_batch(
    db: AsyncSession, batch_size: int = 100
) -> dict:
    """Run a batch of AI classifications (legacy sequential mode)."""
    return await classify_all(db, limit=batch_size)


async def reclassify_keyword(
    db: AsyncSession, keyword: str, target_category: str
) -> dict:
    """Directly reclassify records whose proposal contains keyword.

    Useful for bulk corrections, e.g. reclassifying all "student accommodation"
    proposals from hotel_accommodation to student_accommodation.
    """
    result = await db.execute(
        text("""
            SELECT id FROM applications
            WHERE proposal ILIKE :pattern
              AND (dev_category IS NULL OR dev_category != :target)
        """),
        {"pattern": f"%{keyword}%", "target": target_category},
    )
    rows = result.fetchall()

    logger.info(
        f"Reclassifying {len(rows)} records matching '{keyword}' to {target_category}"
    )

    for i, row in enumerate(rows):
        await db.execute(
            text("""
                UPDATE applications
                SET dev_category = :category, classified_at = NOW()
                WHERE id = :id
            """),
            {"category": target_category, "id": row.id},
        )
        if (i + 1) % 500 == 0:
            await db.commit()
            logger.info(f"Committed {i + 1}/{len(rows)} reclassifications...")

    await db.commit()
    logger.info(f"Reclassified {len(rows)} records to {target_category}")
    return {"reclassified": len(rows), "keyword": keyword, "target_category": target_category}
