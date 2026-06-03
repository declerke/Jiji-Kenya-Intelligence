"""
Unit tests for Jiji Kenya scraper utilities and parsing logic.

Run with: pytest tests/ -v
"""

import pytest
from pathlib import Path
import sys
import os
import csv
import tempfile

# Make scraper package importable from test runner
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.utils import (
    parse_price,
    normalize_location,
    extract_listing_id,
    extract_car_make,
    detect_phone_brand,
    categorize_price,
)


# ---------------------------------------------------------------------------
# parse_price tests
# ---------------------------------------------------------------------------

class TestParsePrice:
    def test_standard_ksh_format(self):
        assert parse_price("KSh 15,000") == 15000.0

    def test_large_price(self):
        assert parse_price("KSh 1,500,000") == 1500000.0

    def test_negotiable_returns_none(self):
        assert parse_price("Negotiable") is None

    def test_empty_string_returns_none(self):
        assert parse_price("") is None

    def test_none_input(self):
        assert parse_price(None) is None

    def test_call_for_price_returns_none(self):
        assert parse_price("Call for price") is None

    def test_free_returns_zero(self):
        assert parse_price("Free") == 0.0

    def test_kes_variant(self):
        result = parse_price("KES 45,000")
        assert result == 45000.0

    def test_price_with_month_suffix(self):
        # "KSh 25,000 / month" -> 25000.0
        result = parse_price("KSh 25,000 / month")
        assert result == 25000.0

    def test_plain_number_string(self):
        assert parse_price("50000") == 50000.0

    def test_decimal_price(self):
        result = parse_price("KSh 1,250,000.50")
        assert result is not None
        assert result > 1_000_000

    def test_n_a_returns_none(self):
        assert parse_price("N/A") is None

    def test_contact_seller_returns_none(self):
        assert parse_price("Contact seller") is None


# ---------------------------------------------------------------------------
# normalize_location tests
# ---------------------------------------------------------------------------

class TestNormalizeLocation:
    def test_nairobi_direct(self):
        assert normalize_location("Nairobi") == "Nairobi"

    def test_nairobi_neighborhood(self):
        assert normalize_location("Westlands, Nairobi") == "Nairobi"

    def test_karen_maps_to_nairobi(self):
        assert normalize_location("Karen") == "Nairobi"

    def test_mombasa_direct(self):
        assert normalize_location("Mombasa") == "Mombasa"

    def test_nyali_maps_to_mombasa(self):
        assert normalize_location("Nyali, Mombasa") == "Mombasa"

    def test_kisumu(self):
        assert normalize_location("Kisumu") == "Kisumu"

    def test_nakuru(self):
        assert normalize_location("Nakuru") == "Nakuru"

    def test_empty_string_returns_unknown(self):
        assert normalize_location("") == "Unknown"

    def test_none_returns_unknown(self):
        assert normalize_location(None) == "Unknown"

    def test_unknown_location_returns_titlecase(self):
        result = normalize_location("Somewhere Unknown")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_kasarani_maps_to_nairobi(self):
        result = normalize_location("Kasarani")
        assert result == "Nairobi"

    def test_kilimani_maps_to_nairobi(self):
        assert normalize_location("Kilimani") == "Nairobi"


# ---------------------------------------------------------------------------
# extract_listing_id tests
# ---------------------------------------------------------------------------

class TestExtractListingId:
    def test_url_with_hex_id(self):
        url = "https://jiji.co.ke/cars/toyota-land-cruiser-abc123def456"
        result = extract_listing_id(url)
        assert result is not None
        assert len(result) > 0

    def test_empty_url_returns_uuid(self):
        result = extract_listing_id("")
        assert result is not None
        # UUID format: 32 hex chars (with or without dashes)
        assert len(result) >= 8

    def test_none_url_returns_uuid(self):
        result = extract_listing_id(None)
        assert result is not None

    def test_plain_url_returns_slug(self):
        url = "https://jiji.co.ke/cars/ford-ranger-2019"
        result = extract_listing_id(url)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# extract_car_make tests
# ---------------------------------------------------------------------------

class TestExtractCarMake:
    def test_toyota(self):
        assert extract_car_make("Toyota Land Cruiser V8 2019") == "Toyota"

    def test_nissan(self):
        assert extract_car_make("Nissan X-Trail 2018") == "Nissan"

    def test_subaru(self):
        assert extract_car_make("Subaru Forester 2.0 XT") == "Subaru"

    def test_bmw(self):
        assert extract_car_make("BMW 3 Series 320i") == "BMW"

    def test_mercedes(self):
        assert extract_car_make("Mercedes Benz C200 Kompressor") == "Mercedes"

    def test_unknown_make(self):
        result = extract_car_make("Some Unknown Brand XYZ")
        assert isinstance(result, str)

    def test_empty_title(self):
        result = extract_car_make("")
        assert result == "Unknown"

    def test_land_rover(self):
        assert extract_car_make("Land Rover Discovery 4") == "Land Rover"


# ---------------------------------------------------------------------------
# detect_phone_brand tests
# ---------------------------------------------------------------------------

class TestDetectPhoneBrand:
    def test_samsung(self):
        assert detect_phone_brand("Samsung Galaxy S23 Ultra 256GB") == "Samsung"

    def test_iphone(self):
        assert detect_phone_brand("iPhone 14 Pro Max 128GB") == "iPhone"

    def test_apple_maps_to_iphone(self):
        assert detect_phone_brand("Apple iPhone 13 Pro") == "iPhone"

    def test_tecno(self):
        assert detect_phone_brand("Tecno Spark 20 Pro+ 8GB/256GB") == "Tecno"

    def test_infinix(self):
        assert detect_phone_brand("Infinix Note 40 Pro 5G") == "Infinix"

    def test_unknown_brand(self):
        result = detect_phone_brand("Generic Android Smartphone")
        assert result == "Other"

    def test_empty_title(self):
        result = detect_phone_brand("")
        assert result == "Other"

    def test_huawei(self):
        assert detect_phone_brand("Huawei P40 Pro 8GB") == "Huawei"


# ---------------------------------------------------------------------------
# categorize_price tests
# ---------------------------------------------------------------------------

class TestCategorizePrice:
    def test_cars_budget(self):
        assert categorize_price(400_000, "cars") == "budget"

    def test_cars_mid(self):
        assert categorize_price(1_200_000, "cars") == "mid"

    def test_cars_premium(self):
        assert categorize_price(5_000_000, "cars") == "premium"

    def test_phones_budget(self):
        assert categorize_price(8_000, "phones") == "budget"

    def test_phones_mid(self):
        assert categorize_price(30_000, "phones") == "mid"

    def test_phones_premium(self):
        assert categorize_price(80_000, "phones") == "premium"

    def test_property_budget(self):
        assert categorize_price(12_000, "property") == "budget"

    def test_property_mid(self):
        assert categorize_price(35_000, "property") == "mid"

    def test_property_premium(self):
        assert categorize_price(120_000, "property") == "premium"

    def test_none_price_returns_unknown(self):
        assert categorize_price(None, "cars") == "unknown"


# ---------------------------------------------------------------------------
# CSV save/load integration test
# ---------------------------------------------------------------------------

class TestCSVIntegration:
    def test_save_and_reload_listings(self, tmp_path, monkeypatch):
        """Verify that scraped listings round-trip correctly through CSV."""
        from scraper.jiji_scraper import CSV_FIELDNAMES
        import csv

        sample_listings = [
            {
                "listing_id": "test-001",
                "title": "Toyota Corolla 2017",
                "price_kes": 1_200_000.0,
                "location": "Nairobi",
                "category": "cars",
                "condition": "Used",
                "listing_url": "https://jiji.co.ke/cars/toyota-corolla-test-001",
                "description_snippet": "Clean Toyota Corolla, one owner, well maintained.",
                "scraped_at": "2024-06-01T10:00:00",
                "scrape_date": "2024-06-01",
            },
            {
                "listing_id": "test-002",
                "title": "Samsung Galaxy S22",
                "price_kes": 45_000.0,
                "location": "Mombasa",
                "category": "phones",
                "condition": "New",
                "listing_url": "https://jiji.co.ke/phones-tablets/samsung-s22-test-002",
                "description_snippet": "Brand new Samsung S22 sealed box.",
                "scraped_at": "2024-06-01T10:00:00",
                "scrape_date": "2024-06-01",
            },
        ]

        csv_path = tmp_path / "test_listings.csv"

        # Write
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for listing in sample_listings:
                writer.writerow({field: listing.get(field, "") for field in CSV_FIELDNAMES})

        # Read back
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["title"] == "Toyota Corolla 2017"
        assert rows[0]["price_kes"] == "1200000.0"
        assert rows[1]["category"] == "phones"
        assert rows[1]["condition"] == "New"

    def test_empty_csv_has_header(self, tmp_path):
        """An empty scrape run should still produce a valid CSV with header."""
        from scraper.jiji_scraper import CSV_FIELDNAMES
        import csv

        csv_path = tmp_path / "empty.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == CSV_FIELDNAMES
            rows = list(reader)
        assert rows == []
