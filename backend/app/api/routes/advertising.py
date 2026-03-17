"""PlanSearch — Advertising API routes.

Ad selection with contextual targeting, impression/click tracking,
and admin CRUD for advertisers and campaigns.

Per spec Build Note #4: No user identifiers in impressions.
Per spec 24.5: Never ads on detail pages, map, or as pop-ups.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, update, and_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db
from app.models import Advertiser, AdCampaign, AdImpression
from app.api.routes.admin import verify_admin_token

router = APIRouter(prefix="/api/ads", tags=["advertising"])


# ── Schemas ──────────────────────────────────────────────────────────

class AdDisplay(BaseModel):
    """What the frontend receives to render a promoted card."""
    campaign_id: int
    advertiser: str
    headline: Optional[str] = None
    body_text: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    logo_url: Optional[str] = None
    campaign_type: str


class AdvertiserSchema(BaseModel):
    id: Optional[int] = None
    company_name: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    industry: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class CampaignSchema(BaseModel):
    id: Optional[int] = None
    advertiser_id: int
    campaign_name: str
    campaign_type: str = "display"
    start_date: str
    end_date: str
    status: str = "active"
    headline: Optional[str] = None
    body_text: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    logo_url: Optional[str] = None
    target_categories: Optional[list[str]] = None
    target_councils: Optional[list[str]] = None
    target_lifecycle: Optional[list[str]] = None
    agreed_price: Optional[float] = None
    invoice_ref: Optional[str] = None

    class Config:
        from_attributes = True


class CampaignStats(BaseModel):
    campaign_id: int
    campaign_name: str
    advertiser: str
    campaign_type: str
    impressions: int
    clicks: int
    ctr: float
    status: str
    start_date: str
    end_date: str
    agreed_price: Optional[float] = None


class AdDashboard(BaseModel):
    active_campaigns: int
    total_impressions_month: int
    total_clicks_month: int
    ctr_month: float
    revenue_month: float
    campaigns: list[CampaignStats]


# ── Public: Ad selection (contextual) ─────────────────────────────────

@router.get("/contextual", response_model=Optional[AdDisplay])
async def get_contextual_ad(
    dev_category: Optional[str] = None,
    council: Optional[str] = None,
    lifecycle_stage: Optional[str] = None,
    page_path: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Select most contextually relevant active ad.

    Per spec 24.4: Relevance scoring with least-shown rotation.
    """
    today = date.today()

    # Build query with relevance scoring
    result = await db.execute(
        select(AdCampaign, Advertiser.company_name)
        .join(Advertiser, AdCampaign.advertiser_id == Advertiser.id)
        .where(
            and_(
                AdCampaign.status == "active",
                AdCampaign.start_date <= today,
                AdCampaign.end_date >= today,
            )
        )
        .order_by(
            # Prefer more specific targeting matches
            desc(
                func.coalesce(
                    text(f"CASE WHEN '{dev_category or ''}' = ANY(COALESCE(ad_campaigns.target_categories, '{{}}')) THEN 2 ELSE 0 END"),
                    text("0"),
                )
                +
                func.coalesce(
                    text(f"CASE WHEN '{council or ''}' = ANY(COALESCE(ad_campaigns.target_councils, '{{}}')) THEN 1 ELSE 0 END"),
                    text("0"),
                )
            ),
            AdCampaign.impressions.asc(),  # Rotate by least shown
        )
        .limit(1)
    )

    row = result.first()
    if not row:
        return None

    campaign, company_name = row

    # Record impression (per spec Build Note #4: no user data)
    impression = AdImpression(
        campaign_id=campaign.id,
        page_path=page_path or "/unknown",
        clicked=False,
    )
    db.add(impression)

    # Increment aggregate counter
    await db.execute(
        update(AdCampaign)
        .where(AdCampaign.id == campaign.id)
        .values(impressions=AdCampaign.impressions + 1)
    )
    await db.commit()

    return AdDisplay(
        campaign_id=campaign.id,
        advertiser=company_name,
        headline=campaign.headline,
        body_text=campaign.body_text,
        cta_text=campaign.cta_text,
        cta_url=campaign.cta_url,
        logo_url=campaign.logo_url,
        campaign_type=campaign.campaign_type or "display",
    )


# ── Public: Click tracking ────────────────────────────────────────────

@router.post("/click/{campaign_id}")
async def record_click(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Record an ad click. No user data stored — aggregate only."""
    await db.execute(
        update(AdCampaign)
        .where(AdCampaign.id == campaign_id)
        .values(clicks=AdCampaign.clicks + 1)
    )
    await db.commit()
    return {"ok": True}


# ── Admin: Advertiser CRUD ────────────────────────────────────────────

@router.get("/admin/advertisers", dependencies=[Depends(verify_admin_token)])
async def list_advertisers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Advertiser).order_by(desc(Advertiser.created_at))
    )
    return [AdvertiserSchema.model_validate(a) for a in result.scalars().all()]


@router.post("/admin/advertisers", dependencies=[Depends(verify_admin_token)])
async def create_advertiser(data: AdvertiserSchema, db: AsyncSession = Depends(get_db)):
    adv = Advertiser(
        company_name=data.company_name,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        industry=data.industry,
        notes=data.notes,
    )
    db.add(adv)
    await db.commit()
    await db.refresh(adv)
    return AdvertiserSchema.model_validate(adv)


@router.put("/admin/advertisers/{adv_id}", dependencies=[Depends(verify_admin_token)])
async def update_advertiser(adv_id: int, data: AdvertiserSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Advertiser).where(Advertiser.id == adv_id))
    adv = result.scalar_one_or_none()
    if not adv:
        raise HTTPException(404, "Advertiser not found")
    adv.company_name = data.company_name
    adv.contact_name = data.contact_name
    adv.contact_email = data.contact_email
    adv.industry = data.industry
    adv.notes = data.notes
    await db.commit()
    return AdvertiserSchema.model_validate(adv)


@router.delete("/admin/advertisers/{adv_id}", dependencies=[Depends(verify_admin_token)])
async def delete_advertiser(adv_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Advertiser).where(Advertiser.id == adv_id))
    adv = result.scalar_one_or_none()
    if not adv:
        raise HTTPException(404, "Advertiser not found")
    await db.delete(adv)
    await db.commit()
    return {"ok": True}


# ── Admin: Campaign CRUD ──────────────────────────────────────────────

@router.get("/admin/campaigns", dependencies=[Depends(verify_admin_token)])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AdCampaign, Advertiser.company_name)
        .join(Advertiser, AdCampaign.advertiser_id == Advertiser.id)
        .order_by(desc(AdCampaign.created_at))
    )
    campaigns = []
    for campaign, company_name in result.fetchall():
        ctr = (campaign.clicks / campaign.impressions * 100) if campaign.impressions > 0 else 0
        campaigns.append(CampaignStats(
            campaign_id=campaign.id,
            campaign_name=campaign.campaign_name,
            advertiser=company_name,
            campaign_type=campaign.campaign_type or "display",
            impressions=campaign.impressions or 0,
            clicks=campaign.clicks or 0,
            ctr=round(ctr, 1),
            status=campaign.status or "active",
            start_date=campaign.start_date.isoformat() if campaign.start_date else "",
            end_date=campaign.end_date.isoformat() if campaign.end_date else "",
            agreed_price=float(campaign.agreed_price) if campaign.agreed_price else None,
        ))
    return campaigns


@router.post("/admin/campaigns", dependencies=[Depends(verify_admin_token)])
async def create_campaign(data: CampaignSchema, db: AsyncSession = Depends(get_db)):
    campaign = AdCampaign(
        advertiser_id=data.advertiser_id,
        campaign_name=data.campaign_name,
        campaign_type=data.campaign_type,
        start_date=date.fromisoformat(data.start_date),
        end_date=date.fromisoformat(data.end_date),
        status=data.status,
        headline=data.headline,
        body_text=data.body_text,
        cta_text=data.cta_text,
        cta_url=data.cta_url,
        logo_url=data.logo_url,
        target_categories=data.target_categories,
        target_councils=data.target_councils,
        target_lifecycle=data.target_lifecycle,
        agreed_price=data.agreed_price,
        invoice_ref=data.invoice_ref,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return {"id": campaign.id, "ok": True}


@router.put("/admin/campaigns/{campaign_id}", dependencies=[Depends(verify_admin_token)])
async def update_campaign(campaign_id: int, data: CampaignSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdCampaign).where(AdCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    campaign.campaign_name = data.campaign_name
    campaign.campaign_type = data.campaign_type
    campaign.start_date = date.fromisoformat(data.start_date)
    campaign.end_date = date.fromisoformat(data.end_date)
    campaign.status = data.status
    campaign.headline = data.headline
    campaign.body_text = data.body_text
    campaign.cta_text = data.cta_text
    campaign.cta_url = data.cta_url
    campaign.logo_url = data.logo_url
    campaign.target_categories = data.target_categories
    campaign.target_councils = data.target_councils
    campaign.target_lifecycle = data.target_lifecycle
    campaign.agreed_price = data.agreed_price
    campaign.invoice_ref = data.invoice_ref
    await db.commit()
    return {"ok": True}


@router.delete("/admin/campaigns/{campaign_id}", dependencies=[Depends(verify_admin_token)])
async def delete_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdCampaign).where(AdCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    await db.delete(campaign)
    await db.commit()
    return {"ok": True}


# ── Admin: Dashboard ──────────────────────────────────────────────────

@router.get("/admin/dashboard", response_model=AdDashboard, dependencies=[Depends(verify_admin_token)])
async def get_ad_dashboard(db: AsyncSession = Depends(get_db)):
    """Advertising overview dashboard — aggregate only, no PII."""
    today = date.today()
    month_start = today.replace(day=1)

    # Active campaigns
    active_result = await db.execute(
        select(func.count(AdCampaign.id)).where(
            and_(
                AdCampaign.status == "active",
                AdCampaign.start_date <= today,
                AdCampaign.end_date >= today,
            )
        )
    )
    active_count = active_result.scalar() or 0

    # Monthly impressions/clicks
    month_impressions = await db.execute(
        select(func.count(AdImpression.id)).where(
            AdImpression.created_at >= month_start
        )
    )
    impressions_month = month_impressions.scalar() or 0

    month_clicks = await db.execute(
        select(func.count(AdImpression.id)).where(
            and_(
                AdImpression.created_at >= month_start,
                AdImpression.clicked == True,
            )
        )
    )
    clicks_month = month_clicks.scalar() or 0

    ctr = (clicks_month / impressions_month * 100) if impressions_month > 0 else 0

    # Monthly revenue (sum of agreed_price for active campaigns in this month)
    revenue_result = await db.execute(
        select(func.sum(AdCampaign.agreed_price)).where(
            and_(
                AdCampaign.start_date <= today,
                AdCampaign.end_date >= month_start,
            )
        )
    )
    revenue = float(revenue_result.scalar() or 0)

    # All campaigns
    campaigns_result = await db.execute(
        select(AdCampaign, Advertiser.company_name)
        .join(Advertiser, AdCampaign.advertiser_id == Advertiser.id)
        .order_by(desc(AdCampaign.start_date))
        .limit(50)
    )
    campaigns = []
    for campaign, company in campaigns_result.fetchall():
        c_ctr = (campaign.clicks / campaign.impressions * 100) if campaign.impressions and campaign.impressions > 0 else 0
        campaigns.append(CampaignStats(
            campaign_id=campaign.id,
            campaign_name=campaign.campaign_name,
            advertiser=company,
            campaign_type=campaign.campaign_type or "display",
            impressions=campaign.impressions or 0,
            clicks=campaign.clicks or 0,
            ctr=round(c_ctr, 1),
            status=campaign.status or "active",
            start_date=campaign.start_date.isoformat() if campaign.start_date else "",
            end_date=campaign.end_date.isoformat() if campaign.end_date else "",
            agreed_price=float(campaign.agreed_price) if campaign.agreed_price else None,
        ))

    return AdDashboard(
        active_campaigns=active_count,
        total_impressions_month=impressions_month,
        total_clicks_month=clicks_month,
        ctr_month=round(ctr, 1),
        revenue_month=revenue,
        campaigns=campaigns,
    )
