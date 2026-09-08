-- ============================================================
-- analytics_queries.sql
-- E-Commerce Product Funnel & Revenue Analytics
-- Star schema: fact_orders, fact_order_items, fact_events, fact_channel_spend
--              dim_users, dim_products, dim_marketing_channel, dim_date
-- ============================================================


-- ------------------------------------------------------------
-- Q1. MULTI-STEP CONVERSION FUNNEL (overall)
--     Uses conditional aggregation (COUNT DISTINCT ... FILTER) to count how
--     many sessions reached each stage, then LAG() to compute stage-over-
--     stage drop-off %.
-- ------------------------------------------------------------
WITH stage_counts AS (
    SELECT
        stage,
        stage_order,
        COUNT(DISTINCT session_id) AS sessions_reached
    FROM fact_events
    GROUP BY stage, stage_order
),
funnel AS (
    SELECT
        stage,
        stage_order,
        sessions_reached,
        LAG(sessions_reached) OVER (ORDER BY stage_order) AS prev_stage_sessions
    FROM stage_counts
)
SELECT
    stage_order,
    stage,
    sessions_reached,
    ROUND(100.0 * sessions_reached / FIRST_VALUE(sessions_reached) OVER (ORDER BY stage_order), 2) AS pct_of_total,
    ROUND(100.0 * sessions_reached / NULLIF(prev_stage_sessions, 0), 2) AS pct_of_prev_stage,
    prev_stage_sessions - sessions_reached AS drop_off_count
FROM funnel
ORDER BY stage_order;


-- ------------------------------------------------------------
-- Q2. FUNNEL BY MARKETING CHANNEL
--     Which channel converts best end-to-end? CTE + conditional aggregation.
-- ------------------------------------------------------------
WITH channel_stage AS (
    SELECT
        c.channel_name,
        e.stage,
        e.stage_order,
        COUNT(DISTINCT e.session_id) AS sessions
    FROM fact_events e
    JOIN dim_marketing_channel c ON c.channel_id = e.channel_id
    GROUP BY c.channel_name, e.stage, e.stage_order
),
pivoted AS (
    SELECT
        channel_name,
        MAX(sessions) FILTER (WHERE stage = 'session_start')  AS sessions,
        MAX(sessions) FILTER (WHERE stage = 'product_view')   AS product_views,
        MAX(sessions) FILTER (WHERE stage = 'add_to_cart')    AS add_to_cart,
        MAX(sessions) FILTER (WHERE stage = 'checkout_start') AS checkout_start,
        MAX(sessions) FILTER (WHERE stage = 'purchase')       AS purchases
    FROM channel_stage
    GROUP BY channel_name
)
SELECT
    channel_name,
    sessions,
    purchases,
    ROUND(100.0 * purchases / NULLIF(sessions, 0), 2) AS overall_conversion_pct,
    ROUND(100.0 * add_to_cart / NULLIF(sessions, 0), 2) AS view_to_cart_pct,
    ROUND(100.0 * purchases / NULLIF(checkout_start, 0), 2) AS checkout_to_purchase_pct
FROM pivoted
ORDER BY overall_conversion_pct DESC;


-- ------------------------------------------------------------
-- Q3. TIME-TO-CONVERT PER SESSION (LAG within a session)
--     For converted sessions, how long does each stage transition take?
--     Demonstrates LAG() partitioned by session_id, ordered by stage_order.
-- ------------------------------------------------------------
WITH session_stage_time AS (
    SELECT
        e.session_id,
        e.stage,
        e.stage_order,
        e.stage_timestamp,
        LAG(e.stage_timestamp) OVER (PARTITION BY e.session_id ORDER BY e.stage_order) AS prev_stage_ts
    FROM fact_events e
    WHERE e.session_id LIKE 'S-%'   -- converted (real-order) sessions only
)
SELECT
    stage,
    COUNT(*) AS n_sessions,
    ROUND(AVG(EXTRACT(EPOCH FROM (stage_timestamp - prev_stage_ts)) / 60)::numeric, 1) AS avg_minutes_since_prev_stage
FROM session_stage_time
WHERE prev_stage_ts IS NOT NULL
GROUP BY stage, stage_order
ORDER BY stage_order;


-- ------------------------------------------------------------
-- Q4. CAC (Customer Acquisition Cost) BY CHANNEL & MONTH
--     Spend from fact_channel_spend / count of NEW customers acquired
--     (first-ever order) that month via that channel.
-- ------------------------------------------------------------
WITH new_customers AS (
    SELECT
        o.channel_id,
        d.year_month,
        COUNT(DISTINCT o.user_key) AS new_customers
    FROM fact_orders o
    JOIN dim_date d ON d.date_key = o.date_key
    JOIN dim_users u ON u.user_key = o.user_key
    WHERE d.full_date = u.first_order_date::date   -- this order IS their first order
    GROUP BY o.channel_id, d.year_month
)
SELECT
    c.channel_name,
    nc.year_month,
    nc.new_customers,
    s.spend_amount,
    ROUND((s.spend_amount / NULLIF(nc.new_customers, 0))::numeric, 2) AS cac
FROM new_customers nc
JOIN fact_channel_spend s ON s.channel_id = nc.channel_id AND s.year_month = nc.year_month
JOIN dim_marketing_channel c ON c.channel_id = nc.channel_id
ORDER BY nc.year_month, cac;


-- ------------------------------------------------------------
-- Q5. ROAS (Return on Ad Spend) BY CHANNEL
--     Revenue attributed to a channel (via each customer's acquisition
--     channel) / total spend on that channel, all-time.
-- ------------------------------------------------------------
WITH revenue_by_channel AS (
    SELECT
        o.channel_id,
        SUM(o.total_payment_value) AS revenue
    FROM fact_orders o
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY o.channel_id
),
spend_by_channel AS (
    SELECT channel_id, SUM(spend_amount) AS total_spend
    FROM fact_channel_spend
    GROUP BY channel_id
)
SELECT
    c.channel_name,
    c.channel_type,
    r.revenue,
    s.total_spend,
    ROUND((r.revenue / NULLIF(s.total_spend, 0))::numeric, 2) AS roas
FROM revenue_by_channel r
JOIN spend_by_channel s ON s.channel_id = r.channel_id
JOIN dim_marketing_channel c ON c.channel_id = r.channel_id
ORDER BY roas DESC NULLS LAST;


-- ------------------------------------------------------------
-- Q6. AOV (Average Order Value) TREND + 3-MONTH MOVING AVERAGE
--     Window function moving average over month-ordered rows.
-- ------------------------------------------------------------
WITH monthly_aov AS (
    SELECT
        d.year_month,
        COUNT(o.order_id) AS orders,
        SUM(o.total_payment_value) AS revenue,
        ROUND(AVG(o.total_payment_value)::numeric, 2) AS aov
    FROM fact_orders o
    JOIN dim_date d ON d.date_key = o.date_key
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY d.year_month
)
SELECT
    year_month,
    orders,
    revenue,
    aov,
    ROUND(AVG(aov) OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)::numeric, 2) AS aov_3mo_moving_avg
FROM monthly_aov
ORDER BY year_month;


-- ------------------------------------------------------------
-- Q7. CHURN RATE — customers with no repeat order within 180 days
--     Uses LEAD() to find each customer's NEXT order date, then flags churn.
-- ------------------------------------------------------------
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
            WHEN next_order_date IS NULL THEN TRUE   -- no repeat order at all
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
ORDER BY 1;


-- ------------------------------------------------------------
-- Q8. CATEGORY-LEVEL DRILL-DOWN (for dashboard drill-down capability)
--     ROW_NUMBER() to rank top category per state.
-- ------------------------------------------------------------
WITH cat_state_rev AS (
    SELECT
        u.customer_state,
        p.category_name,
        SUM(foi.price) AS revenue,
        ROW_NUMBER() OVER (PARTITION BY u.customer_state ORDER BY SUM(foi.price) DESC) AS rnk
    FROM fact_order_items foi
    JOIN dim_products p ON p.product_key = foi.product_key
    JOIN dim_users u ON u.user_key = foi.user_key
    GROUP BY u.customer_state, p.category_name
)
SELECT customer_state, category_name AS top_category, revenue
FROM cat_state_rev
WHERE rnk = 1
ORDER BY revenue DESC
LIMIT 15;
