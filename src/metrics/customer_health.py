"""Explainable customer health scoring and retention action recommendations."""
import numpy as np
import pandas as pd

def score_customer_health(df: pd.DataFrame) -> pd.DataFrame:
    """Score customer risk from 0 (lower risk) to 100 (higher risk)."""
    result = df.copy()
    defaults = {
        "product_usage_score": 50.0, "usage_change_pct": 0.0,
        "support_tickets_90d": 1, "payment_failures_90d": 0, "nps_score": 5,
    }
    for column, default in defaults.items():
        if column not in result:
            result[column] = default
    usage_risk = 100 - pd.to_numeric(result.product_usage_score, errors="coerce").fillna(50).clip(0, 100)
    trend_risk = (-pd.to_numeric(result.usage_change_pct, errors="coerce").fillna(0)).clip(0, 100)
    support_risk = (pd.to_numeric(result.support_tickets_90d, errors="coerce").fillna(1).clip(0, 15) / 8 * 100).clip(0, 100)
    payment_risk = (pd.to_numeric(result.payment_failures_90d, errors="coerce").fillna(0).clip(0, 3) / 3 * 100)
    nps_risk = (10 - pd.to_numeric(result.nps_score, errors="coerce").fillna(5).clip(0, 10)) * 10
    result["risk_score"] = (
        .30 * usage_risk + .20 * trend_risk + .15 * support_risk
        + .20 * payment_risk + .15 * nps_risk
    ).round(1)
    result["risk_band"] = pd.cut(
        result.risk_score, bins=[-0.01, 34, 64, 100],
        labels=["Low", "Medium", "High"]
    ).astype(str)
    result["revenue_at_risk"] = (
        pd.to_numeric(result.monthly_price, errors="coerce").fillna(0)
        * result.risk_score / 100
    ).round(2)
    result["recommended_action"] = result.apply(_next_best_action, axis=1)
    return result


def _next_best_action(row):
    if row.get("status") != "Active":
        return "No action · already churned"
    if row.get("payment_failures_90d", 0) >= 2:
        return "Payment recovery · resolve failed billing"
    if row.get("support_tickets_90d", 0) >= 5:
        return "Service recovery · escalate support"
    if row.get("product_usage_score", 50) < 30 or row.get("usage_change_pct", 0) <= -30:
        return "Adoption rescue · guided onboarding"
    if row.get("nps_score", 5) <= 4:
        return "Customer success · personal check-in"
    return "Value review · reinforce product outcomes"


def retention_opportunity(scored: pd.DataFrame, outreach_coverage_pct: float, save_rate_pct: float) -> dict:
    """Illustrative scenario; not a causal estimate or guaranteed saved revenue."""
    if not 0 <= outreach_coverage_pct <= 100 or not 0 <= save_rate_pct <= 100:
        raise ValueError("Coverage and save rate must be between 0 and 100")
    active = scored[scored.status.eq("Active")].copy()
    high = active[active.risk_band.eq("High")]
    at_risk = float(high.revenue_at_risk.sum())
    modeled = at_risk * outreach_coverage_pct / 100 * save_rate_pct / 100
    return {
        "high_risk_customers": int(len(high)),
        "revenue_at_risk": at_risk,
        "modeled_revenue_retained": modeled,
        "outreach_coverage_pct": outreach_coverage_pct,
        "assumed_save_rate_pct": save_rate_pct,
    }
