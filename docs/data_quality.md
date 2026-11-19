# Source data quality and modeling notes

The raw generator deliberately introduces duplicate subscription and event records, a missing industry, inconsistent whitespace/capitalization, a malformed event date, and a negative subscription price.

The pipeline reports issue counts, normalizes text, fills missing industry as `Unknown`, removes exact duplicates, rejects invalid dates, excludes negative prices from the modeled fact, and enforces dimension relationships.

## Fact grain
`fact_subscription_monthly` has one row per customer per month when active at month end. It is a monthly snapshot, not a transaction fact.

## Leakage
This is descriptive analytics, not a predictive model. Future cancellation dates and churn reasons must not be used as features when training a predictive churn model.

All generated data and injected defects are synthetic.
