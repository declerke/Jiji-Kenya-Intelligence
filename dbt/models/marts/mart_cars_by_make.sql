/*
mart_cars_by_make — Car market analysis by manufacturer.

Extracts vehicle make from listing title using known make list.
Returns top 20 makes by listing count with price statistics.
*/

WITH cars AS (

    SELECT
        listing_id,
        title,
        price_kes,
        scrape_date
    FROM {{ ref('fct_listings') }}
    WHERE category = 'cars'

),

make_extracted AS (

    SELECT
        listing_id,
        title,
        price_kes,
        scrape_date,

        -- Extract make using CASE on known brands (first match wins)
        CASE
            WHEN UPPER(title) LIKE '%TOYOTA%'        THEN 'Toyota'
            WHEN UPPER(title) LIKE '%NISSAN%'         THEN 'Nissan'
            WHEN UPPER(title) LIKE '%MITSUBISHI%'     THEN 'Mitsubishi'
            WHEN UPPER(title) LIKE '%SUBARU%'         THEN 'Subaru'
            WHEN UPPER(title) LIKE '%HONDA%'          THEN 'Honda'
            WHEN UPPER(title) LIKE '%MAZDA%'          THEN 'Mazda'
            WHEN UPPER(title) LIKE '%ISUZU%'          THEN 'Isuzu'
            WHEN UPPER(title) LIKE '%MERCEDES%'       THEN 'Mercedes'
            WHEN UPPER(title) LIKE '%BMW%'            THEN 'BMW'
            WHEN UPPER(title) LIKE '%VOLKSWAGEN%'     THEN 'Volkswagen'
            WHEN UPPER(title) LIKE '%VW%'             THEN 'Volkswagen'
            WHEN UPPER(title) LIKE '%AUDI%'           THEN 'Audi'
            WHEN UPPER(title) LIKE '%FORD%'           THEN 'Ford'
            WHEN UPPER(title) LIKE '%HYUNDAI%'        THEN 'Hyundai'
            WHEN UPPER(title) LIKE '%KIA%'            THEN 'Kia'
            WHEN UPPER(title) LIKE '%LAND ROVER%'     THEN 'Land Rover'
            WHEN UPPER(title) LIKE '%RANGE ROVER%'    THEN 'Land Rover'
            WHEN UPPER(title) LIKE '%PEUGEOT%'        THEN 'Peugeot'
            WHEN UPPER(title) LIKE '%SUZUKI%'         THEN 'Suzuki'
            WHEN UPPER(title) LIKE '%JEEP%'           THEN 'Jeep'
            WHEN UPPER(title) LIKE '%LEXUS%'          THEN 'Lexus'
            WHEN UPPER(title) LIKE '%VOLVO%'          THEN 'Volvo'
            WHEN UPPER(title) LIKE '%RENAULT%'        THEN 'Renault'
            WHEN UPPER(title) LIKE '%FIAT%'           THEN 'Fiat'
            WHEN UPPER(title) LIKE '%CHEVROLET%'      THEN 'Chevrolet'
            WHEN UPPER(title) LIKE '%PORSCHE%'        THEN 'Porsche'
            WHEN UPPER(title) LIKE '%JAGUAR%'         THEN 'Jaguar'
            WHEN UPPER(title) LIKE '%MINI%'           THEN 'Mini'
            WHEN UPPER(title) LIKE '%SSANGYONG%'      THEN 'SsangYong'
            WHEN UPPER(title) LIKE '%TATA%'           THEN 'Tata'
            WHEN UPPER(title) LIKE '%MAHINDRA%'       THEN 'Mahindra'
            WHEN UPPER(title) LIKE '%BYD%'            THEN 'BYD'
            WHEN UPPER(title) LIKE '%HAVAL%'          THEN 'Haval'
            WHEN UPPER(title) LIKE '%GREAT WALL%'     THEN 'Great Wall'
            WHEN UPPER(title) LIKE '%CHANGAN%'        THEN 'Changan'
            WHEN UPPER(title) LIKE '%FOTON%'          THEN 'Foton'
            ELSE 'Other'
        END AS make

    FROM cars

),

make_stats AS (

    SELECT
        make,
        COUNT(*)           AS listing_count,
        AVG(price_kes)     AS avg_price_kes,
        MEDIAN(price_kes)  AS median_price_kes,
        MIN(price_kes)     AS min_price_kes,
        MAX(price_kes)     AS max_price_kes,
        MAX(scrape_date)   AS latest_scrape_date
    FROM make_extracted
    GROUP BY make

),

ranked AS (

    SELECT
        make,
        listing_count,
        ROUND(avg_price_kes, 2)    AS avg_price_kes,
        ROUND(median_price_kes, 2) AS median_price_kes,
        ROUND(min_price_kes, 2)    AS min_price_kes,
        ROUND(max_price_kes, 2)    AS max_price_kes,
        latest_scrape_date,
        ROW_NUMBER() OVER (ORDER BY listing_count DESC) AS rank
    FROM make_stats

)

SELECT *
FROM ranked
WHERE rank <= 20
ORDER BY rank
