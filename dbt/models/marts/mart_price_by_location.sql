/*
mart_price_by_location — Per category + city price analytics.

Includes only cities with 5 or more listings.
Provides median, average, and listing count for data journalism use.
*/

WITH base AS (

    SELECT
        category,
        location,
        price_kes
    FROM {{ ref('fct_listings') }}
    WHERE price_kes IS NOT NULL
      AND location != 'Unknown'

),

city_stats AS (

    SELECT
        category,
        location,
        COUNT(*)                                        AS listing_count,
        AVG(price_kes)                                  AS avg_price_kes,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_kes) AS median_price_kes,
        MIN(price_kes)                                  AS min_price_kes,
        MAX(price_kes)                                  AS max_price_kes
    FROM base
    GROUP BY category, location

)

SELECT
    category,
    location,
    listing_count,
    ROUND(avg_price_kes, 2)        AS avg_price_kes,
    ROUND(median_price_kes, 2)     AS median_price_kes,
    ROUND(min_price_kes, 2)        AS min_price_kes,
    ROUND(max_price_kes, 2)        AS max_price_kes
FROM city_stats
WHERE listing_count >= 5
ORDER BY category, listing_count DESC
