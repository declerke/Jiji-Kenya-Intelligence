"""
Utility functions for parsing Jiji Kenya listing data.
Handles price parsing, location normalization, and listing ID extraction.
"""

import re
import uuid
from typing import Optional


# Known Kenyan cities for normalization
CITY_MAP = {
    "nairobi": "Nairobi",
    "mombasa": "Mombasa",
    "kisumu": "Kisumu",
    "nakuru": "Nakuru",
    "eldoret": "Eldoret",
    "thika": "Thika",
    "ruiru": "Ruiru",
    "kikuyu": "Kikuyu",
    "machakos": "Machakos",
    "meru": "Meru",
    "nyeri": "Nyeri",
    "kitale": "Kitale",
    "malindi": "Malindi",
    "garissa": "Garissa",
    "kisii": "Kisii",
    "kakamega": "Kakamega",
    "embu": "Embu",
    "athi river": "Athi River",
    "ongata rongai": "Ongata Rongai",
    "limuru": "Limuru",
    "ngong": "Ngong",
    "westlands": "Nairobi",
    "karen": "Nairobi",
    "kilimani": "Nairobi",
    "lavington": "Nairobi",
    "parklands": "Nairobi",
    "eastleigh": "Nairobi",
    "kasarani": "Nairobi",
    "embakasi": "Nairobi",
    "langata": "Nairobi",
    "south b": "Nairobi",
    "south c": "Nairobi",
    "kileleshwa": "Nairobi",
    "upperhill": "Nairobi",
    "upper hill": "Nairobi",
    "cbd": "Nairobi",
    "industrial area": "Nairobi",
    "ruaraka": "Nairobi",
    "roysambu": "Nairobi",
    "zimmerman": "Nairobi",
    "githurai": "Nairobi",
    "kayole": "Nairobi",
    "komarock": "Nairobi",
    "donholm": "Nairobi",
    "buruburu": "Nairobi",
    "umoja": "Nairobi",
    "pipeline": "Nairobi",
    "fedha": "Nairobi",
    "utawala": "Nairobi",
    "syokimau": "Nairobi",
    "kitengela": "Nairobi",
    "juja": "Thika",
    "nyali": "Mombasa",
    "bamburi": "Mombasa",
    "shanzu": "Mombasa",
    "likoni": "Mombasa",
    "diani": "Mombasa",
    "mvita": "Mombasa",
    "kisauni": "Mombasa",
}


def parse_price(raw_price: str) -> Optional[float]:
    """
    Convert Jiji price string to float.
    Examples:
        "KSh 15,000" -> 15000.0
        "KSh 1,500,000" -> 1500000.0
        "Negotiable" -> None
        "Free" -> 0.0
        "" -> None
    """
    if not raw_price or not isinstance(raw_price, str):
        return None

    price_str = raw_price.strip()

    if not price_str:
        return None

    lower = price_str.lower()
    if any(keyword in lower for keyword in ["negotiable", "neg.", "contact", "call", "n/a", "free offer"]):
        return None
    if lower == "free":
        return 0.0

    # Strip currency symbols and text
    cleaned = re.sub(r"[Kk][Ss][Hh]\.?\s*", "", price_str)
    cleaned = re.sub(r"[Kk][Ss]\.?\s*", "", cleaned)
    cleaned = re.sub(r"[Kk][Ee][Ss]\.?\s*", "", cleaned)
    cleaned = re.sub(r"[/\-].*$", "", cleaned)  # remove "/ month" suffixes
    cleaned = cleaned.replace(",", "").strip()

    # Extract numeric value
    match = re.search(r"[\d]+(?:\.\d+)?", cleaned)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None

    return None


def normalize_location(raw_location: str) -> str:
    """
    Normalize location string to city name.
    Strips area/neighborhood suffixes and maps to nearest major city.
    """
    if not raw_location or not isinstance(raw_location, str):
        return "Unknown"

    location = raw_location.strip()
    if not location:
        return "Unknown"

    lower = location.lower()

    # Direct match
    for key, city in CITY_MAP.items():
        if lower == key:
            return city

    # Substring match (location contains city name)
    for key, city in CITY_MAP.items():
        if key in lower:
            return city

    # Return first meaningful component (before comma)
    parts = location.split(",")
    if parts:
        return parts[0].strip().title()

    return location.title()


def extract_listing_id(url: str) -> str:
    """
    Extract listing ID from Jiji URL slug.
    Falls back to UUID if extraction fails.
    Example URL: https://jiji.co.ke/cars/ford-ranger-2019-abc123def456
    """
    if not url:
        return str(uuid.uuid4())

    # Jiji IDs typically appear at end of URL slug
    match = re.search(r"([a-f0-9]{8,}(?:-[a-f0-9]{4,}){0,})", url.lower())
    if match:
        return match.group(1)

    # Fall back to last path segment
    parts = url.rstrip("/").split("/")
    if parts:
        slug = parts[-1]
        if slug and len(slug) > 3:
            return slug

    return str(uuid.uuid4())


def extract_car_make(title: str) -> str:
    """
    Extract car make from listing title.
    Returns first meaningful word(s) as the make.
    """
    if not title:
        return "Unknown"

    known_makes = [
        "Toyota", "Nissan", "Mitsubishi", "Subaru", "Honda", "Mazda",
        "Isuzu", "Mercedes", "BMW", "Volkswagen", "Audi", "Ford",
        "Hyundai", "Kia", "Land Rover", "Range Rover", "Peugeot",
        "Suzuki", "Jeep", "Lexus", "Volvo", "Fiat", "Renault",
        "Chevrolet", "Dodge", "Porsche", "Jaguar", "Mini", "Alfa",
        "Ssangyong", "Tata", "Mahindra", "BYD", "Great Wall",
        "Changan", "Lifan", "JAC", "Foton", "DFSK", "Haval",
    ]

    title_upper = title.upper()
    for make in known_makes:
        if make.upper() in title_upper:
            return make

    # Fall back to first word
    words = title.strip().split()
    if words:
        return words[0].title()

    return "Unknown"


def detect_phone_brand(title: str) -> str:
    """
    Extract phone brand from listing title.
    """
    if not title:
        return "Other"

    brands = [
        "Samsung", "iPhone", "Apple", "Tecno", "Infinix", "Itel",
        "Huawei", "Xiaomi", "Redmi", "Nokia", "Motorola", "Oppo",
        "Vivo", "Realme", "OnePlus", "Google", "Sony", "LG",
        "HTC", "Lenovo", "Alcatel",
    ]

    title_lower = title.lower()
    for brand in brands:
        if brand.lower() in title_lower:
            # Normalize Apple/iPhone to one brand
            if brand in ("Apple", "iPhone"):
                return "iPhone"
            return brand

    return "Other"


def categorize_price(price: Optional[float], category: str) -> str:
    """
    Assign price tier based on category-specific thresholds.
    """
    if price is None:
        return "unknown"

    thresholds = {
        "cars": {"budget": 500_000, "mid": 2_000_000},
        "phones": {"budget": 10_000, "mid": 50_000},
        "property": {"budget": 15_000, "mid": 50_000},
    }

    cat_thresholds = thresholds.get(category, {"budget": 10_000, "mid": 100_000})

    if price <= cat_thresholds["budget"]:
        return "budget"
    elif price <= cat_thresholds["mid"]:
        return "mid"
    else:
        return "premium"
