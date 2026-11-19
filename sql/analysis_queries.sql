SELECT d.month_start,SUM(f.mrr_amount) AS mrr,
       SUM(f.active_customer_count) AS active_customers
FROM fact_subscription_monthly f JOIN dim_month d USING(month_key)
GROUP BY d.month_start ORDER BY d.month_start;

SELECT d.month_start,p.plan,c.industry,SUM(f.mrr_amount) AS mrr
FROM fact_subscription_monthly f
JOIN dim_month d USING(month_key)
JOIN dim_plan p USING(plan_key)
JOIN dim_customer c USING(customer_key)
GROUP BY d.month_start,p.plan,c.industry
ORDER BY d.month_start,p.plan,c.industry;
