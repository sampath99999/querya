# Eval run: openai/querya-qwen2.5-coder:3b on sqlite

Started 2026-11-21 18:35 UTC.

| Metric | Value |
| --- | --- |
| Questions | 33 |
| Execution accuracy | 21/33 (63.6%) |
| Runs that produced an answer | 93.9% |
| Avg model calls per question | 3.67 |
| Avg SQL attempts per question | 1.39 |
| Avg trace steps per question | 8.18 |
| Avg / median latency | 42.21 s / 36.26 s |
| Tokens (in / out) | 160391 / 5999 |

| Case | Pass | Calls | SQL tries | Latency (s) | Note |
| --- | --- | --- | --- | --- | --- |
| orders_all_statuses | yes | 3 | 1 | 32.8 |  |
| customer_count | yes | 3 | 1 | 36.6 |  |
| orders_per_status | no | 3 | 1 | 45.0 | 3 rows, expected 5 |
| revenue_2025 | yes | 3 | 1 | 54.5 |  |
| revenue_by_year | yes | 3 | 1 | 59.4 |  |
| monthly_revenue_2025 | yes | 3 | 1 | 74.4 |  |
| top5_products_revenue | yes | 3 | 1 | 40.8 |  |
| revenue_by_category | no | 4 | 2 | 51.5 | 5 rows, expected 7 |
| top_category_2024 | yes | 6 | 3 | 114.9 |  |
| orders_per_channel | yes | 3 | 1 | 37.2 |  |
| aov_2025 | no | 3 | 1 | 46.4 | values differ |
| customers_per_region | yes | 3 | 1 | 36.3 |  |
| top_region_revenue | yes | 9 | 1 | 122.7 |  |
| top_country_customers | yes | 3 | 1 | 21.6 |  |
| completed_payments_by_method | yes | 3 | 1 | 27.6 |  |
| refunded_amount | yes | 3 | 1 | 36.3 |  |
| failed_payments | yes | 3 | 1 | 29.3 |  |
| cancellation_rate | no | 3 | 1 | 40.5 | values differ |
| black_friday_2025 | no | 3 | 1 | 49.1 | values differ |
| signups_2025 | yes | 3 | 1 | 35.6 |  |
| avg_units_per_order | no | 3 | 1 | 34.6 | values differ |
| top5_customer_ids_spend | yes | 3 | 1 | 56.5 |  |
| gross_profit_by_category | no | 7 | 4 | 169.9 | Gave up after 4 failed queries |
| most_units_product | no | 3 | 1 | 25.3 | values differ |
| orders_per_segment | yes | 3 | 1 | 8.4 |  |
| mobile_share_2025 | no | 6 | 4 | 15.2 | values differ |
| monthly_orders_2024 | yes | 3 | 1 | 11.4 |  |
| electronics_subcategories | no | 7 | 4 | 24.5 | Gave up after 4 failed queries |
| customers_without_orders | yes | 4 | 2 | 9.4 |  |
| avg_discount_when_discounted | yes | 3 | 1 | 6.5 |  |
| busiest_day | yes | 3 | 1 | 11.8 |  |
| revenue_growth_pct | no | 3 | 1 | 19.7 | 2 rows, expected 1 |
| shipping_fees_2025 | no | 3 | 1 | 7.2 | values differ |
