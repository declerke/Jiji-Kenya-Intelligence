"""
Jiji Kenya multi-category scraper.

Strategy:
1. Fetch page with requests + extract devalued JSON from embedded script tag
   (Jiji embeds SSR data as a Pinia/devalued array in a <script> tag)
2. Decode the flat devalued array into advert objects
3. Fall back to Playwright headless Chromium if JSON extraction fails
4. Rate limiting: 3-5 second delays between pages
5. Minimum 3 pages per category
"""

import asyncio
import csv
import json
import logging
import os
import random
import re
import time
import uuid
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scraper.utils import (
    parse_price,
    normalize_location,
    extract_listing_id,
)

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

CATEGORY_URLS = {
    "cars": "https://jiji.co.ke/cars",
    "phones": "https://jiji.co.ke/phones-tablets",
    "property": "https://jiji.co.ke/houses-apartments-for-rent",
}

STAGING_DIR = Path(os.environ.get("STAGING_DIR", "/opt/airflow/staging"))
CSV_FILES = {
    "cars": STAGING_DIR / "jiji_cars.csv",
    "phones": STAGING_DIR / "jiji_phones.csv",
    "property": STAGING_DIR / "jiji_property.csv",
}

CSV_FIELDNAMES = [
    "listing_id",
    "title",
    "price_kes",
    "location",
    "category",
    "condition",
    "listing_url",
    "description_snippet",
    "scraped_at",
    "scrape_date",
]


# ---------------------------------------------------------------------------
# Devalued JSON decoder
# ---------------------------------------------------------------------------


def _resolve(val, data: list):
    """
    Recursively resolve a value in Pinia devalued format.
    Integer values are indexes into the flat data array.
    Special values: 12 = False, 32 = True, 17 = None
    """
    # Special Pinia sentinel values
    if val == 12:
        return False
    if val == 32:
        return True
    if val == 17:
        return None

    if isinstance(val, int) and 0 <= val < len(data):
        item = data[val]
        if isinstance(item, dict):
            return {k: _resolve(v, data) for k, v in item.items()}
        elif isinstance(item, list):
            # Check if it's a Pinia type marker like ["ShallowReactive", 1]
            if item and isinstance(item[0], str) and item[0] in (
                "ShallowReactive", "Reactive", "Ref", "ShallowRef", "Raw"
            ):
                if len(item) > 1:
                    return _resolve(item[1], data)
                return None
            return [_resolve(v, data) for v in item]
        else:
            return item
    return val


def _parse_devalued_adverts(html: str, category: str) -> list[dict]:
    """
    Extract listing data from Jiji's embedded Pinia devalued JSON state.
    Returns list of listing dicts.
    """
    soup = BeautifulSoup(html, "html.parser")
    scraped_at = datetime.now(timezone.utc).isoformat()
    scrape_date = date.today().isoformat()

    devalued_data = None
    for script in soup.find_all("script"):
        txt = script.get_text()
        if "adverts_list" in txt and txt.startswith("["):
            try:
                devalued_data = json.loads(txt)
                break
            except (json.JSONDecodeError, ValueError):
                continue

    if devalued_data is None:
        logger.warning("No devalued JSON found for category=%s", category)
        return []

    # Find all advert objects: dicts with both 'guid' and 'title' keys
    listings = []
    for item in devalued_data:
        if not isinstance(item, dict):
            continue
        if "guid" not in item or "title" not in item:
            continue

        try:
            advert = {k: _resolve(v, devalued_data) for k, v in item.items()}
            listing = _advert_to_listing(advert, category, scraped_at, scrape_date)
            if listing and listing.get("title"):
                listings.append(listing)
        except Exception as exc:
            logger.debug("Failed to decode advert: %s", exc)
            continue

    logger.info("Extracted %d listings from devalued JSON for category=%s", len(listings), category)
    return listings


def _advert_to_listing(advert: dict, category: str, scraped_at: str, scrape_date: str) -> Optional[dict]:
    """Convert a decoded Jiji advert dict to our standard listing schema."""

    title = advert.get("title", "")
    if not title or not isinstance(title, str):
        return None

    # Price
    price_kes = None
    price_obj = advert.get("price_obj") or {}
    if isinstance(price_obj, dict):
        raw_price = price_obj.get("value")
        if raw_price is not None:
            try:
                price_kes = float(raw_price)
            except (TypeError, ValueError):
                price_view = price_obj.get("view", "")
                price_kes = parse_price(str(price_view)) if price_view else None

    # Location
    location = normalize_location(
        advert.get("region_name") or advert.get("region_parent_name") or ""
    )

    # URL
    rel_url = advert.get("url", "")
    if isinstance(rel_url, str) and rel_url.startswith("/"):
        listing_url = f"https://jiji.co.ke{rel_url.split('?')[0]}"
    elif isinstance(rel_url, str) and rel_url.startswith("http"):
        listing_url = rel_url.split("?")[0]
    else:
        listing_url = ""

    # Listing ID from slug or GUID
    listing_id = advert.get("guid") or advert.get("slug") or extract_listing_id(listing_url) or str(uuid.uuid4())

    # Condition
    condition = "N/A"
    attrs = advert.get("attrs") or []
    if isinstance(attrs, list):
        for attr in attrs:
            if isinstance(attr, dict):
                val = str(attr.get("value", "")).lower()
                if val in ("new", "used"):
                    condition = val.title()
                    break

    # Description
    description_snippet = ""
    desc = advert.get("short_description") or advert.get("description") or ""
    if desc and isinstance(desc, str):
        description_snippet = desc[:200]

    return {
        "listing_id": str(listing_id),
        "title": title.strip(),
        "price_kes": price_kes,
        "location": location,
        "category": category,
        "condition": condition,
        "listing_url": listing_url,
        "description_snippet": description_snippet,
        "scraped_at": scraped_at,
        "scrape_date": scrape_date,
    }


# ---------------------------------------------------------------------------
# requests-based fetching
# ---------------------------------------------------------------------------


def _fetch_with_requests(url: str, session: requests.Session) -> Optional[str]:
    """Fetch URL using an existing requests session and return raw HTML or None."""
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.warning("requests fetch failed for %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Playwright-based fallback
# ---------------------------------------------------------------------------


async def _fetch_with_playwright(url: str) -> Optional[str]:
    """
    Fetch rendered page HTML using Playwright headless Chromium.
    Returns raw HTML string or None on failure.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = await context.new_page()

            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf}",
                lambda route: route.abort(),
            )

            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            try:
                await page.wait_for_selector(
                    '[data-qa="advert-list-item"], article, script',
                    timeout=8_000,
                )
            except Exception:
                logger.warning("Selector wait timed out for %s", url)

            html = await page.content()
            await browser.close()
            return html

    except Exception as exc:
        logger.error("Playwright fetch failed for %s: %s", url, exc)
        return None


def _fetch_page(url: str, session: requests.Session) -> Optional[str]:
    """
    Try requests first; fall back to Playwright if devalued JSON is missing.
    Returns raw HTML string.
    """
    html = _fetch_with_requests(url, session)

    if html and "adverts_list" in html:
        logger.info("requests fetch with devalued JSON succeeded for %s", url)
        return html

    logger.info("No adverts_list in requests response for %s — trying Playwright", url)
    pw_html = asyncio.run(_fetch_with_playwright(url))
    if pw_html and "adverts_list" in pw_html:
        return pw_html

    # Last resort: return whatever requests got (may yield 0 listings)
    return html or pw_html


# ---------------------------------------------------------------------------
# Main scraping entry point
# ---------------------------------------------------------------------------


def scrape_category(
    category: str,
    pages: int = 3,
    session: Optional[requests.Session] = None,
) -> list[dict]:
    """
    Scrape a Jiji Kenya category across multiple pages.

    Args:
        category: One of 'cars', 'phones', 'property'
        pages: Number of pages to scrape (minimum 3)
        session: Optional shared requests.Session; creates one if not provided.

    Returns:
        List of listing dicts
    """
    if category not in CATEGORY_URLS:
        raise ValueError(f"Unknown category: {category}. Choose from {list(CATEGORY_URLS)}")

    base_url = CATEGORY_URLS[category]
    pages = max(pages, 3)
    all_listings: list[dict] = []
    seen_ids: set[str] = set()

    _session = session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)

    for page_num in range(1, pages + 1):
        url = base_url if page_num == 1 else f"{base_url}?page={page_num}"

        logger.info("Scraping %s page %d: %s", category, page_num, url)

        html = _fetch_page(url, _session)

        if html is None:
            logger.warning("Failed to fetch page %d for %s — skipping", page_num, category)
        else:
            page_listings = _parse_devalued_adverts(html, category)

            # Deduplicate by listing_id
            new_count = 0
            for listing in page_listings:
                lid = listing.get("listing_id", "")
                if lid and lid in seen_ids:
                    continue
                seen_ids.add(lid)
                all_listings.append(listing)
                new_count += 1

            logger.info(
                "Page %d: %d new listings (total so far: %d)",
                page_num,
                new_count,
                len(all_listings),
            )

        if page_num < pages:
            delay = random.uniform(3, 5)
            logger.info("Waiting %.1fs before next page...", delay)
            time.sleep(delay)

    logger.info(
        "Scraping complete for %s: %d total listings across %d pages",
        category,
        len(all_listings),
        pages,
    )
    return all_listings


def save_to_csv(listings: list[dict], category: str) -> Path:
    """
    Save scraped listings to the staging CSV file for this category.
    Creates staging directory if it doesn't exist.
    Overwrites any existing file from a previous run.

    Returns the path to the written CSV file.
    """
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CSV_FILES[category]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for listing in listings:
            row = {field: listing.get(field, "") for field in CSV_FIELDNAMES}
            writer.writerow(row)

    logger.info("Saved %d listings to %s", len(listings), output_path)
    return output_path


def run_scraper(category: str, pages: int = 3) -> str:
    """
    Full scrape-and-save pipeline for one category.
    Called by Airflow task functions.

    Returns path to the output CSV as a string.
    """
    with requests.Session() as session:
        session.headers.update(HEADERS)
        listings = scrape_category(category, pages=pages, session=session)

    if not listings:
        logger.warning("No listings scraped for %s — writing empty CSV", category)
        save_to_csv([], category)
    else:
        save_to_csv(listings, category)

    return str(CSV_FILES[category])
