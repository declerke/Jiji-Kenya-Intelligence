---
title: Jiji Kenya Intelligence — Overview
---

# Jiji Kenya Classifieds Intelligence

Real-time analytics across Cars, Phones & Tablets, and Rental Property listings scraped daily from [Jiji.co.ke](https://jiji.co.ke).

```sql category_summary
SELECT
    category,
    COUNT(*)                                    AS listing_count,
    ROUND(AVG(price_kes), 0)                    AS avg_price_kes,
    ROUND(MEDIAN(price_kes), 0)                 AS median_price_kes,
    MAX(scrape_date)::VARCHAR                   AS latest_scrape
FROM jiji.fct_listings
GROUP BY category
ORDER BY listing_count DESC
```

## Listings by Category

<BarChart
    data={category_summary}
    x=category
    y=listing_count
    title="Total Active Listings by Category"
    xAxisTitle="Category"
    yAxisTitle="Listings"
    colorPalette={['#2196F3', '#4CAF50', '#FF9800']}
/>

## Price Summary by Category

<DataTable
    data={category_summary}
    title="Average & Median Prices (KES)"
    rows=10
>
    <Column id=category title="Category" />
    <Column id=listing_count title="Listings" align=right />
    <Column id=avg_price_kes title="Avg Price (KES)" fmt=num0 align=right />
    <Column id=median_price_kes title="Median Price (KES)" fmt=num0 align=right />
    <Column id=latest_scrape title="Last Scraped" />
</DataTable>

---

```sql daily_volume
SELECT
    scrape_date::VARCHAR AS scrape_date,
    category,
    listing_count
FROM jiji.mart_category_volume
ORDER BY scrape_date DESC, category
LIMIT 30
```

## Daily Scrape Volume

<LineChart
    data={daily_volume}
    x=scrape_date
    y=listing_count
    series=category
    title="Daily Listings Scraped per Category"
    xAxisTitle="Date"
    yAxisTitle="Listings"
/>

---

```sql total_stats
SELECT
    COUNT(*)                         AS total_listings,
    COUNT(DISTINCT category)         AS categories,
    COUNT(DISTINCT location)         AS cities,
    MAX(scrape_date)::VARCHAR        AS latest_scrape_date,
    MIN(scrape_date)::VARCHAR        AS first_scrape_date
FROM jiji.fct_listings
```

## Pipeline Stats

<BigValue
    data={total_stats}
    value=total_listings
    title="Total Listings"
/>

<BigValue
    data={total_stats}
    value=cities
    title="Cities Covered"
/>

<BigValue
    data={total_stats}
    value=latest_scrape_date
    title="Latest Scrape"
/>

---

```sql price_tiers
SELECT
    category,
    price_category,
    COUNT(*) AS count
FROM jiji.fct_listings
WHERE price_category != 'unknown'
GROUP BY category, price_category
ORDER BY category, count DESC
```

## Price Tier Distribution

<BarChart
    data={price_tiers}
    x=price_category
    y=count
    series=category
    title="Budget / Mid / Premium Listings per Category"
    xAxisTitle="Price Tier"
    yAxisTitle="Listings"
    type=grouped
/>
