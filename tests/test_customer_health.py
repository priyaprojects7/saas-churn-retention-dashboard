import pandas as pd
import pytest
from src.metrics.customer_health import score_customer_health, retention_opportunity


def test_low_usage_and_failed_payments_raise_risk():
    frame = pd.DataFrame([
        {"customer_id":"A","status":"Active","monthly_price":100,"product_usage_score":85,
         "usage_change_pct":5,"support_tickets_90d":0,"payment_failures_90d":0,"nps_score":9},
        {"customer_id":"B","status":"Active","monthly_price":100,"product_usage_score":10,
         "usage_change_pct":-70,"support_tickets_90d":8,"payment_failures_90d":3,"nps_score":1},
    ])
    scored = score_customer_health(frame)
    assert scored.iloc[1].risk_score > scored.iloc[0].risk_score
    assert scored.iloc[1].risk_band == "High"


def test_retention_opportunity_is_bounded_and_excludes_churned():
    frame = pd.DataFrame([
        {"customer_id":"A","status":"Active","monthly_price":100,"product_usage_score":5,
         "usage_change_pct":-80,"support_tickets_90d":8,"payment_failures_90d":3,"nps_score":0},
        {"customer_id":"B","status":"Churned","monthly_price":200,"product_usage_score":5,
         "usage_change_pct":-80,"support_tickets_90d":8,"payment_failures_90d":3,"nps_score":0},
    ])
    result = retention_opportunity(score_customer_health(frame),100,50)
    assert result["high_risk_customers"] == 1
    assert result["modeled_revenue_retained"] <= result["revenue_at_risk"]


def test_invalid_scenario_inputs_rejected():
    with pytest.raises(ValueError):
        retention_opportunity(pd.DataFrame(),120,20)
