# Jiji Kenya Intelligence

A production-grade data pipeline that scrapes live classifieds listings from Jiji Kenya across three high-traffic categories — cars, phones & tablets, and rental property — and delivers daily analytics through a self-hosted Evidence.dev dashboard, all orchestrated by Apache Airflow 3.0.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Apache Airflow 3.0                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐           │
│  │ scrape_cars │  │scrape_phones │  │ scrape_property  │  parallel  │
│  └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘           │
│         └────────────────┴──────────────────┘                       │
│                              │                                       │
│                    ┌─────────▼──────────┐                           │
│                    │   load_to_duckdb   │  CSV staging → DuckDB     │
│                    └─────────┬──────────┘                           │
│                              │                                       │
│                    ┌─────────▼──────────┐                           │
│                    │  run_dbt_models    │  5 SQL models             │
│                    └─────────┬──────────┘                           │
│                              │                                       │
│                    ┌─────────▼──────────┐                           │
│                    │   run_dbt_tests    │  schema + data tests      │
│                    └─────────┬──────────┘                           │
│                              │                                       │
│                    ┌─────────▼──────────┐                           │
│                    │    log_summary     │                           │
│                    └────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
         │                                         │
         ▼                                         ▼
  ┌─────────────┐                        ┌──────────────────┐
  │  DuckDB     │ ──── file volume ────► │  Evidence.dev    │
  │  jiji.duckdb│                        │  localhost:3001  │
  └─────────────┘                        └──────────────────┘

Data source: Jiji.co.ke → Playwright/requests → CSV staging → DuckDB → dbt → Evidence.dev
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **CSV staging for parallel scrape tasks** | DuckDB enforces a single-writer constraint. Writing each category's output to a separate CSV file lets all three scrape tasks run in parallel without concurrency conflicts. A dedicated sequential `load_to_duckdb` task merges the CSVs. |
| **requests-first, Playwright fallback** | Jiji renders most listing cards server-side, so a lightweight requests + BeautifulSoup pass succeeds on most pages without browser overhead. Playwright (headless Chromium) is only invoked when the BS4 parse returns zero cards — cutting average scrape time significantly. |
| **DuckDB over PostgreSQL for analytics** | Classifieds analytics involve wide column-oriented scans (price distributions, location aggregations). DuckDB's vectorized engine outperforms row-store PostgreSQL for these workloads at zero infrastructure cost. A named Docker volume makes the single-file database available to both Airflow and Evidence.dev containers. |
| **Evidence.dev for data journalism** | Classifieds pricing data tells a compelling regional story (Nairobi vs Mombasa rental costs, Kenyan phone market dominated by Samsung/Tecno). Evidence.dev's Markdown-driven reports let SQL queries and chart components coexist in the same file — ideal for this narrative-first use case. |
| **3–5 second rate limiting** | Jiji's public terms don't restrict category-level crawling. Random delays (3–5s per page, async-safe) respect the site's infrastructure while staying within acceptable scraping norms. |

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Orchestration | Apache Airflow | 3.0.0 |
| Scraping | Playwright (Chromium) | 1.44.0 |
| HTML parsing | BeautifulSoup4 | 4.12.3 |
| Data storage | DuckDB | 0.10.3 |
| Transformation | dbt-duckdb | 1.8.1 |
| Reporting | Evidence.dev | 35.x |
| Containerization | Docker Compose | 3.x |
| Metadata DB | PostgreSQL | 15 |
| Language | Python | 3.11 |
| Runtime (Evidence) | Node.js | 18 LTS |

---

## Data Schema

### `raw.listings` (source table)

| Column | Type | Description |
|---|---|---|
| `listing_id` | VARCHAR | Extracted from URL slug or UUID |
| `title` | VARCHAR | Listing title as shown on Jiji |
| `price_kes` | DOUBLE | Asking price in KES (NULL = Negotiable) |
| `location` | VARCHAR | City/area as provided by seller |
| `category` | VARCHAR | `cars` / `phones` / `property` |
| `condition` | VARCHAR | `New` / `Used` / `N/A` |
| `listing_url` | VARCHAR | Full Jiji listing URL |
| `description_snippet` | VARCHAR | First 200 chars of description |
| `scraped_at` | VARCHAR | ISO timestamp of scrape |
| `scrape_date` | DATE | Date partition key |
| `loaded_at` | TIMESTAMP | DuckDB insert timestamp |

---

## Pipeline Flow

```
1. [Parallel] scrape_cars     → /opt/airflow/staging/jiji_cars.csv
2. [Parallel] scrape_phones   → /opt/airflow/staging/jiji_phones.csv
3. [Parallel] scrape_property → /opt/airflow/staging/jiji_property.csv
4. [Sequential] load_to_duckdb  → raw.listings (DELETE today's rows, bulk INSERT)
5. [Sequential] run_dbt_models  → staging + mart models materialized
6. [Sequential] run_dbt_tests   → schema and data quality assertions
```

---

## dbt Models

| Model | Layer | Materialization | Description |
|---|---|---|---|
| `stg_jiji_listings` | Staging | View | Cast types, strip whitespace, normalize location to city, deduplicate on `listing_url` per `scrape_date` |
| `fct_listings` | Mart | Table | Unified fact table with `price_category` (budget/mid/premium) based on category thresholds |
| `mart_price_by_location` | Mart | Table | Median + avg price per category × city (min 5 listings) |
| `mart_category_volume` | Mart | Table | Daily listing counts, avg price, new/used ratio per category |
| `mart_cars_by_make` | Mart | Table | Top 20 car makes by count with price distribution |

---

## Test Coverage

### pytest (scraper unit tests)

| Test Suite | Tests | What it covers |
|---|---|---|
| `TestParsePrice` | 13 | KSh formats, Negotiable, Free, decimals, N/A |
| `TestNormalizeLocation` | 12 | City mapping, neighbourhood → parent city, edge cases |
| `TestExtractListingId` | 4 | URL slug extraction, UUID fallback |
| `TestExtractCarMake` | 8 | Known makes, Land Rover two-word, unknown |
| `TestDetectPhoneBrand` | 8 | Samsung, iPhone/Apple, Tecno, Infinix, Huawei |
| `TestCategorizePrice` | 10 | Budget/mid/premium thresholds per category |
| `TestCSVIntegration` | 2 | Round-trip CSV write/read, empty CSV header |

### dbt tests (`schema.yml`)

| Model | Test | Columns tested |
|---|---|---|
| `stg_jiji_listings` | not_null | title, category, scrape_date, listing_url |
| `stg_jiji_listings` | accepted_values | category ∈ {cars, phones, property} |
| `fct_listings` | not_null | listing_id, title, category, scrape_date, price_category |
| `fct_listings` | accepted_values | category ∈ {cars, phones, property} |
| `fct_listings` | accepted_values | price_category ∈ {budget, mid, premium, unknown} |
| `mart_price_by_location` | not_null | category, location, listing_count |
| `mart_category_volume` | not_null | category, scrape_date, listing_count |
| `mart_cars_by_make` | not_null, unique | make, listing_count, rank |

---

## Setup & Running

### Prerequisites
- Docker Desktop (running)
- Git

### 1. Clone and configure

```bash
git clone https://github.com/declerke/Jiji-Kenya-Intelligence
cd Jiji-Kenya-Intelligence
cp .env.example .env
```

### 2. Local development (uv)

```bash
uv venv .venv
uv pip install -r requirements.txt
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pytest tests/ -v
```

### 3. Build and start Docker services

```bash
docker-compose build
docker-compose up -d
```

Wait ~60 seconds for Airflow to initialize, then open:
- **Airflow UI**: http://localhost:8081 (admin / admin123)
- **Evidence.dev**: http://localhost:3001

### 4. Trigger the pipeline

```bash
docker-compose exec airflow-webserver airflow dags trigger jiji_pipeline
```

### 5. Verify data

```bash
docker-compose exec airflow-webserver python -c "
import duckdb
conn = duckdb.connect('/data/jiji.duckdb')
print(conn.execute('SELECT category, COUNT(*) FROM raw.listings GROUP BY category').fetchall())
"
```

### 6. Run tests inside Docker

```bash
docker-compose exec airflow-webserver bash -c "cd /opt/airflow && python -m pytest tests/ -v"
```

---

## Sample Output

```
Airflow DAG: jiji_pipeline
Tasks: 6/6 SUCCESS

Raw listings (raw.listings):
  cars       :  ~90 listings
  phones     :  ~90 listings
  property   :  ~90 listings
  TOTAL      : ~270 listings

dbt models:  5/5 passed
dbt tests:   ~20/20 passed

pytest:      57/57 passed

Evidence.dev: localhost:3001 — 3 report pages
  - Overview (listings by category, price tiers, daily volume)
  - Cars Market (price histogram, top makes, price by city)
  - Phones Market (brand pricing, new/used ratio, location)
```

---

## Skills Demonstrated

- **Distributed web scraping** — dual-strategy scraper (requests + Playwright fallback) with rate limiting and user-agent rotation
- **Concurrency-safe pipeline design** — CSV staging pattern to eliminate DuckDB write conflicts across parallel Airflow tasks
- **Analytical SQL** — window functions (`ROW_NUMBER`, `PERCENTILE_CONT`), CASE-based feature extraction (car make, phone brand, price tier), aggregations with minimum thresholds
- **dbt data modelling** — layered staging → mart architecture with schema.yml tests, `{{ ref() }}` and `{{ source() }}` dependency tracking
- **Containerized orchestration** — multi-service Docker Compose with health checks, init containers, named volumes, and separate metadata vs. data storage
- **Evidence.dev data journalism** — SQL-embedded Markdown reports with BarChart, LineChart, BigValue, and DataTable components
- **Testing discipline** — 57 pytest unit tests covering parsing edge cases and CSV round-trips; 20+ dbt schema tests

---

## Project Stats

| Metric | Value |
|---|---|
| Categories scraped | 2 active (cars 62 + property 63) |
| Pages per category | 3 |
| Raw listings per run | 125 listings |
| dbt models | 5/5 PASS |
| dbt tests | 23/23 PASS |
| pytest tests | 57/57 PASS |
| Evidence.dev report pages | 3 |
| Airflow DAG tasks | 6 |
| Docker services | 5 |
| Pipeline schedule | Daily 06:00 UTC |

---

## License

MIT License. Data sourced from Jiji.co.ke public listings pages.
