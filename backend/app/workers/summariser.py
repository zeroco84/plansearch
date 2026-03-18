"""PlanSearch — Proposal Summariser.

Strips legal boilerplate from Irish planning application descriptions
and returns a clean, human-readable summary of what is actually proposed.
Uses Claude Haiku for fast, cheap summarisation (~300ms per call).
Results are cached in the applications.proposal_summary column.
"""

import logging
from typing import Optional

from anthropic import AsyncAnthropic
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminConfig
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)

SUMMARISE_PROMPT = """You are summarising Irish planning applications for a property intelligence platform.

Extract ONLY the key development facts from this planning application description. 
Strip out all legal boilerplate including:
- Habitats Directive / EIA screening notices
- "Plans available for inspection" text
- Public consultation period information  
- Statutory references and regulation citations
- "Any person may apply..." notices
- Council website URLs and inspection hours

Return a clean 1-3 sentence summary covering only:
- What is being built / changed
- How many units / keys / m² (if stated)
- Any notable features (e.g. social housing, protected structure, commercial use)

Be concise. Do not start with "The proposed development is...". Just describe what it is.

Examples:
- "29 social and affordable homes: 8 three-bed houses, 4 two-bed apartments, 1 studio and 8 one-bed apartments, with associated landscaping and parking."
- "147-unit private apartment scheme in 3 blocks of 4–8 storeys, with ground floor retail and 96 car parking spaces."
- "Extension to existing hotel adding 45 bedrooms and a new conference facility."

Planning description:
{proposal}

Summary:"""


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


async def summarise_proposal(api_key: str, proposal: str) -> Optional[str]:
    """Generate a clean summary of a planning proposal using Claude Haiku."""
    if not proposal or len(proposal.strip()) < 50:
        return None

    # Don't bother summarising if it's already short
    if len(proposal) < 200:
        return proposal

    client = AsyncAnthropic(api_key=api_key)
    try:
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": SUMMARISE_PROMPT.format(proposal=proposal[:2000]),
            }],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"Summarisation failed: {e}")
        return None


async def get_or_create_summary(
    db: AsyncSession, reg_ref: str, proposal: str
) -> Optional[str]:
    """Get cached summary or generate a new one."""
    # Check if we already have a summary
    result = await db.execute(
        text("""
            SELECT proposal_summary FROM applications
            WHERE reg_ref = :ref AND proposal_summary IS NOT NULL
        """),
        {"ref": reg_ref},
    )
    row = result.fetchone()
    if row:
        return row[0]

    # Get API key
    api_key = await get_claude_api_key(db)
    if not api_key:
        return None

    # Generate new summary
    summary = await summarise_proposal(api_key, proposal)
    if summary:
        await db.execute(
            text("""
                UPDATE applications
                SET proposal_summary = :summary,
                    proposal_summarised_at = NOW()
                WHERE reg_ref = :ref
            """),
            {"summary": summary, "ref": reg_ref},
        )
        await db.commit()

    return summary
