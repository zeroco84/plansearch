"""PlanSearch — Stripe Billing API routes.

Checkout sessions, customer portal, webhook handler.
Webhook endpoint has NO auth — called directly by Stripe.
"""

import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.auth import get_current_user

router = APIRouter()

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

# Stripe Price IDs — set in env after creating products in Stripe Dashboard
PRICE_IDS = {
    "starter": os.environ.get("STRIPE_PRICE_STARTER"),            # €29/month
    "professional": os.environ.get("STRIPE_PRICE_PROFESSIONAL"),   # €79/month
    "agency": os.environ.get("STRIPE_PRICE_AGENCY"),               # €199/month
}

TIER_LIMITS = {
    "starter": 5,
    "professional": 25,
    "agency": 999,
}


@router.post("/billing/checkout")
async def create_checkout(
    tier: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for subscription."""
    if tier not in PRICE_IDS or not PRICE_IDS[tier]:
        raise HTTPException(status_code=400, detail="Invalid tier")

    # Create or retrieve Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            metadata={"user_id": str(user.id)},
        )
        user.stripe_customer_id = customer.id
        await db.commit()

    frontend_url = os.environ.get("FRONTEND_URL", "https://plansearch.cc")

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": PRICE_IDS[tier], "quantity": 1}],
        mode="subscription",
        success_url=f"{frontend_url}/alerts?subscribed=true",
        cancel_url=f"{frontend_url}/pricing",
        metadata={"user_id": str(user.id), "tier": tier},
    )

    return {"checkout_url": session.url}


@router.post("/billing/portal")
async def billing_portal(user: User = Depends(get_current_user)):
    """Create a Stripe Customer Portal session."""
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No subscription found")

    frontend_url = os.environ.get("FRONTEND_URL", "https://plansearch.cc")

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{frontend_url}/alerts",
    )
    return {"portal_url": session.url}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events — NO auth, called by Stripe directly."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"]["user_id"]
        tier = session["metadata"]["tier"]
        subscription_id = session.get("subscription")

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.subscription_tier = tier
            user.subscription_status = "active"
            user.stripe_subscription_id = subscription_id
            await db.commit()

    elif event["type"] in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        sub = event["data"]["object"]
        result = await db.execute(
            select(User).where(User.stripe_subscription_id == sub["id"])
        )
        user = result.scalar_one_or_none()
        if user:
            if sub["status"] in ("active", "trialing"):
                user.subscription_status = "active"
            elif sub["status"] in ("canceled", "unpaid", "past_due"):
                user.subscription_status = sub["status"].replace(
                    "canceled", "cancelled"
                )
                if sub["status"] == "canceled":
                    user.subscription_tier = "free"
            await db.commit()

    return {"received": True}


@router.get("/billing/status")
async def billing_status(user: User = Depends(get_current_user)):
    """Return current billing status."""
    return {
        "tier": user.subscription_tier,
        "status": user.subscription_status,
        "max_profiles": TIER_LIMITS.get(user.subscription_tier, 0),
    }
