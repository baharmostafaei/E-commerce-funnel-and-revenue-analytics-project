DROP TABLE IF EXISTS fact_customer_value_180d;

CREATE TABLE fact_customer_value_180d AS

WITH valid_orders AS (
    SELECT
        o.user_key,
        o.order_id,
        d.full_date::date AS order_date,
        o.total_payment_value
    FROM fact_orders o
    JOIN dim_date d
        ON d.date_key = o.date_key
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
),

retention_base AS (
    SELECT
        user_key,
        channel_id,
        first_order_date::date AS first_order_date,
        second_order_date::date AS second_order_date,
        is_churned_180d,
        is_repeat_180d
    FROM fact_customer_retention
)

SELECT
    r.user_key,
    r.channel_id,

    r.first_order_date,

    DATE_TRUNC(
        'month',
        r.first_order_date
    )::date AS cohort_month,

    r.second_order_date,

    r.is_repeat_180d,
    r.is_churned_180d,

    CASE
        WHEN r.second_order_date IS NOT NULL
        THEN r.second_order_date - r.first_order_date
        ELSE NULL
    END AS days_to_second_order,

    COUNT(DISTINCT vo.order_id)
        FILTER (
            WHERE vo.order_date >= r.first_order_date
              AND vo.order_date <=
                  r.first_order_date + INTERVAL '180 days'
        ) AS orders_180d,

    COALESCE(
        SUM(vo.total_payment_value)
        FILTER (
            WHERE vo.order_date >= r.first_order_date
              AND vo.order_date <=
                  r.first_order_date + INTERVAL '180 days'
        ),
        0
    ) AS revenue_180d

FROM retention_base r

LEFT JOIN valid_orders vo
    ON vo.user_key = r.user_key

GROUP BY
    r.user_key,
    r.channel_id,
    r.first_order_date,
    r.second_order_date,
    r.is_repeat_180d,
    r.is_churned_180d;