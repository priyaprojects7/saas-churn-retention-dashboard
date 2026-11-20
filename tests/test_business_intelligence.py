import pandas as pd

from src.metrics.business_intelligence import (
    detect_metric_changes, forecast_metric, segment_revenue_change,
)


def test_segment_revenue_change_compares_month_end_snapshots():
    data = pd.DataFrame({
        "plan": ["Basic", "Basic", "Pro"],
        "signup_date": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-01"]),
        "churn_date": pd.to_datetime(["2024-02-10", None, None]),
        "monthly_price": [100, 100, 300],
    })
    result = segment_revenue_change(data, "2024-01-01", "2024-02-01", "plan")
    basic = result[result.plan.eq("Basic")].iloc[0]
    assert basic.previous_revenue == 200
    assert basic.current_revenue == 100
    assert basic.change == -100


def test_forecast_returns_requested_months_and_nonnegative_estimates():
    metrics = pd.DataFrame({
        "month": pd.date_range("2024-01-01", periods=12, freq="MS"),
        "mrr": [1000 + 100 * i for i in range(12)],
    })
    result = forecast_metric(metrics, "mrr", 4)
    assert len(result) == 4
    assert result.forecast.ge(0).all()
    assert result.lower_estimate.le(result.forecast).all()
    assert result.upper_estimate.ge(result.forecast).all()


def test_change_detector_flags_large_drop():
    metrics = pd.DataFrame({
        "month": pd.date_range("2024-01-01", periods=8, freq="MS"),
        "mrr": [1000, 1010, 1005, 1015, 1008, 1012, 1009, 700],
    })
    result = detect_metric_changes(metrics)
    assert bool(result.iloc[-1].unusual)
