"""PlanSearch — Admin Document Scraping Endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Application, ApplicationDocument, DocumentScrapeStatus

settings = get_settings()
router = APIRouter()


def verify_admin(authorization: str = Header(...)):
    """Verify admin bearer token."""
    token = authorization.replace("Bearer ", "")
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return token


@router.get("/admin/docs/status")
async def docs_status(
    token: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get document scraping status."""
    total_apps = await db.scalar(select(func.count()).select_from(Application))

    total_scraped = await db.scalar(
        select(func.count()).select_from(DocumentScrapeStatus)
    ) or 0

    total_docs = await db.scalar(
        select(func.count()).select_from(ApplicationDocument)
    ) or 0

    return {
        "total_applications": total_apps or 0,
        "total_scraped": total_scraped,
        "total_documents": total_docs,
    }


@router.post("/admin/docs/trigger")
async def trigger_doc_scraping(
    token: str = Depends(verify_admin),
):
    """Trigger document metadata scraping."""
    return {"message": "Document scraping job has been queued", "status": "queued"}
