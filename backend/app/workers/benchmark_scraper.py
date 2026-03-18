"""PlanSearch — Mitchell McDermott InfoCard Benchmark Scraper.

Downloads Mitchell McDermott's publicly available construction cost PDFs,
sends them to Claude for structured data extraction, and stores the
resulting benchmarks in the cost_benchmarks table.

Mitchell McDermott InfoCards: https://mitchellmcdermott.com/infocards/
Published annually in January. PDFs are publicly accessible without login.

Attribution: All cost estimates shown in PlanSearch are sourced from
Mitchell McDermott (https://mitchellmcdermott.com/infocards/).
"""

import base64
import json
import logging
from datetime import date, datetime
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

MM_INFOCARDS_URL = "https://mitchellmcdermott.com/infocards/"

# PDFs to fetch — update year in URLs each January
INFOCARD_PDFS = [
    {
        "name": "Market InfoCard 2026",
        "url": "https://mitchellmcdermott.com/wp-content/uploads/2026/01/Market-InfoCard-2026.pdf",
        "building_types": [
            "residential_new_build", "hotel_accommodation",
            "commercial_office", "industrial_warehouse",
            "student_accommodation", "data_centre",
        ],
    },
    {
        "name": "Residential InfoCard 2026",
        "url": "https://mitchellmcdermott.com/wp-content/uploads/2026/01/Residential-Info-Card-2026.pdf",
        "building_types": ["residential_new_build", "residential_extension"],
    },
    {
        "name": "Inflation (Apartments) InfoCard 2026",
        "url": "https://mitchellmcdermott.com/wp-content/uploads/2026/01/Inflation-Apartments-Infocard-2026.pdf",
        "building_types": ["residential_new_build"],
    },
    {
        "name": "Hotel InfoCard 2026",
        "url": "https://mitchellmcdermott.com/wp-content/uploads/2026/01/Hotel-Infocard-2026.pdf",
        "building_types": ["hotel_accommodation"],
    },
    {
        "name": "Industrial & Logistics InfoCard 2026",
        "url": "https://mitchellmcdermott.com/wp-content/uploads/2026/01/Industrial-Logistics-Infocard-2026.pdf",
        "building_types": ["industrial_warehouse"],
    },
    {
        "name": "Data Centres InfoCard 2026",
        "url": "https://mitchellmcdermott.com/wp-content/uploads/2026/01/Data-Centres-Infocard-2026.pdf",
        "building_types": ["data_centre"],
    },
]

EXTRACTION_PROMPT = """
You are extracting structured construction cost data from a Mitchell McDermott InfoCard PDF.

Mitchell McDermott are a leading Irish quantity surveying and construction consultancy.
Their InfoCards are published annually and contain benchmark construction costs for Ireland.

Extract ALL construction cost benchmarks visible in this PDF. For each building type found:

1. The building type (apartments, houses, hotels, offices, industrial, student accommodation, data centres, etc.)
2. Construction cost per square metre (low and high range if given, in euros)
3. Construction cost per unit where applicable (per apartment, per hotel key, etc.)
4. The date/year these costs apply to
5. The overall inflation rate mentioned (e.g. 2% for 2025)
6. What IS included in these costs
7. What is explicitly EXCLUDED from these costs (this is critical — MM always list exclusions)
8. Any important notes or caveats

The exclusions list is very important. Mitchell McDermott consistently exclude items such as:
VAT, site acquisition, planning fees, development contributions, professional fees,
finance costs, site works, sprinklers, marketing costs, etc.

Respond ONLY with valid JSON in this exact format:
{
  "infocard_name": "Market InfoCard 2026",
  "valid_from": "2026-01-01",
  "inflation_rate": 0.02,
  "benchmarks": [
    {
      "building_type": "apartments_private_mid_rise",
      "display_name": "Private Apartments (Mid-Rise Suburban)",
      "cost_per_sqm_low": 3200,
      "cost_per_sqm_high": 3800,
      "cost_per_unit_low": 280000,
      "cost_per_unit_high": 340000,
      "cost_basis": "both",
      "notes": "Assumed built on grade, medium-rise suburban location"
    }
  ],
  "inclusions": ["Construction costs", "Main contractor costs", "Preliminaries", "Contractor margin"],
  "exclusions": [
    "VAT", "Site acquisition", "Planning and statutory fees",
    "Development contributions", "Professional fees", "Finance costs",
    "Site works", "Sprinklers", "Marketing"
  ],
  "general_notes": "Costs are for construction only."
}

If you cannot find costs for a particular building type, omit it from the benchmarks array.
Be conservative — only extract figures that are clearly stated in the PDF.
"""

BUILDING_TYPE_MAPPING = {
    "apartments_private": "residential_new_build",
    "apartments_social": "residential_new_build",
    "apartments_private_mid_rise": "residential_new_build",
    "apartments_private_high_rise": "residential_new_build",
    "houses": "residential_new_build",
    "hotel": "hotel_accommodation",
    "hostel": "hotel_accommodation",
    "office": "commercial_office",
    "industrial": "industrial_warehouse",
    "logistics": "industrial_warehouse",
    "student_accommodation": "student_accommodation",
    "data_centre": "data_centre",
    "retail": "commercial_retail",
}


async def download_pdf_as_base64(url: str) -> Optional[str]:
    """Download a PDF and return as base64 string."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PlanSearch/1.0; +https://plansearch.cc)",
    }
    try:
        async with httpx.AsyncClient(
            headers=headers, follow_redirects=True, timeout=60.0
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return base64.standard_b64encode(response.content).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to download PDF {url}: {e}")
        return None


async def extract_benchmarks_from_pdf(
    pdf_base64: str,
    infocard_name: str,
    api_key: str,
) -> Optional[dict]:
    """Send PDF to Claude and extract structured benchmark data."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "document",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "application/pdf",
                                        "data": pdf_base64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": EXTRACTION_PROMPT,
                                },
                            ],
                        }
                    ],
                },
            )

        if resp.status_code != 200:
            logger.error(
                f"Claude API error {resp.status_code} for {infocard_name}: {resp.text[:200]}"
            )
            return None

        data = resp.json()
        raw_text = data["content"][0]["text"]

        # Strip markdown code fences
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("```").strip()

        return json.loads(clean)

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse Claude response for {infocard_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Claude extraction failed for {infocard_name}: {e}")
        return None


async def upsert_benchmarks(
    db: AsyncSession, extracted: dict, pdf_url: str
) -> int:
    """Store extracted benchmarks in the cost_benchmarks table."""
    count = 0
    valid_from = date.fromisoformat(extracted.get("valid_from", "2026-01-01"))
    inflation_rate = extracted.get("inflation_rate")
    exclusions = extracted.get("exclusions", [])
    inclusions = extracted.get("inclusions", [])
    general_notes = extracted.get("general_notes", "")
    infocard_name = extracted.get(
        "infocard_name", "Mitchell McDermott InfoCard"
    )

    for benchmark in extracted.get("benchmarks", []):
        raw_type = benchmark.get("building_type", "")
        mapped_type = BUILDING_TYPE_MAPPING.get(raw_type, raw_type)

        display_name = benchmark.get("display_name", raw_type)
        notes_text = f"{display_name}. {benchmark.get('notes', '')} {general_notes}".strip()

        values = {
            "source_name": "Mitchell McDermott",
            "source_url": MM_INFOCARDS_URL,
            "infocard_name": infocard_name,
            "infocard_pdf_url": pdf_url,
            "extracted_at": datetime.utcnow(),
            "valid_from": valid_from,
            "inflation_rate": inflation_rate,
            "building_type": mapped_type,
            "cost_per_sqm_low": benchmark.get("cost_per_sqm_low"),
            "cost_per_sqm_high": benchmark.get("cost_per_sqm_high"),
            "cost_per_unit_low": benchmark.get("cost_per_unit_low"),
            "cost_per_unit_high": benchmark.get("cost_per_unit_high"),
            "cost_basis": benchmark.get("cost_basis", "per_sqm"),
            "inclusions": inclusions,
            "exclusions": exclusions,
            "notes": notes_text,
            "raw_extracted_json": json.dumps(benchmark),
        }

        try:
            await db.execute(text("SAVEPOINT benchmark_upsert"))

            cols = list(values.keys())
            placeholders = [f":{k}" for k in cols]
            sql = text(f"""
                INSERT INTO cost_benchmarks ({', '.join(cols)})
                VALUES ({', '.join(placeholders)})
            """)
            await db.execute(sql, values)

            await db.execute(text("RELEASE SAVEPOINT benchmark_upsert"))
            count += 1
        except Exception as e:
            await db.execute(text("ROLLBACK TO SAVEPOINT benchmark_upsert"))
            logger.error(f"Error upserting benchmark {mapped_type}: {e}")
            continue

    await db.commit()
    return count


async def get_claude_key(db: AsyncSession) -> Optional[str]:
    """Get Claude API key from admin config or settings."""
    from app.models import AdminConfig
    from app.utils.crypto import decrypt_value

    result = await db.execute(
        text("SELECT value, encrypted FROM admin_config WHERE key = 'claude_api_key'")
    )
    row = result.fetchone()
    if row:
        return decrypt_value(row[0]) if row[1] else row[0]

    return getattr(settings, "claude_api_key", None)


async def run_benchmark_scrape(db: AsyncSession) -> dict:
    """Run the full Mitchell McDermott benchmark scrape pipeline.

    Downloads PDFs, sends to Claude for extraction, stores in database.
    """
    logger.info(
        "Starting Mitchell McDermott benchmark scrape — "
        "https://mitchellmcdermott.com/infocards/"
    )
    stats = {"pdfs_processed": 0, "benchmarks_extracted": 0, "errors": 0}

    api_key = await get_claude_key(db)
    if not api_key:
        logger.error("No Claude API key — cannot extract benchmarks")
        return stats

    for card in INFOCARD_PDFS:
        logger.info(f"Processing: {card['name']}")
        try:
            pdf_b64 = await download_pdf_as_base64(card["url"])
            if not pdf_b64:
                stats["errors"] += 1
                continue

            extracted = await extract_benchmarks_from_pdf(
                pdf_b64, card["name"], api_key
            )
            if not extracted:
                stats["errors"] += 1
                continue

            count = await upsert_benchmarks(db, extracted, card["url"])
            stats["pdfs_processed"] += 1
            stats["benchmarks_extracted"] += count
            logger.info(f"Extracted {count} benchmarks from {card['name']}")

        except Exception as e:
            logger.error(f"Failed to process {card['name']}: {e}")
            stats["errors"] += 1
            continue

    logger.info(f"Benchmark scrape complete: {stats}")
    return stats
