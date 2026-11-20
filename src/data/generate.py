from pathlib import Path
import numpy as np
import pandas as pd


def generate_subscriptions(n_customers=2500, start="2023-01-01", end="2025-12-31", seed=42):
    """Generate deterministic synthetic subscription records with engagement signals."""
    rng = np.random.default_rng(seed)
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    days = max(1, (end_ts - start_ts).days)
    signup = start_ts + pd.to_timedelta(rng.integers(0, days, n_customers), unit="D")
    plan = rng.choice(["Starter", "Growth", "Enterprise"], n_customers, p=[.55, .32, .13])
    prices = pd.Series(plan).map({"Starter": 49.0, "Growth": 149.0, "Enterprise": 499.0}).to_numpy()

    # Engagement and service signals create explainable, correlated churn risk.
    product_usage = np.clip(rng.beta(2.2, 2.0, n_customers) * 100, 0, 100).round(1)
    usage_change = np.clip(rng.normal((product_usage - 50) * .65, 24), -100, 100).round(1)
    support_tickets = np.clip(rng.poisson(1.0 + (100 - product_usage) / 28), 0, 15)
    payment_failures = np.clip(rng.binomial(3, np.clip((100 - product_usage) / 180, .02, .65)), 0, 3)
    nps = np.clip(np.rint(rng.normal(2.5 + product_usage / 15 - support_tickets * .18, 2.0)), 0, 10).astype(int)

    usage_risk = 100 - product_usage
    trend_risk = np.clip(-usage_change, 0, 100)
    support_risk = np.clip(support_tickets / 8 * 100, 0, 100)
    payment_risk = np.clip(payment_failures / 3 * 100, 0, 100)
    nps_risk = (10 - nps) * 10
    risk_score = (
        .30 * usage_risk + .20 * trend_risk + .15 * support_risk
        + .20 * payment_risk + .15 * nps_risk
    )
    base_hazard = np.select([plan == "Starter", plan == "Growth"], [.045, .027], default=.016)
    hazard = np.clip(base_hazard * (.45 + 1.2 * risk_score / 100), .002, .15)
    exposure = np.maximum(1, ((end_ts - signup).days / 30.4375).astype(int))
    churned = rng.random(n_customers) < (1 - np.power(1 - hazard, exposure))
    offsets = [rng.integers(1, max(2, m + 1)) if c else 0 for c, m in zip(churned, exposure)]
    churn_date = [min(s + pd.DateOffset(months=int(o)), end_ts) if o else pd.NaT for s, o in zip(signup, offsets)]
    reason = rng.choice(["Price", "Missing features", "Low usage", "Service issue", "Other"], n_customers)
    return pd.DataFrame({
        "customer_id": [f"C{i:06d}" for i in range(1, n_customers + 1)],
        "signup_date": pd.to_datetime(signup), "plan": plan, "monthly_price": prices,
        "status": np.where(churned, "Churned", "Active"), "churn_date": pd.to_datetime(churn_date),
        "churn_reason": np.where(churned, reason, "Not applicable"),
        "acquisition_channel": rng.choice(["Organic", "Paid Search", "Partner", "Referral"], n_customers),
        "industry": rng.choice(["Technology", "Healthcare", "Retail", "Finance", "Education"], n_customers),
        "seats": np.where(plan == "Starter", rng.integers(1, 4, n_customers), rng.integers(3, 30, n_customers)),
        "product_usage_score": product_usage, "usage_change_pct": usage_change,
        "support_tickets_90d": support_tickets, "payment_failures_90d": payment_failures,
        "nps_score": nps,
    }).sort_values("signup_date").reset_index(drop=True)


if __name__ == "__main__":
    output = Path("data/raw/subscriptions.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    generate_subscriptions().to_csv(output, index=False)
    print(f"Wrote synthetic data to {output}")
