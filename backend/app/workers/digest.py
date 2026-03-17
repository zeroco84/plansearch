"""PlanSearch — Weekly Digest Generator + RSS Feed.

Generates a weekly digest of significant newly granted planning permissions.
Publishes as:
  1. RSS feed at /feed/weekly-digest.xml
  2. JSON API at /api/digest/latest
"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, tostring

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, WeeklyDigest

logger = logging.getLogger(__name__)

SIGNIFICANCE_THRESHOLD = 50  # Default – adjustable in admin_config


async def generate_weekly_digest(
    db: AsyncSession,
    threshold: int = SIGNIFICANCE_THRESHOLD,
) -> dict:
    """Find all newly granted significant applications in the past 7 days."""
    today = date.today()
    week_start = today - timedelta(days=7)
    week_end = today

    result = await db.execute(
        select(Application)
        .where(
            and_(
                Application.dec_date >= week_start,
                Application.decision.ilike("%grant%"),
                Application.significance_score >= threshold,
            )
        )
        .order_by(Application.est_value_high.desc().nullslast())
    )
    applications = result.scalars().all()

    entries = []
    for app in applications:
        applicant = None
        if app.applicant_forename and app.applicant_surname:
            applicant = f"{app.applicant_forename} {app.applicant_surname}"
        elif app.applicant_name:
            applicant = app.applicant_name

        value_str = None
        if app.est_value_low and app.est_value_high:
            value_str = f"€{app.est_value_low:,.0f} – €{app.est_value_high:,.0f}"
        elif app.est_value_high:
            value_str = f"~€{app.est_value_high:,.0f}"

        entry = {
            "reg_ref": app.reg_ref,
            "planning_authority": app.planning_authority or "Dublin City Council",
            "location": app.location,
            "proposal": app.proposal,
            "applicant": applicant,
            "dev_category": app.dev_category,
            "dev_subcategory": app.dev_subcategory,
            "num_residential_units": app.num_residential_units,
            "floor_area": app.floor_area,
            "est_value_low": app.est_value_low,
            "est_value_high": app.est_value_high,
            "est_value_str": value_str,
            "est_value_basis": app.est_value_basis,
            "decision": app.decision,
            "decision_date": str(app.dec_date) if app.dec_date else None,
            "link_app_details": app.link_app_details,
            "significance_score": app.significance_score,
            "lifecycle_stage": app.lifecycle_stage,
        }
        entries.append(entry)

    # Store digest
    digest = WeeklyDigest(
        week_start=week_start,
        week_end=week_end,
        total_entries=len(entries),
        digest_data={"entries": entries},
        published=True,
    )
    db.add(digest)
    await db.commit()

    logger.info(f"Digest: Generated {len(entries)} entries for week {week_start} – {week_end}")
    return {"week_start": str(week_start), "week_end": str(week_end), "entries": len(entries)}


def generate_rss_xml(digest_data: dict, week_start: date) -> str:
    """Generate RSS XML from digest data."""
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "PlanSearch — Weekly Significant Approvals"
    SubElement(channel, "link").text = "https://plansearch.ie"
    SubElement(channel, "description").text = (
        "Newly granted planning permissions in Ireland this week"
    )
    SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    entries = digest_data.get("entries", [])
    for entry in entries:
        item = SubElement(channel, "item")

        # Title: "€42m Residential Development, Cherrywood, Dublin 18"
        parts = []
        if entry.get("est_value_str"):
            parts.append(entry["est_value_str"])
        if entry.get("proposal"):
            desc_short = entry["proposal"][:80]
            parts.append(desc_short)
        if entry.get("location"):
            parts.append(entry["location"][:80])
        SubElement(item, "title").text = ", ".join(parts) if parts else entry["reg_ref"]

        # Description
        lines = []
        if entry.get("proposal"):
            lines.append(entry["proposal"][:200])
        if entry.get("applicant"):
            lines.append(f"Applicant: {entry['applicant']}")
        if entry.get("est_value_str"):
            lines.append(f"Est. value: {entry['est_value_str']}")
        if entry.get("planning_authority"):
            lines.append(f"Authority: {entry['planning_authority']}")
        lines.append(f"Reference: {entry['reg_ref']}")
        SubElement(item, "description").text = "\n".join(lines)

        # Link
        SubElement(item, "link").text = (
            entry.get("link_app_details") or
            f"https://plansearch.ie/application/{entry['reg_ref']}"
        )

        SubElement(item, "pubDate").text = datetime.utcnow().strftime(
            "%a, %d %b %Y %H:%M:%S +0000"
        )

    return tostring(rss, encoding="unicode", xml_declaration=True)
