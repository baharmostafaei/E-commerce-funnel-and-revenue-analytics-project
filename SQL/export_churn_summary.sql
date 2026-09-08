COPY (
WITH customer_orders AS (
    SELECT
        o.user_key,
        d.full_date AS order_date,
        LEAD(d.full_date) OVER (PARTITION BY o.user_key ORDER BY d.full_date) AS next_order_date
    FROM fact_orders o
    JOIN dim_date d ON d.date_key = o.date_key
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
),
flagged AS (
    SELECT
        *,
        CASE
            WHEN next_order_date IS NULL THEN TRUE
            WHEN next_order_date - order_date > INTERVAL '180 days' THEN TRUE
            ELSE FALSE
        END AS is_churn_after_this_order
    FROM customer_orders
)
SELECT
    DATE_TRUNC('month', order_date)::date AS cohort_month,
    COUNT(*) AS orders,
    SUM(CASE WHEN is_churn_after_this_order THEN 1 ELSE 0 END) AS churned_after,
    ROUND(100.0 * SUM(CASE WHEN is_churn_after_this_order THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate_pct
FROM flagged
GROUP BY 1
ORDER BY 1
) TO '/tmp/churn_summary.csv' WITH CSV HEADER;
