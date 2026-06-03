---
title: Phones & Tablets Market — Jiji Kenya Intelligence
---

# Kenya Phones & Tablets Market

Analysis of phones and tablets listed on Jiji Kenya — brand pricing, new vs used mix, and regional demand.

```sql phones_overview
SELECT
    COUNT(*)                             AS total_listings,
    ROUND(AVG(price_kes), 0)             AS avg_price_kes,
    ROUND(MEDIAN(price_kes), 0)          AS median_price_kes,
    COUNT(CASE WHEN UPPER(condition) = 'NEW'  THEN 1 END) AS new_count,
    COUNT(CASE WHEN UPPER(condition) = 'USED' THEN 1 END) AS used_count
FROM marts.fct_listings
WHERE category = 'phones'
```

<BigValue data={phones_overview} value=total_listings title="Total Phone Listings" />
<BigValue data={phones_overview} value=median_price_kes title="Median Price (KES)" fmt=num0 />
<BigValue data={phones_overview} value=new_count title="New Listings" />
<BigValue data={phones_overview} value=used_count title="Used Listings" />

---

## Price Range by Brand

```sql brand_prices
SELECT
    CASE
        WHEN UPPER(title) LIKE '%SAMSUNG%'  THEN 'Samsung'
        WHEN UPPER(title) LIKE '%IPHONE%'
          OR UPPER(title) LIKE '%APPLE%'    THEN 'iPhone'
        WHEN UPPER(title) LIKE '%TECNO%'    THEN 'Tecno'
        WHEN UPPER(title) LIKE '%INFINIX%'  THEN 'Infinix'
        WHEN UPPER(title) LIKE '%ITEL%'     THEN 'Itel'
        WHEN UPPER(title) LIKE '%HUAWEI%'   THEN 'Huawei'
        WHEN UPPER(title) LIKE '%XIAOMI%'
          OR UPPER(title) LIKE '%REDMI%'    THEN 'Xiaomi'
        WHEN UPPER(title) LIKE '%NOKIA%'    THEN 'Nokia'
        WHEN UPPER(title) LIKE '%OPPO%'     THEN 'Oppo'
        WHEN UPPER(title) LIKE '%VIVO%'     THEN 'Vivo'
        WHEN UPPER(title) LIKE '%REALME%'   THEN 'Realme'
        WHEN UPPER(title) LIKE '%MOTOROLA%' THEN 'Motorola'
        ELSE 'Other'
    END AS brand,
    COUNT(*)                            AS listing_count,
    ROUND(MIN(price_kes), 0)            AS min_price_kes,
    ROUND(MEDIAN(price_kes), 0)         AS median_price_kes,
    ROUND(MAX(price_kes), 0)            AS max_price_kes
FROM marts.fct_listings
WHERE category = 'phones'
  AND price_kes IS NOT NULL
GROUP BY brand
ORDER BY listing_count DESC
```

<BarChart
    data={brand_prices}
    x=brand
    y=median_price_kes
    title="Median Phone Price by Brand (KES)"
    xAxisTitle="Brand"
    yAxisTitle="Median Price (KES)"
    colorPalette={['#FF9800']}
/>

<DataTable data={brand_prices} title="Brand Price Ranges" rows=15>
    <Column id=brand title="Brand" />
    <Column id=listing_count title="Listings" align=right />
    <Column id=min_price_kes title="Min (KES)" fmt=num0 align=right />
    <Column id=median_price_kes title="Median (KES)" fmt=num0 align=right />
    <Column id=max_price_kes title="Max (KES)" fmt=num0 align=right />
</DataTable>

---

## New vs Used Ratio

```sql condition_breakdown
SELECT
    condition,
    COUNT(*) AS listing_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM marts.fct_listings
WHERE category = 'phones'
  AND condition != 'N/A'
GROUP BY condition
ORDER BY listing_count DESC
```

<BarChart
    data={condition_breakdown}
    x=condition
    y=listing_count
    title="New vs Used Phone Listings"
    xAxisTitle="Condition"
    yAxisTitle="Listings"
    colorPalette={['#4CAF50', '#F44336']}
/>

---

## Location Distribution

```sql phones_by_city
SELECT
    location,
    listing_count,
    ROUND(median_price_kes, 0) AS median_price_kes
FROM marts.mart_price_by_location
WHERE category = 'phones'
ORDER BY listing_count DESC
LIMIT 10
```

<BarChart
    data={phones_by_city}
    x=location
    y=listing_count
    title="Phone Listings by City"
    xAxisTitle="City"
    yAxisTitle="Listings"
    colorPalette={['#9C27B0']}
/>

---

## Price Tier Distribution

```sql phones_tiers
SELECT
    price_category,
    COUNT(*) AS listing_count,
    ROUND(AVG(price_kes), 0) AS avg_price_kes
FROM marts.fct_listings
WHERE category = 'phones'
GROUP BY price_category
ORDER BY listing_count DESC
```

<DataTable data={phones_tiers} title="Phone Price Tiers">
    <Column id=price_category title="Tier" />
    <Column id=listing_count title="Listings" align=right />
    <Column id=avg_price_kes title="Avg Price (KES)" fmt=num0 align=right />
</DataTable>
