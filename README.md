# PlanSearch — Dublin Planning Intelligence Platform

A modern, searchable database of all Dublin City Council planning applications. AI-classified by development type, enriched with Companies Registration Office data, and linked to public documents.

## Features

- **Full-text search** — tsvector-powered instant search across 200,000+ planning applications
- **Spatial search** — PostGIS proximity filtering ("show me applications within 500m of this point")
- **AI classification** — Claude Haiku classifies applications into 14 development categories (residential, commercial, hotel, etc.)
- **Applicant name scraping** — rate-limited scraper extracts applicant names from the Agile Applications portal
- **CRO company enrichment** — matches company applicants against the Companies Registration Office registry
- **Document metadata** — scrapes and indexes document listings from both planning portals
- **Map view** — Leaflet/OpenStreetMap with colour-coded pins by decision status
- **Admin dashboard** — token-protected control centre for API key management, sync triggers, and progress monitoring
- **CSV export** — download filtered search results in CSV format

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Backend | FastAPI (Python 3.12, async) |
| Frontend | Next.js 16 + TypeScript + Tailwind CSS |
| Task Queue | ARQ (Redis-backed) |
| Reverse Proxy | Nginx |
| Map | Leaflet + OpenStreetMap / CartoDB |
| AI | Claude Haiku (Anthropic) |
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
    │PostgreSQL│ │Redis │ │ARQ Worker│
    │+PostGIS  │ │      │ │cron jobs │
    └──────────┘ └──────┘ └──────────┘
```

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd plansearch
cp .env.example .env
# Edit .env — set strong passwords and a Fernet encryption key:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
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
# Test with 1000 rows first
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

### 5. Access the application

- **Frontend**: http://localhost (via Nginx)
- **API docs**: http://localhost:8000/docs (FastAPI Swagger)
- **Admin**: http://localhost/admin (use `ADMIN_TOKEN` from `.env`)

## Project Structure

```
plansearch/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI endpoints
│   │   │   ├── search.py        # GET /api/search
│   │   │   ├── applications.py  # GET /api/applications/{ref}
│   │   │   ├── map.py           # GET /api/map/points
│   │   │   ├── stats.py         # GET /api/stats
│   │   │   ├── admin.py         # POST /api/admin/*
│   │   │   └── export.py        # GET /api/export/csv
│   │   ├── workers/             # Background job workers
│   │   │   ├── ingest.py        # DCC CSV data ingest
│   │   │   ├── scraper.py       # Applicant name scraper
│   │   │   ├── classifier.py    # Claude AI classifier
│   │   │   ├── cro.py           # CRO company enrichment
│   │   │   ├── doc_scraper.py   # Document metadata scraper
│   │   │   └── scheduler.py     # ARQ cron scheduler
│   │   ├── utils/               # Shared utilities
│   │   ├── config.py            # Pydantic settings
│   │   ├── database.py          # Async SQLAlchemy setup
│   │   ├── models.py            # ORM models
│   │   ├── schemas.py           # Pydantic schemas
│   │   └── main.py              # FastAPI entrypoint
│   ├── alembic/                 # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   │   ├── page.tsx         # Main search page
│   │   │   ├── application/     # Application detail
│   │   │   ├── map/             # Map view
│   │   │   └── admin/           # Admin dashboard
│   │   ├── lib/api.ts           # API client & types
│   │   └── types/               # TypeScript declarations
│   ├── Dockerfile
│   └── package.json
├── nginx/nginx.conf             # Reverse proxy config
├── scripts/
│   ├── init_schema.sql          # PostgreSQL schema
│   ├── backup.sh                # Daily backup script
│   └── restore.sh               # Restore from backup
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Reference

### Public Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search` | GET | Full-text, fuzzy, and spatial search |
| `/api/applications/{reg_ref}` | GET | Full application detail |
| `/api/map/points` | GET | GeoJSON FeatureCollection |
| `/api/stats` | GET | Platform-wide statistics |
| `/api/export/csv` | GET | CSV export of filtered results |
| `/api/health` | GET | Health check |

### Admin Endpoints (Bearer token required)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/config` | GET/POST | Config key management |
| `/api/admin/keys/claude` | POST | Update Claude API key |
| `/api/admin/keys/cro` | POST | Update CRO API key |
| `/api/admin/sync/trigger` | POST | Trigger DCC data sync |
| `/api/admin/sync/status` | GET | Sync status |
| `/api/admin/classify/trigger` | POST | Trigger AI classification |
| `/api/admin/classify/status` | GET | Classification progress |
| `/api/admin/scrape/trigger` | POST | Trigger applicant scraping |
| `/api/admin/scrape/status` | GET | Scraper progress |
| `/api/admin/logs` | GET | System logs |
| `/api/admin/stream` | GET | SSE live progress |

### Search Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Full-text search query |
| `category` | string | Development category filter |
| `decision` | string | Decision status filter |
| `applicant` | string | Fuzzy applicant name search |
| `location` | string | Fuzzy location search |
| `year_from` | int | Minimum year |
| `year_to` | int | Maximum year |
| `lat` | float | Latitude for proximity search |
| `lng` | float | Longitude for proximity search |
| `radius_m` | int | Radius in metres |
| `sort` | string | `date_desc`, `date_asc`, or `relevance` |
| `page` | int | Page number (1-indexed) |
| `page_size` | int | Results per page (max 100) |

## AI Classification Taxonomy

| Category | Label | Keywords |
|----------|-------|----------|
| `residential_new_build` | New Residential | dwelling, apartment, houses |
| `residential_extension` | Extension / Renovation | extension, attic, dormer |
| `residential_conversion` | Residential Conversion | conversion, bedsits |
| `hotel_accommodation` | Hotel & Accommodation | hotel, hostel, student accommodation |
| `commercial_retail` | Retail & Food | shop, restaurant, café, pub |
| `commercial_office` | Office | office, co-working |
| `industrial_warehouse` | Industrial / Warehouse | warehouse, data centre, factory |
| `mixed_use` | Mixed Use | mixed use, ground floor retail |
| `protected_structure` | Protected Structure | conservation, RPS |
| `telecommunications` | Telecoms | antenna, mast, 5G |
| `renewable_energy` | Renewable Energy | solar, wind, EV charging |
| `signage` | Signage | advertisement, sign, hoarding |
| `change_of_use` | Change of Use | change of use, formerly |
| `demolition` | Demolition | demolition, clearance |
| `other` | Other | Everything else |

## Security

- **API Keys**: Claude and CRO API keys stored in PostgreSQL `admin_config` table, encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
- **Master Key**: Encryption key stored ONLY as server environment variable
- **Admin Auth**: Bearer token on all `/api/admin/*` endpoints
- **HTTPS**: Enforced via Nginx + Let's Encrypt
- **Scraper Ethics**: Rate-limited (1 req/3s), User-Agent identification, off-peak hours only

## Deployment

### Production (Hetzner CX32)

```bash
# 1. Set up the VPS
ssh root@your-server
apt update && apt install docker.io docker-compose-plugin

# 2. Clone and configure
git clone <repo-url>
cd plansearch
cp .env.example .env
# Edit .env with production values

# 3. Start services
docker compose up -d

# 4. Set up SSL
certbot --nginx -d yourdomain.ie

# 5. Set up daily backup
chmod +x scripts/backup.sh
echo "0 4 * * * /path/to/scripts/backup.sh" | crontab -

# 6. Set up monitoring (UptimeRobot free tier)
# Monitor: https://yourdomain.ie/api/health
```

## Data Sources

- **Dublin City Council Open Data**: 4 CSV files (base applications, spatial, appeals, further info)
- **Agile Applications Portal**: Applicant names (scraper)
- **National Planning Portal**: New applications from Sep 2024+ (LocalGov)
- **Companies Registration Office**: Company enrichment API
- **Anthropic Claude**: AI classification

## License

Data sourced from Dublin City Council under CC BY 4.0.
