# 🛒 Jiji Kenya Intelligence: Classifieds Market Analytics Pipeline

**Jiji Kenya Intelligence** is a production-grade data engineering pipeline that scrapes live listings from [Jiji.co.ke](https://jiji.co.ke) — Kenya's largest online classifieds marketplace — transforms the raw data through a DuckDB lakehouse using dbt, and surfaces market intelligence across three Evidence.dev analytics dashboards. It implements a modular **Bronze → Silver → Gold lakehouse architecture** — parallel Playwright scraping → DuckDB raw storage → dbt-duckdb transformation → Evidence.dev report serving — providing daily snapshots of used car prices, handset pricing trends, and rental property markets across Kenya's major cities.

| Metric | Value |
|--------|-------|
| Listings scraped | 143 (71 cars · 72 property) |
| Active categories | 2 (cars, rental property) |
| Airflow tasks | 7 (3 scrape → load → dbt → validate → log) |
| dbt models | 5 (1 staging · 4 marts) |
| dbt tests | 23 (all passing) |
| Pytest tests | 57 (all passing) |
| Evidence.dev pages | 3 (overview · cars · phones) |
| Cost to run | $0 — open web + local stack only |

---

## 🎯 Project Goal

Kenya's classifieds market is large, fragmented, and almost entirely unanalysed. Jiji.co.ke lists tens of thousands of used cars, second-hand phones, and rental properties daily — but there is no public price index, no historical trend data, and no structured way to answer questions like: what is the median asking price for a Toyota Premio in Nairobi? How do used phone prices compare between Mombasa and Kisumu? Which Nairobi estates command the highest rental premiums? Buyers negotiate blind, and sellers price by feel.

Jiji Kenya Intelligence builds the analytical infrastructure to answer these questions from raw HTML. The pipeline scrapes live listing pages using Playwright (with a Requests fallback for pages that do not require JavaScript), extracts structured fields — title, price, location, condition, category — from each listing, loads them into DuckDB through a raw → staging → mart transformation layer, and serves the resulting analytics via Evidence.dev — a markdown-native BI tool that compiles SQL directly into interactive dashboards. The result is a fully automated, zero-cost market intelligence pipeline that any analyst or developer can run locally with a single `docker compose up`.

---

## 🧬 System Architecture

1. **Scraping — Playwright + Requests (parallel per category)** — `jiji_scraper.py` opens each Jiji category page (cars, phones/tablets, rental property) using a shared `requests.Session` with Kenyan browser headers; falls back to Playwright Chromium for pages that require JavaScript rendering. The scraper paginates through 3 pages per category (configurable), extracts structured listing data from each advert card, strips tracking query strings from listing URLs, deduplicates by `listing_id`, and writes results to a timestamped CSV in the staging volume. A single `requests.Session` is created once per `run_scraper` call and passed through the call chain to `scrape_category → _fetch_page → _fetch_with_requests`, eliminating per-page TCP handshake overhead.

2. **Orchestration — Apache Airflow 3.0 TaskFlow API** — `jiji_pipeline.py` defines a DAG with 7 tasks using AIP-72 Task SDK imports. Three scrape tasks are generated from a single `make_scrape_task(category)` factory function using a `@task(task_id=f"scrape_{category}")` closure, eliminating copy-pasted task definitions per category. `load_to_duckdb` uses DuckDB's native `read_csv_auto()` to ingest each CSV file in a single SQL statement — replacing ~35 lines of Python CSV parsing. A `DELETE FROM raw.listings WHERE scrape_date = ? AND category = ?` before each load enables safe re-runs without cross-category data loss.

3. **DuckDB Lakehouse** — a single file-based DuckDB warehouse (`/data/jiji.duckdb`) serves as the entire analytical store. The `raw` schema holds the append-only listings table loaded from each scrape run. The `main_staging` schema holds `stg_jiji_listings` — a dbt view that casts price to DOUBLE, standardises the condition field, and validates required columns. The `main_marts` schema holds four materialised tables: `fct_listings` (full enriched fact table with price tier bucketing), `mart_cars_by_make` (car market aggregated by make), `mart_category_volume` (daily scrape volume by category), and `mart_price_by_location` (price distribution across cities). All Airflow tasks and the Evidence.dev container share the DuckDB file via a named Docker volume.

4. **dbt-duckdb Transformation Layer** — 5 models across two layers define the analytical schema. The staging layer (`stg_jiji_listings`) applies type casting and standardisation to raw inputs. The mart layer (`fct_listings`, `mart_cars_by_make`, `mart_category_volume`, `mart_price_by_location`) builds the analytical aggregates each dashboard page needs directly. 23 dbt tests covering `not_null`, `unique`, and `accepted_values` validate the complete transformation chain on every pipeline run.

5. **Evidence.dev Analytics Dashboard** — three markdown pages (`index.md`, `cars.md`, `phones.md`) define SQL queries inline against the `jiji` Evidence source, backed by the DuckDB mart tables. Evidence compiles each SQL block into a Parquet cache on startup, then serves the pages via a Vite/SvelteKit dev server. The Evidence container uses a custom `Dockerfile.evidence` that installs all dependencies at image build time (avoiding runtime `npm install` network failures), rebuilds the DuckDB native binary via `npm rebuild duckdb`, and mounts the DuckDB volume at the path Evidence's connector resolves after its internal `path.join` construction.

All 7 stages run as an **Apache Airflow 3.0 DAG** (`jiji_pipeline`) with the TaskFlow API, lazy imports inside callables to keep DAG parse time under 300s, and a task factory pattern to keep the DAG definition DRY across three scraped categories.

---

## 🛠️ Technical Stack

| **Layer** | **Tool** | **Version** |
|---|---|---|
| Orchestration | Apache Airflow (LocalExecutor, AIP-72) | 3.0 |
| Web scraping | Playwright + Requests + BeautifulSoup4 | 1.44 / 2.32 / 4.12 |
| OLAP database | DuckDB | 1.1.3 |
| Data transformation | dbt-duckdb | 1.8.1 |
| Analytics dashboard | Evidence.dev | 35 |
| Containerisation | Docker Compose (7 services) | — |
| Language | Python | 3.11 |

---

## 📊 Performance & Results

- **143 listings loaded** across 2 active categories (71 cars · 72 rental property) in a single DAG run; phones/tablets category returned 0 results due to Jiji anti-scraping protection on that category endpoint
- **Full 7-task pipeline** (3 parallel scrapes → DuckDB load → dbt run → validation → summary log) completes in approximately **1 minute 25 seconds** end-to-end
- **DuckDB native CSV ingestion** — `read_csv_auto()` inside a single `INSERT INTO ... SELECT` statement replaces ~35 lines of Python CSV parsing; load time under 1 second per category
- **dbt test suite** (23 tests across staging and mart layers) passes in under 15 seconds; all `not_null`, `unique`, and `accepted_values` constraints green on first run after DAG completes
- **57 pytest tests** covering scraper unit tests, URL normalisation, field extraction, pagination logic, and DuckDB load validation all pass in under 30 seconds
- **Evidence.dev** serves 3 interactive analytics pages at `localhost:3001`; mart tables queried via DuckDB Parquet cache with sub-second page response time

---

## 📸 Dashboard

### Overview — All Categories

![](<assets/jiji kenya intelligence.png>)

*Homepage showing total listing count, category breakdown, average price per category, and price tier distribution across all scraped listings.*

![](<assets/jiji kenya intelligence, daily scrape.png>)

*Daily scrape volume chart tracking listing counts per category over time — shows the cadence of the Airflow pipeline.*

![](<assets/jiji kenya intelligence, daily scrape, pipeline stats.png>)

*Pipeline stats panel displaying total listings, unique locations covered, and scrape date range from the mart layer.*

### Cars Market

![](<assets/cars markets.png>)

*Kenya used car market overview — total listings, median asking price (KES), new vs used split, and price distribution histogram.*

![](<assets/cars markets, top car makes.png>)

*Top car makes by listing count and median price — Toyota dominates Kenya's used car market; bar chart ranked by volume with median price overlay.*

![](<assets/cars markets, price by location.png>)

*Average and median asking prices by city — Nairobi, Mombasa, Kisumu, Nakuru, and Eldoret compared; data table with full location breakdown.*

### Airflow DAG — 7/7 Success

![](<assets/successful dag runs.png>)

*All 7 DAG tasks completing successfully: scrape_cars → scrape_phones → scrape_property → load_to_duckdb → run_dbt → validate_marts → log_summary.*

---

## 📑 Data Sources

| Source | Method | Listings | Key Fields |
|--------|--------|---------|-----------|
| [Jiji Kenya — Cars](https://jiji.co.ke/cars) | Playwright + Requests | 71 | Title, price (KES), location, condition, listing URL |
| [Jiji Kenya — Property](https://jiji.co.ke/houses-apartments-for-rent) | Playwright + Requests | 72 | Title, price (KES), location, condition, listing URL |
| [Jiji Kenya — Phones](https://jiji.co.ke/mobile-phones) | Playwright + Requests | 0 (anti-scraping) | Title, price (KES), location, condition, listing URL |

---

## 🧠 Key Design Decisions

- **Task factory pattern for scrape tasks** — the original DAG defined three nearly-identical `scrape_cars`, `scrape_phones`, `scrape_property` task functions with only the category string differing. The factory `make_scrape_task(category)` uses a `@task(task_id=f"scrape_{category}")` closure to generate all three tasks from a single definition. Adding a fourth category (electronics, services) requires one `make_scrape_task("electronics")` call — not a copy-pasted function block. This is the correct abstraction boundary: the variance between tasks is a single string parameter, not logic.

- **DuckDB `read_csv_auto()` for ingestion** — the original `load_to_duckdb` used `csv.DictReader` to iterate rows, built Python dicts, and called `connection.executemany(INSERT INTO ..., rows)` — ~35 lines of code with per-row Python overhead. `read_csv_auto(path, header=True)` is a DuckDB table function that reads the CSV file directly in C++, performs column type inference, and streams rows into the INSERT without touching Python. The rewrite reduced the load function to 8 lines and cut load time to under 1 second per CSV. `TRY_CAST` in the SELECT handles malformed price or date fields gracefully without Python-level validation.

- **Per-category DELETE instead of blanket scrape-date wipe** — the original pipeline ran `DELETE FROM raw.listings WHERE scrape_date = TODAY()` before loading any category. If cars loaded successfully but phones then failed, the re-run would re-delete all of today's successfully loaded data before re-inserting it. The per-category delete `WHERE scrape_date = ? AND category = ?` is scoped to exactly the data being replaced, making each category load idempotent and independently re-runnable without touching other categories' data.

- **Shared `requests.Session` across the scrape call chain** — the original `_fetch_with_requests` created a new `requests.Session()` on every page fetch call, opening a fresh TCP connection and performing a TLS handshake for each request. For 3 pages × 3 categories = 9 requests, this means 9 TLS handshakes where 3 would suffice. The session is now created once in `run_scraper` using a context manager (`with requests.Session() as session:`), configured with Kenyan browser headers, and passed down through `scrape_category → _fetch_page → _fetch_with_requests`. Connection reuse across pages in the same category eliminates redundant handshake latency on all subsequent pages.

- **`PYTHONPATH` environment variable instead of `sys.path.insert`** — the original DAG included `sys.path.insert(0, "/opt/airflow")` at the top of every task callable so Python could resolve `from scraper.jiji_scraper import run_scraper`. Adding `PYTHONPATH: /opt/airflow` to the `x-airflow-common` environment block in docker-compose achieves the same resolution at the Docker layer and removes the path manipulation from every task function. The correct place to configure import paths is the environment, not application code — `sys.path` manipulation belongs in scripts, not in production DAG callables.

- **Evidence.dev custom Dockerfile over runtime `npm install`** — Evidence.dev 35 requires ~20 peer dependencies that must all be present before `evidence dev` can start. Relying on `npm install` at container startup means any network interruption during the large install tree download exits the container. Building a `Dockerfile.evidence` that runs `npm install --legacy-peer-deps --ignore-scripts && npm rebuild duckdb` at image build time moves the network dependency to `docker compose build` — slow once, then cached indefinitely. The `--ignore-scripts` flag bypasses a broken TypeScript postinstall in `@evidence-dev/sdk@1.2.2`; `npm rebuild duckdb` then specifically re-runs only the DuckDB native binary download that `--ignore-scripts` skipped.

- **XCom data for category breakdown in `log_summary`** — the original `log_summary` task ran `SELECT COUNT(*) FROM raw.listings GROUP BY category` to report per-category row counts after load, requiring an additional DuckDB connection. The rewrite has `load_to_duckdb` return `{"total": n, "by_category": {"cars": 71, "property": 72}}` via XCom, and `log_summary` reads `load_result["by_category"]` directly from memory. The DB re-query is retained only for `mart_rows` — the post-dbt mart count — where a fresh query is genuinely needed to confirm what dbt materialised.

---

## 📂 Project Structure

```text
Jiji-Kenya-Intelligence/
├── dags/
│   └── jiji_pipeline.py            # Airflow DAG — 7 tasks, make_scrape_task factory, XCom log_summary
├── scraper/
│   └── jiji_scraper.py             # Playwright + Requests — shared session, 3 categories, 3 pages each
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   │   └── stg_jiji_listings.sql    # Type casts, condition standardisation, not-null guards
│   │   ├── marts/
│   │   │   ├── fct_listings.sql         # Full fact table with price_category bucketing
│   │   │   ├── mart_cars_by_make.sql    # Car market by make — count, avg/median/min/max price, rank
│   │   │   ├── mart_category_volume.sql # Daily volume by category — new/used counts, pct_new
│   │   │   └── mart_price_by_location.sql # Price distribution by city — avg/median/min/max
│   │   └── schema.yml                   # 23 dbt tests — not_null, unique, accepted_values
│   ├── dbt_project.yml
│   └── profiles.yml                # DuckDB path /data/jiji.duckdb, threads: 1
├── reports/                        # Evidence.dev project root
│   ├── pages/
│   │   ├── index.md               # Overview — category totals, price summary, daily volume, pipeline stats
│   │   ├── cars.md                # Cars market — makes, price by location, condition split, price tiers
│   │   └── phones.md              # Phones market — brand pricing, new vs used (0 rows: anti-scraping)
│   ├── sources/
│   │   └── jiji/
│   │       ├── connection.yaml    # DuckDB connector — Evidence 35 options.filename format
│   │       ├── fct_listings.sql
│   │       ├── mart_cars_by_make.sql
│   │       ├── mart_category_volume.sql
│   │       └── mart_price_by_location.sql
│   ├── evidence.plugins.yaml      # components + datasources map (Evidence 35 format)
│   └── package.json               # Evidence 35 peer deps pinned, type: module
├── tests/
│   └── test_scraper.py            # 57 pytest tests — URL parsing, field extraction, CSV output, DuckDB load
├── assets/                        # Dashboard and DAG screenshots
├── Dockerfile                     # Airflow image — Playwright, dbt-duckdb 1.8.1, duckdb 1.1.3, pytest 9
├── Dockerfile.evidence            # Evidence image — ignore-scripts install + npm rebuild duckdb
├── docker-compose.yml             # 7 services: postgres, airflow-perms, init, dag-processor,
│                                  #   scheduler, api-server (webserver), evidence-dev
├── requirements.txt               # Local dev — playwright, duckdb, dbt-duckdb, pytest, deepdiff
├── .env.example                   # JWT secret, Fernet key, internal API secret placeholders
└── .gitignore                     # .env, *.duckdb, staging/, dbt/target/, dbt/dbt_packages/
```

---

## ⚙️ Installation & Setup

### Prerequisites

- Docker Desktop (4 GB RAM recommended)
- Git

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/declerke/Jiji-Kenya-Intelligence.git
   cd Jiji-Kenya-Intelligence
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # The defaults work out of the box for local development
   ```

3. **Build and start all services**
   ```bash
   docker compose up -d
   ```
   First build installs Playwright, dbt-duckdb, and pytest inside the Airflow image and all Evidence.dev peer dependencies inside the Evidence image (~4–6 minutes).

4. **Wait for Airflow to initialise** (~2 minutes)
   ```bash
   docker compose logs -f airflow-scheduler
   # Wait until: "Scheduler started"
   ```

5. **Trigger the pipeline**
   ```bash
   docker compose exec airflow-webserver airflow dags trigger jiji_pipeline
   ```
   Or use the Airflow UI at `http://localhost:8081`. The full pipeline completes in approximately 90 seconds.

6. **Access the stack**

   | Service | URL | Credentials |
   |---------|-----|-------------|
   | Evidence.dev dashboard | http://localhost:3001 | — |
   | Airflow UI | http://localhost:8081 | admin / admin |
   | PostgreSQL (Airflow metadata) | localhost:5437 | airflow / airflow |

---

## 🗄️ dbt Models

| Model | Layer | Type | Description |
|-------|-------|------|-------------|
| `stg_jiji_listings` | Staging | View | Casts `price_kes` to DOUBLE; standardises `condition` to New/Used/Unknown; validates `listing_id` not null; filters rows with null titles |
| `fct_listings` | Mart | Table | Full enriched fact table with `price_category` bucket (Budget <50K / Mid-Range 50–200K / Premium 200–500K / Luxury 500K+) |
| `mart_cars_by_make` | Mart | Table | Car market aggregated by make — listing_count, avg/median/min/max price (KES), latest_scrape_date, rank by listing count |
| `mart_category_volume` | Mart | Table | Daily listing volume by category and scrape_date — listing_count, avg_price, new_count, used_count, pct_new |
| `mart_price_by_location` | Mart | Table | Price distribution by category and city — listing_count, avg/median/min/max price per location |

**23 dbt tests — 23/23 PASS:**
- Staging: `not_null` on `listing_id`, `title`, `category`, `scrape_date`; `unique` on `listing_id`; `accepted_values` on `condition` (New, Used, Unknown)
- Marts: `not_null` on all key metric columns; `unique` on composite grain keys; `accepted_values` on `price_category` (Budget, Mid-Range, Premium, Luxury)

---

## 🎓 Skills Demonstrated

- **Apache Airflow 3.0 DAG design** — AIP-72 Task SDK operator imports, dag-processor as a separate required service, TaskFlow API with `@dag` + `@task` decorators, task factory pattern (`make_scrape_task` closure) for DRY parallel scrape tasks across three categories, lazy imports inside callables to keep DAG parse time under 300s, XCom return values for inter-task data sharing without redundant DB queries

- **DuckDB OLAP engineering** — file-based columnar warehouse requiring no separate database service; native CSV ingestion via `read_csv_auto()` table function eliminating Python CSV parsing; `TRY_CAST` for resilient type conversion on user-generated price strings; per-category idempotent DELETE enabling independent category re-runs; `CREATE SCHEMA IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS` idempotent DDL; `read_only=True` on Evidence connections for concurrent read safety

- **Production web scraping** — dual-mode fetch with Requests primary and Playwright Chromium fallback for JavaScript-rendered pages; shared `requests.Session` context manager for connection reuse across pages per category; Kenyan browser User-Agent + Accept-Language headers; query string stripping from listing URLs; graceful handling of missing price/location fields; 3-page pagination per category

- **dbt-duckdb transformation layer** — 2-layer model architecture (staging → mart); `profiles.yml` with DuckDB path from `/data/jiji.duckdb`, `threads: 1` (DuckDB single-writer constraint); 23 data quality tests including `accepted_values` on condition and price category enums; mart tables materialised as `TABLE` type for Evidence.dev query performance

- **Evidence.dev 35 analytics** — markdown-native BI tool with inline SQL compiled to Parquet; custom `Dockerfile.evidence` with `--ignore-scripts` to bypass broken `@evidence-dev/sdk` TypeScript postinstall, followed by `npm rebuild duckdb` to restore the native binary; `evidence.plugins.yaml` manually authored with correct `components` + `datasources` map format for Evidence 35's plugin-connector schema; `sources/jiji/connection.yaml` using Evidence 35's `options.filename` nesting; dual Docker volume mount to resolve Evidence's internal `path.join(sourceDir, filename)` construction

- **Docker Compose multi-service orchestration** — 7-service stack (postgres, airflow-perms, airflow-init, dag-processor, scheduler, api-server, evidence-dev); shared `duckdb_data` named volume mounted across all Airflow containers and the Evidence container; `service_completed_successfully` dependency conditions on init containers; separate `Dockerfile` and `Dockerfile.evidence` for heterogeneous service requirements; Airflow 3.0 `api-server` command replacing the legacy `webserver`

- **Python data engineering testing** — 57 pytest tests in `test_scraper.py` covering URL normalisation (query string stripping, relative vs absolute URL handling), field extraction (price parsing, location extraction, condition standardisation), session reuse verification, pagination logic, and DuckDB load validation; `pytest-asyncio>=0.24.0` for async Playwright test compatibility with pytest 9.x

- **Security and dependency hygiene** — `pip-audit --local` scan with `--ignore-vuln GHSA-w75w-9qv4-j5xj` for the unfixable dbt-core 1.8.x CVE; `pytest>=9.0.3`, `requests>=2.32.3`, `deepdiff>=8.6.2` pinned to CVE-safe minimum versions; `.env.example` with Fernet key, JWT secret, and internal API secret placeholders; `.gitignore` covering `.duckdb` warehouse files and `staging/` CSV output
