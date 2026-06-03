---
title: Cars Market — Jiji Kenya Intelligence
---

# Kenya Used Car Market

Analysis of cars listed on Jiji Kenya — prices, popular makes, and regional demand.

```sql cars_overview
SELECT
    COUNT(*)                             AS total_listings,
    ROUND(AVG(price_kes), 0)             AS avg_price_kes,
    ROUND(MEDIAN(price_kes), 0)          AS median_price_kes,
    MIN(price_kes)                       AS min_price_kes,
    MAX(price_kes)                       AS max_price_kes
FROM marts.fct_listings
WHERE category = 'cars'
  AND price_kes IS NOT NULL
```

<BigValue data={cars_overview} value=total_listings title="Total Car Listings" />
<BigValue data={cars_overview} value=median_price_kes title="Median Price (KES)" fmt=num0 />
<BigValue data={cars_overview} value=avg_price_kes title="Average Price (KES)" fmt=num0 />

---

## Price Distribution

```sql cars_price_buckets
SELECT
    CASE
        WHEN price_kes < 200000   THEN 'Under 200K'
        WHEN price_kes < 500000   THEN '200K – 500K'
        WHEN price_kes < 1000000  THEN '500K – 1M'
        WHEN price_kes < 2000000  THEN '1M – 2M'
        WHEN price_kes < 5000000  THEN '2M – 5M'
        ELSE 'Over 5M'
    END AS price_range,
    COUNT(*) AS listing_count,
    CASE
        WHEN price_kes < 200000   THEN 1
        WHEN price_kes < 500000   THEN 2
        WHEN price_kes < 1000000  THEN 3
        WHEN price_kes < 2000000  THEN 4
        WHEN price_kes < 5000000  THEN 5
        ELSE 6
    END AS sort_order
FROM marts.fct_listings
WHERE category = 'cars'
  AND price_kes IS NOT NULL
GROUP BY price_range, sort_order
ORDER BY sort_order
```

<BarChart
    data={cars_price_buckets}
    x=price_range
    y=listing_count
    title="Car Listings by Price Range (KES)"
    xAxisTitle="Price Range"
    yAxisTitle="Number of Listings"
    colorPalette={['#1976D2']}
/>

---

## Top Car Makes

```sql top_makes
SELECT
    make,
    listing_count,
    ROUND(avg_price_kes, 0) AS avg_price_kes,
    ROUND(median_price_kes, 0) AS median_price_kes,
    rank
FROM marts.mart_cars_by_make
ORDER BY rank
LIMIT 20
```

<BarChart
    data={top_makes}
    x=make
    y=listing_count
    title="Top 20 Car Makes by Listing Count"
    xAxisTitle="Make"
    yAxisTitle="Listings"
    colorPalette={['#2196F3']}
/>

<DataTable
    data={top_makes}
    title="Car Makes — Price Comparison"
    rows=20
>
    <Column id=rank title="Rank" align=center />
    <Column id=make title="Make" />
    <Column id=listing_count title="Listings" align=right />
    <Column id=avg_price_kes title="Avg Price (KES)" fmt=num0 align=right />
    <Column id=median_price_kes title="Median Price (KES)" fmt=num0 align=right />
</DataTable>

---

## Price by Location — Top Cities

```sql cars_by_city
SELECT
    location,
    listing_count,
    ROUND(median_price_kes, 0) AS median_price_kes,
    ROUND(avg_price_kes, 0) AS avg_price_kes
FROM marts.mart_price_by_location
WHERE category = 'cars'
ORDER BY listing_count DESC
LIMIT 10
```

<BarChart
    data={cars_by_city}
    x=location
    y=median_price_kes
    title="Median Car Price by City (KES)"
    xAxisTitle="City"
    yAxisTitle="Median Price (KES)"
    colorPalette={['#4CAF50']}
/>

<DataTable data={cars_by_city} title="Cars — City Price Summary" rows=10>
    <Column id=location title="City" />
    <Column id=listing_count title="Listings" align=right />
    <Column id=median_price_kes title="Median (KES)" fmt=num0 align=right />
    <Column id=avg_price_kes title="Average (KES)" fmt=num0 align=right />
</DataTable>

---

## Price Tier Breakdown

```sql cars_price_tiers
SELECT
    price_category,
    COUNT(*) AS listing_count
FROM marts.fct_listings
WHERE category = 'cars'
GROUP BY price_category
ORDER BY listing_count DESC
```

<BarChart
    data={cars_price_tiers}
    x=price_category
    y=listing_count
    title="Budget / Mid / Premium Cars"
    xAxisTitle="Price Tier"
    yAxisTitle="Listings"
/>
