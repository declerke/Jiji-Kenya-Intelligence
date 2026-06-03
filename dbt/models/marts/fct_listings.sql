/*
fct_listings — Unified fact table for all Jiji Kenya listing categories.

Adds:
  - price_category: budget / mid / premium based on category-specific thresholds
  - price_category thresholds:
      cars:     budget <= 500,000 | mid <= 2,000,000 | premium > 2,000,000
      phones:   budget <= 10,000  | mid <= 50,000    | premium > 50,000
      property: budget <= 15,000  | mid <= 50,000    | premium > 50,000  (monthly rent KES)
*/

SELECT
    listing_id,
    title,
    price_kes,
    location,
    category,
    condition,
    listing_url,
    description_snippet,
    scraped_at,
    scrape_date,

    CASE
        WHEN price_kes IS NULL THEN 'unknown'
        WHEN category = 'cars' THEN
            CASE
                WHEN price_kes <= 500000    THEN 'budget'
                WHEN price_kes <= 2000000   THEN 'mid'
                ELSE 'premium'
            END
        WHEN category = 'phones' THEN
            CASE
                WHEN price_kes <= 10000     THEN 'budget'
                WHEN price_kes <= 50000     THEN 'mid'
                ELSE 'premium'
            END
        WHEN category = 'property' THEN
            CASE
                WHEN price_kes <= 15000     THEN 'budget'
                WHEN price_kes <= 50000     THEN 'mid'
                ELSE 'premium'
            END
        ELSE
            CASE
                WHEN price_kes <= 10000     THEN 'budget'
                WHEN price_kes <= 100000    THEN 'mid'
                ELSE 'premium'
            END
    END AS price_category

FROM {{ ref('stg_jiji_listings') }}
