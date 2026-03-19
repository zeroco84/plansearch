"""PlanSearch — Alert Engine.

Matches new/changed applications against user alert profiles and sends
digest emails via AWS SES.

Schedule (managed in main.py):
- instant profiles: every 30 minutes
- daily profiles: once per day at 8am
- weekly profiles: Monday 8am
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select, and_, or_, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import engine
from app.models import User, AlertProfile, AlertDelivery, AlertMatch, Application

logger = logging.getLogger(__name__)

SES_REGION = os.environ.get("AWS_SES_REGION", "eu-west-1")
SES_FROM = os.environ.get("SES_FROM_EMAIL", "alerts@plansearch.cc")

# Map trigger events to SQL conditions
EVENT_CONDITIONS = {
    "new_application": "apn_date >= :since",
    "granted": "decision ILIKE '%grant%' AND dec_date >= :since",
    "refused": "decision ILIKE '%refus%' AND dec_date >= :since",
    "under_construction": "lifecycle_stage = 'under_construction'",
    "complete": "lifecycle_stage = 'complete'",
    "fsc_filed": "lifecycle_stage = 'fsc_filed'",
    "further_info": "stage ILIKE '%further%'",
    "withdrawn": "decision ILIKE '%withdrawn%' AND dec_date >= :since",
}


async def find_matches(db, profile: AlertProfile, since: datetime) -> list:
    """Find applications matching an alert profile since a given datetime."""
    conditions = ["1=1"]
    params: dict = {"since": since}

    # Location filter
    if profile.planning_authorities:
        conditions.append("planning_authority = ANY(:authorities)")
        params["authorities"] = profile.planning_authorities

    # Category filter
    if profile.dev_categories:
        conditions.append("dev_category = ANY(:categories)")
        params["categories"] = profile.dev_categories

    # Value filter
    if profile.value_min:
        conditions.append("est_value_high >= :value_min")
        params["value_min"] = profile.value_min
    if profile.value_max:
        conditions.append("est_value_high <= :value_max")
        params["value_max"] = profile.value_max

    # Keyword filter
    if profile.keywords:
        conditions.append("search_vector @@ plainto_tsquery('english', :keywords)")
        params["keywords"] = profile.keywords

    # Trigger events — OR across all selected events
    if not profile.trigger_events:
        return []

    event_clauses = []
    for event in profile.trigger_events:
        clause = EVENT_CONDITIONS.get(event)
        if clause:
            event_clauses.append(f"({clause})")

    if not event_clauses:
        return []

    conditions.append(f"({' OR '.join(event_clauses)})")

    where = " AND ".join(conditions)
    result = await db.execute(
        text(f"""
            SELECT reg_ref, proposal, location, planning_authority,
                   decision, dev_category, est_value_low, est_value_high,
                   apn_date, dec_date, lifecycle_stage, link_app_details
            FROM applications
            WHERE {where}
            ORDER BY apn_date DESC NULLS LAST
            LIMIT 50
        """),
        params,
    )

    return result.fetchall()


def build_email_html(
    user: User, profile: AlertProfile, matches: list
) -> tuple[str, str]:
    """Build email subject and HTML body for an alert digest."""
    count = len(matches)
    subject = (
        f"PlanSearch Alert: {count} new match"
        f"{'es' if count != 1 else ''} — {profile.name}"
    )

    rows = ""
    for app in matches[:20]:
        value_str = ""
        if app.est_value_high:
            if app.est_value_high >= 1_000_000:
                value_str = (
                    f" · <b style='color:#0d9488'>€{app.est_value_high/1_000_000:.1f}m</b>"
                )
            else:
                value_str = (
                    f" · <b style='color:#0d9488'>€{app.est_value_high//1000}k</b>"
                )

        plansearch_url = f"https://plansearch.cc/application/{app.reg_ref}"
        decision_colour = (
            "#16a34a" if app.decision and "GRANT" in app.decision.upper()
            else "#dc2626" if app.decision and "REFUS" in app.decision.upper()
            else "#64748b"
        )
        decision_badge = (
            f'<span style="background:{decision_colour};color:white;font-size:11px;'
            f'padding:2px 6px;border-radius:4px;font-weight:600">'
            f'{app.decision or "PENDING"}</span>'
        ) if app.decision else ""

        proposal_text = (app.proposal or "")[:200]
        if app.proposal and len(app.proposal) > 200:
            proposal_text += "..."

        rows += f"""
        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:12px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                <span style="font-family:monospace;font-size:12px;color:#6b7280">{app.reg_ref}</span>
                {decision_badge}
                {value_str}
            </div>
            <div style="font-size:14px;color:#111827;margin-bottom:4px;font-weight:500">
                {proposal_text}
            </div>
            <div style="font-size:12px;color:#6b7280;margin-bottom:10px">
                {app.location or ''} · {app.planning_authority or ''}
            </div>
            <a href="{plansearch_url}" style="font-size:12px;color:#0d9488;text-decoration:none">
                View on PlanSearch →
            </a>
        </div>"""

    more_note = ""
    if count > 20:
        more_note = (
            f'<p style="color:#6b7280;font-size:13px">+ {count - 20} more results. '
            f'<a href="https://plansearch.cc/alerts" style="color:#0d9488">'
            f"View all on PlanSearch</a></p>"
        )

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                 max-width:640px;margin:0 auto;background:#f9fafb;padding:20px">
        <div style="background:white;border-radius:12px;overflow:hidden;
                    box-shadow:0 1px 3px rgba(0,0,0,0.1)">
            <div style="background:#0f172a;padding:24px 32px">
                <div style="font-size:20px;font-weight:700;color:#2dd4bf">PlanSearch</div>
                <div style="font-size:13px;color:#94a3b8;margin-top:4px">
                    Planning Intelligence Alert
                </div>
            </div>
            <div style="padding:24px 32px">
                <h2 style="font-size:18px;color:#111827;margin:0 0 4px">{profile.name}</h2>
                <p style="color:#6b7280;font-size:14px;margin:0 0 20px">
                    {count} new planning application{'s' if count != 1 else ''}
                    matched your alert profile.
                </p>
                {rows}
                {more_note}
                <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
                <p style="font-size:12px;color:#9ca3af;margin:0">
                    You're receiving this because you set up a PlanSearch alert profile.<br>
                    <a href="https://plansearch.cc/alerts" style="color:#0d9488">
                        Manage your alerts
                    </a> ·
                    <a href="https://plansearch.cc/alerts/unsubscribe" style="color:#0d9488">
                        Unsubscribe
                    </a>
                </p>
            </div>
        </div>
    </body>
    </html>"""

    return subject, html


def send_ses_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via AWS SES."""
    try:
        client = boto3.client("ses", region_name=SES_REGION)
        client.send_email(
            Source=SES_FROM,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
            },
        )
        logger.info(f"Alert email sent to {to_email}: {subject}")
        return True
    except ClientError as e:
        logger.error(f"SES error sending to {to_email}: {e}")
        return False


async def run_alert_engine(frequency_filter: Optional[str] = None):
    """Main alert engine — match profiles and send digest emails.

    Args:
        frequency_filter: only process profiles with this frequency
                         (instant/daily/weekly). None = all.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    logger.info(f"Alert engine starting (frequency_filter={frequency_filter})")

    async with session_factory() as db:
        # Get active subscribers with active alert profiles
        profiles_query = (
            select(AlertProfile)
            .join(User)
            .where(
                and_(
                    AlertProfile.is_active == True,  # noqa: E712
                    User.subscription_status == "active",
                    User.is_active == True,  # noqa: E712
                )
            )
        )
        if frequency_filter:
            profiles_query = profiles_query.where(
                AlertProfile.frequency == frequency_filter
            )

        result = await db.execute(profiles_query)
        profiles = result.scalars().all()

        logger.info(f"Processing {len(profiles)} active alert profiles")

        for profile in profiles:
            try:
                # Determine lookback window
                if profile.frequency == "instant":
                    since = datetime.now(timezone.utc) - timedelta(minutes=35)
                elif profile.frequency == "daily":
                    since = datetime.now(timezone.utc) - timedelta(hours=25)
                else:  # weekly
                    since = datetime.now(timezone.utc) - timedelta(days=8)

                # Use last_triggered_at if more recent
                if profile.last_triggered_at and profile.last_triggered_at > since:
                    since = profile.last_triggered_at

                matches = await find_matches(db, profile, since)

                if not matches:
                    continue

                # Get user
                user_result = await db.execute(
                    select(User).where(User.id == profile.user_id)
                )
                user = user_result.scalar_one_or_none()
                if not user:
                    continue

                # Build and send email
                subject, html = build_email_html(user, profile, matches)
                success = send_ses_email(user.email, subject, html)

                # Record delivery
                delivery = AlertDelivery(
                    user_id=user.id,
                    alert_profile_id=profile.id,
                    application_count=len(matches),
                    email_subject=subject,
                    status="sent" if success else "failed",
                )
                db.add(delivery)
                await db.flush()

                # Record matches
                for app in matches[:50]:
                    match = AlertMatch(
                        delivery_id=delivery.id,
                        reg_ref=app.reg_ref,
                        trigger_event="matched",
                    )
                    db.add(match)

                # Update last triggered
                profile.last_triggered_at = datetime.now(timezone.utc)
                await db.commit()

                logger.info(
                    f"Alert sent: profile={profile.name} "
                    f"user={user.email} matches={len(matches)}"
                )

            except Exception as e:
                logger.error(f"Error processing profile {profile.id}: {e}")
                await db.rollback()

    logger.info("Alert engine complete")
