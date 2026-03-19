"""PlanSearch — Alert Profile API routes.

CRUD for alert profiles + delivery history.
All endpoints require active subscription (get_active_subscriber).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import AlertProfile, AlertDelivery, User
from app.auth import get_active_subscriber

router = APIRouter()

TIER_LIMITS = {"starter": 5, "professional": 25, "agency": 999}

VALID_EVENTS = {
    "new_application", "granted", "refused", "under_construction",
    "complete", "fsc_filed", "further_info", "withdrawn",
}


class AlertProfileRequest(BaseModel):
    name: str
    trigger_events: list[str]
    planning_authorities: list[str] = []
    dev_categories: list[str] = []
    value_min: Optional[int] = None
    value_max: Optional[int] = None
    keywords: Optional[str] = None
    frequency: str = "daily"


@router.get("/alerts/profiles")
async def list_profiles(
    user: User = Depends(get_active_subscriber),
    db: AsyncSession = Depends(get_db),
):
    """List all alert profiles for the current user."""
    result = await db.execute(
        select(AlertProfile)
        .where(AlertProfile.user_id == user.id)
        .order_by(AlertProfile.created_at.desc())
    )
    profiles = result.scalars().all()
    return {
        "profiles": [
            {
                "id": str(p.id),
                "name": p.name,
                "is_active": p.is_active,
                "trigger_events": p.trigger_events,
                "planning_authorities": p.planning_authorities,
                "dev_categories": p.dev_categories,
                "value_min": p.value_min,
                "value_max": p.value_max,
                "keywords": p.keywords,
                "frequency": p.frequency,
                "last_triggered_at": p.last_triggered_at,
            }
            for p in profiles
        ]
    }


@router.post("/alerts/profiles")
async def create_profile(
    req: AlertProfileRequest,
    user: User = Depends(get_active_subscriber),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert profile."""
    # Check profile limit for tier
    limit = TIER_LIMITS.get(user.subscription_tier, 0)
    count_result = await db.execute(
        select(AlertProfile).where(AlertProfile.user_id == user.id)
    )
    current_count = len(count_result.scalars().all())
    if current_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Profile limit reached ({limit} for {user.subscription_tier} plan). Upgrade to add more.",
        )

    # Validate events
    invalid = set(req.trigger_events) - VALID_EVENTS
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid events: {invalid}")

    if req.frequency not in ("instant", "daily", "weekly"):
        raise HTTPException(
            status_code=400, detail="frequency must be instant, daily or weekly"
        )

    profile = AlertProfile(
        user_id=user.id,
        name=req.name,
        trigger_events=req.trigger_events,
        planning_authorities=req.planning_authorities,
        dev_categories=req.dev_categories,
        value_min=req.value_min,
        value_max=req.value_max,
        keywords=req.keywords,
        frequency=req.frequency,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return {"id": str(profile.id), "name": profile.name}


@router.put("/alerts/profiles/{profile_id}")
async def update_profile(
    profile_id: str,
    req: AlertProfileRequest,
    user: User = Depends(get_active_subscriber),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing alert profile."""
    result = await db.execute(
        select(AlertProfile).where(
            AlertProfile.id == profile_id, AlertProfile.user_id == user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.name = req.name
    profile.trigger_events = req.trigger_events
    profile.planning_authorities = req.planning_authorities
    profile.dev_categories = req.dev_categories
    profile.value_min = req.value_min
    profile.value_max = req.value_max
    profile.keywords = req.keywords
    profile.frequency = req.frequency
    await db.commit()
    return {"status": "updated"}


@router.delete("/alerts/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    user: User = Depends(get_active_subscriber),
    db: AsyncSession = Depends(get_db),
):
    """Delete an alert profile."""
    result = await db.execute(
        select(AlertProfile).where(
            AlertProfile.id == profile_id, AlertProfile.user_id == user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    await db.delete(profile)
    await db.commit()
    return {"status": "deleted"}


@router.patch("/alerts/profiles/{profile_id}/toggle")
async def toggle_profile(
    profile_id: str,
    user: User = Depends(get_active_subscriber),
    db: AsyncSession = Depends(get_db),
):
    """Toggle an alert profile on/off."""
    result = await db.execute(
        select(AlertProfile).where(
            AlertProfile.id == profile_id, AlertProfile.user_id == user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.is_active = not profile.is_active
    await db.commit()
    return {"is_active": profile.is_active}


@router.get("/alerts/history")
async def alert_history(
    user: User = Depends(get_active_subscriber),
    db: AsyncSession = Depends(get_db),
):
    """Return recent alert delivery history."""
    result = await db.execute(
        select(AlertDelivery)
        .where(AlertDelivery.user_id == user.id)
        .order_by(AlertDelivery.sent_at.desc())
        .limit(50)
    )
    deliveries = result.scalars().all()
    return {
        "deliveries": [
            {
                "id": str(d.id),
                "sent_at": d.sent_at,
                "application_count": d.application_count,
                "email_subject": d.email_subject,
                "status": d.status,
            }
            for d in deliveries
        ]
    }
