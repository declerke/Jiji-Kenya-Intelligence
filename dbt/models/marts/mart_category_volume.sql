/*
mart_category_volume — Per category + scrape_date volume and pricing trends.

Tracks daily listing counts, average prices, and new vs used mix.
Useful for monitoring scrape health and identifying market trends.
*/

WITH base AS (

    SELECT
        category,
        scrape_date,
        price_kes,
        condition
    FROM {{ ref('fct_listings') }}

),

aggregated AS (

    SELECT
        category,
        scrape_date,
        COUNT(*)                                                    AS listing_count,
        AVG(price_kes)                                              AS avg_price_kes,
        MEDIAN(price_kes)                                           AS median_price_kes,

        -- New vs Used ratio
        COUNT(CASE WHEN UPPER(condition) = 'NEW'  THEN 1 END)       AS new_count,
        COUNT(CASE WHEN UPPER(condition) = 'USED' THEN 1 END)       AS used_count,
        COUNT(CASE WHEN condition = 'N/A'
                     OR condition IS NULL                THEN 1 END) AS unknown_count,

        ROUND(
            100.0 * COUNT(CASE WHEN UPPER(condition) = 'NEW' THEN 1 END)
            / NULLIF(
                COUNT(CASE WHEN UPPER(condition) IN ('NEW', 'USED') THEN 1 END), 0
            ), 2
        )                                                            AS pct_new

    FROM base
    GROUP BY category, scrape_date

)

SELECT
    category,
    scrape_date,
    listing_count,
    ROUND(avg_price_kes, 2)    AS avg_price_kes,
    ROUND(median_price_kes, 2) AS median_price_kes,
    new_count,
    used_count,
    unknown_count,
    pct_new
FROM aggregated
ORDER BY scrape_date DESC, category
