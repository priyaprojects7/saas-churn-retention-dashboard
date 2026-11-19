CREATE TABLE IF NOT EXISTS dim_customer (
 customer_key INTEGER PRIMARY KEY, customer_id VARCHAR(32) NOT NULL UNIQUE,
 acquisition_channel VARCHAR(80) NOT NULL, industry VARCHAR(80) NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_plan (
 plan_key INTEGER PRIMARY KEY, plan VARCHAR(40) NOT NULL UNIQUE,
 list_monthly_price NUMERIC(12,2) NOT NULL CHECK (list_monthly_price >= 0)
);
CREATE TABLE IF NOT EXISTS dim_month (
 month_key INTEGER PRIMARY KEY, month_start DATE NOT NULL UNIQUE,
 calendar_year INTEGER NOT NULL, calendar_quarter VARCHAR(2) NOT NULL,
 month_number INTEGER NOT NULL CHECK (month_number BETWEEN 1 AND 12),
 month_name VARCHAR(16) NOT NULL
);
CREATE TABLE IF NOT EXISTS fact_subscription_monthly (
 month_key INTEGER NOT NULL REFERENCES dim_month(month_key),
 customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
 plan_key INTEGER NOT NULL REFERENCES dim_plan(plan_key),
 active_customer_count INTEGER NOT NULL DEFAULT 1,
 mrr_amount NUMERIC(12,2) NOT NULL CHECK (mrr_amount >= 0),
 seats INTEGER NOT NULL CHECK (seats >= 0),
 PRIMARY KEY (month_key,customer_key)
);
CREATE INDEX IF NOT EXISTS idx_fact_month_plan ON fact_subscription_monthly(month_key,plan_key);
CREATE INDEX IF NOT EXISTS idx_dim_customer_industry ON dim_customer(industry);
