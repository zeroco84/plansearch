# PlanSearch

**Irish National Planning Intelligence Platform**

Search, classify, and explore 650,000+ planning applications across all 31 Irish local authorities — AI-classified by development type, lifecycle-tracked from submission to building completion, value-estimated using construction cost benchmarks, and enriched with Companies Registration Office data.

---

## Features

- **AI-powered search** — Claude Haiku parses natural language queries into structured intent (`"student accommodation galway"` → filters by `dev_category=student_accommodation` + `planning_authority IN (Galway City, Galway County)`)
- **National coverage** — 31 local authorities via NPAD ArcGIS integration (362k+ records), plus DCC CSV ingest
- **Spatial search** — PostGIS proximity filtering ("show me everything within 500m of this point")
- **AI classification** — Claude Haiku classifies each application into one of 15 development categories
- **AI value estimation** — construction value estimation using Mitchell McDermott InfoCard benchmarks
- **Significance scoring** — 0-100 score for commercial relevance of each application
- **9-stage lifecycle tracking** — from submission through construction to building completion, cross-referencing BCMS data
- **BCMS integration** — commencement notices, certificates of compliance, FSC/DAC applications; Building Control card on application detail pages
- **Geocoding** — OpenStreetMap Nominatim geocoder for application addresses (free, rate-limited)
- **Weekly digest** — automated significant approvals digest as RSS feed and JSON API
- **Applicant name scraping** — rate-limited scraper pulls applicant names from ePlanning and Agile Applications portals
- **CRO company enrichment** — matches company applicants against the Companies Registration Office
- **Document metadata indexing** — scrapes document listings from both the legacy Agile portal (pre-Sep 2024) and the National Planning Portal (post-Sep 2024)
- **Interactive map** — Leaflet / OpenStreetMap with colour-coded pins by decision status and lifecycle stage
- **Admin control centre** — token-protected dashboard for API key management, sync triggers, classification batches, geocoder control, and real-time progress via SSE
- **CSV export** — download filtered search results as CSV (up to 10,000 rows)
- **Significant page** — filterable view of high-value planning approvals sorted by estimated construction value
- **/insights section** — editorial content from The Build newsletter (via Substack RSS), AI-linked to relevant planning applications, with topic and council filtering
- **Content linking** — Claude AI extracts metadata from newsletter posts and links them to matching planning applications by reference, location, and topic
- **Contextual advertising** — privacy-first promoted cards in search results with contextual targeting by development category, council, and lifecycle stage — no tracking cookies, no surveillance
- **Substack integration** — embedded subscribe widget, UTM-tracked outbound links, and reverse integration showing "From The Build" panels on application detail pages

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | PostgreSQL 16 + PostGIS 3.4 + pg_trgm |
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Pydantic |
| Frontend | Next.js 16, TypeScript, Tailwind CSS |
| Task Queue | ARQ (Redis-backed), cron-scheduled |
| Map Tiles | Leaflet + CartoDB / OpenStreetMap |
| AI | Claude Haiku (Anthropic) — classification, search intent, value estimation, content linking |
| Geocoding | OpenStreetMap Nominatim (free, no API key) |
| Reverse Proxy | Nginx |
| Containers | Docker Compose |

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Browser  │────▶│  Nginx   │────▶│ Next.js  │
│           │     │  :80/443 │     │  :3000   │
└──────────┘     └────┬─────┘     └──────────┘
                      │
                      ▼
              ┌──────────────┐
              │   FastAPI    │
              │   :8000      │
              └──────┬───────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
    ┌──────────┐ ┌──────┐ ┌──────────┐
    │PostgreSQL│ │Redis │ │Background│
    │ +PostGIS │ │      │ │ Workers  │
    └──────────┘ └──────┘ └──────────┘
```

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/zeroco84/plansearch.git
cd plansearch
cp .env.example .env
```

Edit `.env` — set strong passwords and generate a Fernet encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Start all services

```bash
docker compose up -d
```

### 3. Initialise the database

```bash
docker exec -i plansearch-postgres-1 psql -U plansearch -d plansearch < scripts/init_schema.sql
```

### 4. Run the initial data ingest

```bash
# Test with 1,000 rows first
docker exec plansearch-backend-1 python -c "
import asyncio
from app.workers.ingest import run_ingest
from app.database import async_session_factory

async def main():
    async with async_session_factory() as db:
        stats = await run_ingest(db, limit=1000)
        print(stats)

asyncio.run(main())
"
```

Once validated, run without the `limit` param to ingest all ~200k records.

### 5. Access the application

| URL | Purpose |
|-----|---------|
| `http://localhost` | Frontend (via Nginx) |
| `http://localhost:8000/docs` | FastAPI Swagger UI |
| `http://localhost/admin` | Admin dashboard (requires `ADMIN_TOKEN` from `.env`) |
| `http://localhost/map` | Map view |
| `http://localhost/insights` | The Build newsletter + linked applications |

## Project Structure

```
plansearch/
├── backend/
│   ├── app/
│   │   ├── api/routes/            # FastAPI endpoints
│   │   │   ├── search.py          #   GET  /api/search (AI intent parsing)
│   │   │   ├── applications.py    #   GET  /api/applications/{ref}
│   │   │   ├── map.py             #   GET  /api/map/points
│   │   │   ├── stats.py           #   GET  /api/stats
│   │   │   ├── export.py          #   GET  /api/export/csv
│   │   │   ├── admin.py           #   POST /api/admin/*
│   │   │   └── docs.py            #   GET  /api/admin/docs/*
│   │   ├── workers/               # Background job workers
│   │   │   ├── npad_ingest.py     #   National NPAD ArcGIS ingest
│   │   │   ├── bcms_ingest.py     #   BCMS commencement notices + FSC
│   │   │   ├── ingest.py          #   DCC CSV ingest (4 files)
│   │   │   ├── applicant_scraper.py #  Applicant name scraper
│   │   │   ├── classifier.py      #   Claude AI classifier
│   │   │   ├── value_estimator.py #   Construction value estimation
│   │   │   ├── geocoder.py        #   OSM Nominatim geocoder
│   │   │   ├── cro.py             #   CRO company enrichment
│   │   │   ├── benchmark_scraper.py # Mitchell McDermott benchmark scraper
│   │   │   ├── content_linker.py  #   AI content-to-application linking
│   │   │   ├── substack_ingest.py #   Substack RSS feed ingest
│   │   │   ├── doc_scraper.py     #   Document metadata scraper
│   │   │   ├── summariser.py      #   AI proposal summary generator
│   │   │   └── scheduler.py       #   ARQ cron scheduler
│   │   ├── utils/                 # Shared utilities
│   │   │   ├── crypto.py          #   Fernet encrypt/decrypt
│   │   │   ├── itm_to_wgs84.py   #   ITM → WGS84 conversion
│   │   │   └── text_clean.py      #   Text normalisation
│   │   ├── config.py              # Pydantic settings
│   │   ├── database.py            # Async SQLAlchemy engine
│   │   ├── models.py              # ORM models
│   │   ├── schemas.py             # Pydantic request/response
│   │   └── main.py                # FastAPI entrypoint + startup sync
│   ├── alembic/                   # Database migrations
│   ├── tests/                     # pytest test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                   # Next.js App Router pages
│   │   │   ├── page.tsx           #   Search page (AI intent + filters)
│   │   │   ├── application/       #   Application detail
│   │   │   ├── map/               #   Map view
│   │   │   ├── insights/          #   The Build newsletter
│   │   │   ├── significant/       #   High-value approvals
│   │   │   └── admin/             #   Admin (sync/classify/keys/logs/geocoder)
│   │   ├── components/            # Shared React components
│   │   │   └── PromotedCard.tsx   #   Contextual advertising card
│   │   ├── lib/api.ts             # API client & TypeScript types
│   │   └── types/                 # Type declarations
│   ├── Dockerfile
│   └── package.json
├── nginx/nginx.conf               # Reverse proxy + SSE config
├── scripts/
│   ├── init_schema.sql            # Full PostgreSQL schema
│   ├── backup.sh                  # Daily pg_dump (7-day retention)
│   └── restore.sh                 # Restore from backup
├── docker-compose.yml
├── .env.example
└── README.md
```

## AI-Powered Search

When a user searches, the query is sent to Claude Haiku to extract structured intent:

```
User types: "student accommodation galway"
    ↓
Claude Haiku (5s timeout) extracts:
    {
      "dev_category": "student_accommodation",
      "planning_authorities": ["Galway City Council", "Galway County Council"],
      "keywords": null,
      "decision": null
    }
    ↓
SQL: WHERE dev_category = 'student_accommodation'
     AND planning_authority IN ('Galway City Council', 'Galway County Council')
    ↓
Returns only student accommodation in Galway ✓
```

**How it composes with manual filters:**
- Manual filter params (`?category=`, `?authority=`, `?decision=`) override AI intent
- Only remaining keywords go through full-text search (`plainto_tsquery`)
- Falls back to text-based location parsing if AI is unavailable (5s timeout)
- Intent chips displayed below the search bar show what the AI understood

## API Reference

### Public Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search` | GET | AI-powered search with structured filtering |
| `/api/applications/{reg_ref}` | GET | Full application detail with BCMS, company, docs |
| `/api/map/points` | GET | GeoJSON FeatureCollection for map pins |
| `/api/stats` | GET | Platform-wide statistics |
| `/api/export/csv` | GET | CSV export of filtered results (max 10k rows) |
| `/api/health` | GET | Health check |

### Admin Endpoints

All admin endpoints require `Authorization: Bearer <ADMIN_TOKEN>` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/config` | GET/POST | View/update config key–value pairs |
| `/api/admin/keys/claude` | POST | Update Claude API key (encrypted) |
| `/api/admin/keys/cro` | POST | Update CRO API key (encrypted) |
| `/api/admin/sync/npad` | POST | Trigger NPAD national data sync |
| `/api/admin/sync/bcms` | POST | Trigger BCMS commencement notices sync |
| `/api/admin/sync/substack` | POST | Trigger Substack RSS feed sync |
| `/api/admin/sync/progress` | GET | Real-time sync progress |
| `/api/admin/sync/stop` | POST | Stop running sync |
| `/api/admin/sync/status` | GET | Last sync status |
| `/api/admin/classify/trigger` | POST | Trigger AI classification batch |
| `/api/admin/classify/status` | GET | Classification progress |
| `/api/admin/estimate-values` | POST | Trigger value estimation |
| `/api/admin/logs` | GET | System operation logs |
| `/api/admin/stream` | GET | SSE live progress stream |

### Search Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Natural language search query (AI-parsed) |
| `category` | string | Development category filter (overrides AI) |
| `decision` | string | Decision status filter (overrides AI) |
| `authority` | string | Planning authority filter (overrides AI) |
| `applicant` | string | Fuzzy applicant name search |
| `location` | string | Fuzzy location search |
| `year_from` | int | Minimum year |
| `year_to` | int | Maximum year |
| `lat` | float | Latitude for proximity search |
| `lng` | float | Longitude for proximity search |
| `radius_m` | int | Search radius in metres |
| `lifecycle_stage` | string | Lifecycle stage filter |
| `value_min` | int | Minimum estimated value (€) |
| `value_max` | int | Maximum estimated value (€) |
| `sort` | string | `date_desc` · `date_asc` · `relevance` · `value_desc` · `significance` |
| `page` | int | Page number (1-indexed) |
| `page_size` | int | Results per page (max 100) |

## AI Classification Taxonomy

15 categories, classified automatically by Claude Haiku from the proposal text:

| Key | Label | Signal Keywords |
|-----|-------|-----------------| 
| `residential_new_build` | New Residential | dwelling, apartment, houses |
| `residential_extension` | Extension / Renovation | extension, attic, dormer |
| `residential_conversion` | Residential Conversion | conversion to, bedsits |
| `hotel_accommodation` | Hotel & Accommodation | hotel, hostel, B&B |
| `student_accommodation` | Student Accommodation | student, PBSA, campus |
| `commercial_retail` | Retail & Food | shop, restaurant, café, pub, takeaway |
| `commercial_office` | Office | office, co-working, headquarters |
| `industrial_warehouse` | Industrial / Warehouse | warehouse, data centre, factory |
| `mixed_use` | Mixed Use | mixed use, ground floor retail |
| `protected_structure` | Protected Structure | conservation, RPS |
| `telecommunications` | Telecoms | antenna, mast, 5G |
| `renewable_energy` | Renewable Energy | solar, wind turbine, EV charging |
| `signage` | Signage | advertisement, sign, hoarding |
| `change_of_use` | Change of Use | change of use, formerly |
| `demolition` | Demolition | demolition, clearance |
| `other` | Other | Everything else |

## Value Estimation

Construction values are estimated using Mitchell McDermott InfoCard benchmarks:

- Maps `dev_category` to the most appropriate benchmark building type
- Calculates low/high cost range based on `floor_area` or `num_residential_units`
- Displayed as green chips on search cards: `€2.1m–€3.4m`
- Full breakdown on application detail page with attribution
- **Construction cost only** — excludes VAT, site acquisition, professional fees, and finance

## BCMS Integration

Building Control Management System data enriches the planning lifecycle:

| Dataset | Records | Join Strategy |
|---------|---------|---------------|
| Commencement Notices | ~100k | `LocalAuthority` → authority code prefix → prefixed `reg_ref` match |
| FSC/DAC Applications | ~50k | Direct planning ref match |

- **Building Control card** on application detail pages shows commencement date, compliance certificate, dwelling units, floor area
- **Lifecycle stage updates**: `under_construction` (CN filed), `complete` (CCC validated), `fsc_filed` (FSC submitted)

## Document Strategy

The platform handles documents from **two separate planning portals**:

| Era | Portal | Notes |
|-----|--------|-------|
| Pre-Sep 2024 | `planning.agileapplications.ie` | Legacy Agile portal, 15+ years of archive |
| Post-Sep 2024 | `planning.localgov.ie` | National Planning Portal, all new applications |

Three rendering states on the application detail page:
1. **Not yet scraped** → "View on portal →" deep link (works from day one)
2. **Scraped, 0 documents** → "No documents available"
3. **Scraped, N documents** → Rich document panel with download links

## Testing

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Tests cover:
- Health check, search (5 variants), application detail, map, stats, CSV export
- Admin authentication (missing token, wrong token)
- ITM → WGS84 coordinate conversion
- Text cleaning and address normalisation
- Fernet encryption round-trip and key masking
- CSV row parsing, year detection from REG_REF
- Classification prompt building and response parsing
- Scraper off-peak hour validation
- Category label completeness

## Security

- **API key encryption** — Claude & CRO keys stored in PostgreSQL `admin_config`, encrypted with Fernet (AES-128-CBC + HMAC-SHA256). Keys never logged or returned in API responses.
- **Master encryption key** — stored only as a server environment variable, never in code or database.
- **Admin authentication** — bearer token on all `/api/admin/*` endpoints. Token stored as environment variable.
- **HTTPS** — enforced via Nginx + Let's Encrypt. Token never transmitted in plain text.
- **Scraper ethics** — rate-limited (1 req / 3–4 seconds), identified User-Agent (`PlanSearch/1.0`), off-peak hours only (8pm–8am), respects 429 responses with 1-hour backoff.
- **Geocoding ethics** — OSM Nominatim rate-limited to 1 req/second per their usage policy.

## Deployment

### Production (Coolify on Hetzner)

The application is deployed via Coolify with automatic builds from GitHub pushes to `main`.

| Service | Domain |
|---------|--------|
| Frontend (Next.js) | `plansearch.cc` |
| Backend (FastAPI) | `api.plansearch.cc` |

### Environment Variables

```bash
# .env (server only — never commit)
DB_PASSWORD=<strong-random-password>
MASTER_ENCRYPTION_KEY=<fernet-key>
ADMIN_TOKEN=<strong-random-token>

# Claude & CRO API keys are stored in the DATABASE
# encrypted with MASTER_ENCRYPTION_KEY — managed via admin UI
```

### Background Workers (auto-started)

| Worker | Schedule |
|--------|----------|
| NPAD sync | On-demand via admin UI |
| BCMS sync | On-demand via admin UI |
| Substack sync | On startup + every 6 hours |
| Applicant scraper | Continuous (1 req / 4s, off-peak) |
| Geocoder | Continuous (1 req / 1.1s) |
| Classifier | On-demand via admin UI |
| Value estimator | On-demand via admin UI |

## Data Sources

| Source | Data | Method |
|--------|------|--------|
| NPAD (National Planning Applications Database) | 362k+ applications, 31 authorities | ArcGIS REST API |
| Dublin City Council Open Data | 4 CSV files (base, spatial, appeals, further info) | HTTP download |
| BCMS (Building Control Management System) | Commencement notices + FSC/DAC | CSV from data.nbco.gov.ie |
| ePlanning / Agile Applications Portal | Applicant names | Rate-limited HTML scraper |
| National Planning Portal | New applications (Sep 2024+) | Document metadata scraper |
| Companies Registration Office | Company data | REST API |
| OpenStreetMap Nominatim | Geocoding (address → lat/lng) | Free API (1 req/s) |
| Mitchell McDermott InfoCards | Construction cost benchmarks | Web scraper |
| The Build (Substack) | Newsletter content | RSS feed |
| Anthropic Claude | Classification, search intent, summaries, content linking | Haiku API |

## Licence

Planning data sourced from Irish government open data under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Construction cost benchmarks attributed to [Mitchell McDermott InfoCards](https://mitchellmcdermott.com/infocards/).
