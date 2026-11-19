# Metric definitions

- MRR: sum of monthly subscription prices for customers active at month end.
- Active customer: signup on/before month end and churn after month end or no churn date.
- Monthly churn: customers whose churn date falls in the month divided by customers active at the beginning of the month.
- Cohort retention: cohort customers not yet churned by cohort age divided by original cohort size.
- ARPA: MRR divided by active customers.
- Simple LTV proxy: ARPA divided by monthly churn; excludes margin, discounting, expansion, and acquisition cost.

The what-if model assumes constant ARPA and churn, no new customers, and no discounting. Data is synthetic.
