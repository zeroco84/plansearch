"""PlanSearch — Claude AI Classification Worker.

Classifies planning applications into 14 development categories
using Claude Haiku. Reads API key from encrypted admin_config.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Application, AdminConfig
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)
settings = get_settings()

CLASSIFICATION_PROMPT = """You are classifying Dublin City Council planning applications.
Given the description and location below, classify into exactly one category.

CATEGORIES:
residential_new_build | residential_extension | residential_conversion |
hotel_accommodation | commercial_retail | commercial_office |
industrial_warehouse | mixed_use | protected_structure |
telecommunications | renewable_energy | signage | change_of_use |
demolition | other

Also provide a subcategory (e.g. "apartment block", "house extension",
"data centre") and confidence score 0.0–1.0.

REF: {reg_ref}
LOCATION: {location}
SHORT: {proposal}
FULL: {long_proposal}

Respond ONLY with valid JSON:
{{"category": "...", "subcategory": "...", "confidence": 0.0}}"""

CATEGORY_LABELS = {
    "residential_new_build": "New Residential",
    "residential_extension": "Extension / Renovation",
    "residential_conversion": "Residential Conversion",
    "hotel_accommodation": "Hotel & Accommodation",
    "commercial_retail": "Retail & Food",
    "commercial_office": "Office",
    "industrial_warehouse": "Industrial / Warehouse",
    "mixed_use": "Mixed Use",
    "protected_structure": "Protected Structure",
    "telecommunications": "Telecoms",
    "renewable_energy": "Renewable Energy",
    "signage": "Signage",
    "change_of_use": "Change of Use",
    "demolition": "Demolition",
    "other": "Other",
}


def build_classification_prompt(proposal: str, location: str = "", reg_ref: str = "") -> str:
    """Build the classification prompt for a given proposal.

    Returns the formatted prompt string.
    """
    return CLASSIFICATION_PROMPT.format(
        reg_ref=reg_ref or "",
        location=location or "Not specified",
        proposal=proposal or "Not specified",
        long_proposal=proposal or "Not specified",
    )


def parse_classification_response(response_text: str) -> Optional[dict]:
    """Parse a classification JSON response.

    Returns dict with category, subcategory, confidence or None on failure.
    """
    try:
        result = json.loads(response_text)
        category = result.get("category")
        if not category or category not in CATEGORY_LABELS:
            return None
        return {
            "category": category,
            "subcategory": result.get("subcategory", ""),
            "confidence": min(1.0, max(0.0, float(result.get("confidence", 0.5)))),
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


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


async def classify_application(
    reg_ref: str,
    location: str,
    proposal: str,
    long_proposal: str,
    api_key: str,
) -> Optional[dict]:
    """Classify a single application using Claude API.

    Returns dict with category, subcategory, confidence or None on failure.
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        prompt = CLASSIFICATION_PROMPT.format(
            reg_ref=reg_ref or "",
            location=location or "Not specified",
            proposal=proposal or "Not specified",
            long_proposal=long_proposal or "Not specified",
        )

        message = client.messages.create(
            model=settings.classifier_model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()

        # Parse JSON response
        result = json.loads(response_text)

        # Validate category
        category = result.get("category", "other")
        if category not in CATEGORY_LABELS:
            category = "other"

        return {
            "category": category,
            "subcategory": result.get("subcategory", ""),
            "confidence": min(1.0, max(0.0, float(result.get("confidence", 0.5)))),
        }

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON response for {reg_ref}: {response_text}")
        return None
    except Exception as e:
        logger.error(f"Classification error for {reg_ref}: {e}")
        return None


async def run_classification_batch(
    db: AsyncSession,
    batch_size: int = 100,
) -> dict:
    """Run a batch of AI classifications.

    Args:
        db: Database session
        batch_size: Number of applications to classify

    Returns:
        Dictionary with classification statistics
    """
    stats = {"classified": 0, "failed": 0, "skipped": 0}

    # Get Claude API key
    api_key = await get_claude_api_key(db)
    if not api_key:
        return {"error": "Claude API key not configured. Set it via the admin UI."}

    # Get unclassified applications
    result = await db.execute(
        select(Application)
        .where(
            and_(
                Application.dev_category.is_(None),
                Application.proposal.isnot(None),
            )
        )
        .order_by(Application.apn_date.desc().nullslast())
        .limit(batch_size)
    )
    applications = result.scalars().all()

    logger.info(f"Classifying {len(applications)} applications")

    for app in applications:
        try:
            result = await classify_application(
                reg_ref=app.reg_ref,
                location=app.location or "",
                proposal=app.proposal or "",
                long_proposal=app.long_proposal or "",
                api_key=api_key,
            )

            if result:
                await db.execute(
                    update(Application)
                    .where(Application.id == app.id)
                    .values(
                        dev_category=result["category"],
                        dev_subcategory=result["subcategory"],
                        classification_confidence=result["confidence"],
                        classified_at=datetime.utcnow(),
                    )
                )
                stats["classified"] += 1
            else:
                stats["failed"] += 1

            # Commit every 10
            if (stats["classified"] + stats["failed"]) % 10 == 0:
                await db.commit()
                logger.info(f"Classified {stats['classified']}, failed {stats['failed']}")

        except Exception as e:
            logger.error(f"Error classifying {app.reg_ref}: {e}")
            stats["failed"] += 1

    await db.commit()
    logger.info(f"Classification batch complete: {stats}")
    return stats
