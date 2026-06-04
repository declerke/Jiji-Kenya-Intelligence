"""
Jiji Kenya Intelligence Pipeline DAG

Task flow:
  scrape_cars ──┐
  scrape_phones  ├──► load_to_duckdb ──► run_dbt_models ──► run_dbt_tests ──► log_summary
  scrape_property┘

Parallel scrape tasks write to separate CSV staging files.
load_to_duckdb reads all three CSVs sequentially (DuckDB single-writer safe).
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timedelta, date
from pathlib import Path

import duckdb
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

DUCKDB_PATH = "/data/jiji.duckdb"
DBT_DIR = "/opt/airflow/dbt"

DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
    "email_on_retry": False,
}


@dag(
    dag_id="jiji_pipeline",
    description="Scrape Jiji Kenya classifieds and build analytics via dbt + Evidence.dev",
    schedule="0 6 * * *",  # Daily at 06:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["jiji", "kenya", "e-commerce", "classifieds"],
    doc_md="""
    ## Jiji Kenya Intelligence Pipeline

    Scrapes three Jiji Kenya categories (cars, phones/tablets, rental property),
    stores raw listings in DuckDB, transforms via dbt, and serves analytics via
    Evidence.dev.

    ### Task order
    - `scrape_cars`, `scrape_phones`, `scrape_property` run **in parallel**
    - `load_to_duckdb` waits for all three scrape tasks
    - `run_dbt_models` → `run_dbt_tests` → `log_summary` run sequentially
    """,
)
def jiji_pipeline():

    def make_scrape_task(category: str) -> str:
        @task(task_id=f"scrape_{category}")
        def _scrape() -> str:
            from scraper.jiji_scraper import run_scraper
            path = run_scraper(category, pages=3)
            logger.info("scrape_%s completed: %s", category, path)
            return path
        return _scrape()

    @task(trigger_rule="none_failed")
    def load_to_duckdb(cars_csv: str, phones_csv: str, property_csv: str) -> dict:
        """
        Load all three CSV staging files into DuckDB raw.listings table.
        Uses DuckDB native read_csv_auto for efficient bulk load.
        Each category delete is scoped so a partial re-run is idempotent per category.
        """
        conn = duckdb.connect(DUCKDB_PATH)

        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw.listings (
                listing_id       VARCHAR,
                title            VARCHAR NOT NULL,
                price_kes        DOUBLE,
                location         VARCHAR,
                category         VARCHAR NOT NULL,
                condition        VARCHAR,
                listing_url      VARCHAR,
                description_snippet VARCHAR,
                scraped_at       VARCHAR,
                scrape_date      DATE NOT NULL,
                loaded_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        today = str(date.today())
        total_loaded = 0
        counts = {}

        for category, csv_path in [
            ("cars", cars_csv),
            ("phones", phones_csv),
            ("property", property_csv),
        ]:
            path = Path(csv_path)
            if not path.exists():
                logger.warning("CSV not found for %s: %s", category, csv_path)
                counts[category] = 0
                continue

            # Per-category delete — safe for partial re-runs (cars re-run won't wipe phones data)
            conn.execute(
                "DELETE FROM raw.listings WHERE scrape_date = ? AND category = ?",
                [today, category],
            )

            conn.execute(f"""
                INSERT INTO raw.listings
                    (listing_id, title, price_kes, location, category,
                     condition, listing_url, description_snippet, scraped_at, scrape_date)
                SELECT
                    listing_id,
                    title,
                    TRY_CAST(price_kes AS DOUBLE),
                    location,
                    category,
                    condition,
                    listing_url,
                    description_snippet,
                    scraped_at,
                    TRY_CAST(scrape_date AS DATE)
                FROM read_csv_auto('{csv_path}', header=True)
                WHERE title IS NOT NULL AND title != ''
            """)

            row_count = conn.execute(
                "SELECT COUNT(*) FROM raw.listings WHERE scrape_date = ? AND category = ?",
                [today, category],
            ).fetchone()[0]
            counts[category] = row_count
            total_loaded += row_count
            logger.info("Loaded %d rows for category=%s", row_count, category)

        conn.close()
        logger.info("load_to_duckdb complete: total=%d rows | breakdown=%s", total_loaded, counts)
        return {"total": total_loaded, "by_category": counts}

    @task()
    def run_dbt_models(load_result: dict) -> str:
        """Run dbt models against DuckDB."""
        logger.info("Running dbt models. Load result: %s", load_result)
        result = subprocess.run(
            ["dbt", "run", "--profiles-dir", DBT_DIR, "--project-dir", DBT_DIR],
            capture_output=True,
            text=True,
            cwd=DBT_DIR,
        )
        logger.info("dbt run stdout:\n%s", result.stdout)
        if result.returncode != 0:
            logger.error("dbt run stderr:\n%s", result.stderr)
            raise RuntimeError(f"dbt run failed with exit code {result.returncode}")
        return result.stdout

    @task()
    def run_dbt_tests(dbt_run_output: str) -> str:
        """Run dbt tests to validate transformed data."""
        result = subprocess.run(
            ["dbt", "test", "--profiles-dir", DBT_DIR, "--project-dir", DBT_DIR],
            capture_output=True,
            text=True,
            cwd=DBT_DIR,
        )
        logger.info("dbt test stdout:\n%s", result.stdout)
        if result.returncode != 0:
            logger.error("dbt test stderr:\n%s", result.stderr)
            raise RuntimeError(f"dbt test failed with exit code {result.returncode}")
        return result.stdout

    @task()
    def log_summary(load_result: dict, dbt_test_output: str) -> None:
        """Log pipeline summary statistics."""
        # Category breakdown comes from load_result XCom — no DB re-query needed.
        # Only mart_rows requires a DuckDB read (populated by dbt, not the load step).
        conn = duckdb.connect(DUCKDB_PATH)
        try:
            mart_rows = conn.execute("SELECT COUNT(*) FROM marts.fct_listings").fetchone()[0]
        except Exception:
            mart_rows = 0
        conn.close()

        logger.info("=" * 60)
        logger.info("JIJI KENYA PIPELINE SUMMARY")
        logger.info("=" * 60)
        logger.info("Raw listings loaded: %d", load_result.get("total", 0))
        for cat, count in sorted(load_result.get("by_category", {}).items()):
            logger.info("  %-12s : %d listings", cat, count)
        logger.info("Mart rows (fct_listings): %d", mart_rows)
        logger.info("=" * 60)

        passed = dbt_test_output.count("PASS")
        failed = dbt_test_output.count("FAIL")
        logger.info("dbt tests: %d passed / %d failed", passed, failed)

    # --- Wire up the DAG ---
    cars_path = make_scrape_task("cars")
    phones_path = make_scrape_task("phones")
    property_path = make_scrape_task("property")

    load_result = load_to_duckdb(
        cars_csv=cars_path,
        phones_csv=phones_path,
        property_csv=property_path,
    )

    dbt_run_out = run_dbt_models(load_result)
    dbt_test_out = run_dbt_tests(dbt_run_out)
    log_summary(load_result, dbt_test_out)


jiji_pipeline_dag = jiji_pipeline()
