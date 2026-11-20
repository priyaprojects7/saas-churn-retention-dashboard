"""Business investigation helpers for the portfolio demo.

All calculations are descriptive or simple trend estimates. They do not establish
causality and should be reviewed before business decisions are made.
"""
import numpy as np
import pandas as pd


def segment_revenue_change(df: pd.DataFrame, current_month, previous_month, dimension: str) -> pd.DataFrame:
    """Compare active subscription revenue by a segment for two month-end snapshots."""
    if dimension not in df.columns:
        return pd.DataFrame(columns=[dimension, "current_revenue", "previous_revenue", "change", "change_pct"])
    data = df.copy()
    data["signup_date"] = pd.to_datetime(data["signup_date"])
    data["churn_date"] = pd.to_datetime(data["churn_date"], errors="coerce")
    rows = []
    for label, group in data.groupby(dimension, dropna=False):
        values = []
        for month in (previous_month, current_month):
            month_end = pd.Timestamp(month) + pd.offsets.MonthEnd(0)
            active = (
                group["signup_date"].le(month_end)
                & (group["churn_date"].isna() | group["churn_date"].gt(month_end))
            )
            values.append(float(group.loc[active, "monthly_price"].sum()))
        previous, current = values
        rows.append({
            dimension: "Not recorded" if pd.isna(label) else str(label),
            "current_revenue": current,
            "previous_revenue": previous,
            "change": current - previous,
            "change_pct": ((current - previous) / previous * 100) if previous else np.nan,
        })
    return pd.DataFrame(rows).sort_values("change")


def forecast_metric(metrics: pd.DataFrame, column: str = "mrr", periods: int = 6) -> pd.DataFrame:
    """Fit a transparent linear trend to recent monthly observations."""
    if periods < 1:
        raise ValueError("periods must be at least 1")
    clean = metrics[["month", column]].dropna().copy()
    if len(clean) < 6:
        raise ValueError("At least six monthly observations are needed for a trend estimate")
    clean = clean.tail(18).reset_index(drop=True)
    y = pd.to_numeric(clean[column], errors="coerce").to_numpy(dtype=float)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = intercept + slope * x
    residuals = y - fitted
    error = float(np.sqrt(np.sum(residuals ** 2) / max(1, len(y) - 2)))
    future_x = np.arange(len(y), len(y) + periods, dtype=float)
    prediction = np.maximum(0, intercept + slope * future_x)
    # A simple widening range, not a formal statistical prediction interval.
    horizon = np.arange(1, periods + 1, dtype=float)
    spread = 1.96 * error * np.sqrt(1 + horizon / len(y))
    future_dates = pd.date_range(
        pd.Timestamp(clean["month"].iloc[-1]) + pd.offsets.MonthBegin(1),
        periods=periods, freq="MS"
    )
    return pd.DataFrame({
        "month": future_dates,
        "forecast": prediction,
        "lower_estimate": np.maximum(0, prediction - spread),
        "upper_estimate": prediction + spread,
    })


def detect_metric_changes(metrics: pd.DataFrame, column: str = "mrr") -> pd.DataFrame:
    """Flag unusually large month-over-month changes using a robust historical threshold."""
    result = metrics[["month", column]].copy()
    result["change"] = result[column].diff()
    result["change_pct"] = result[column].pct_change() * 100
    changes = result["change_pct"].replace([np.inf, -np.inf], np.nan).dropna()
    if len(changes) < 4:
        result["unusual"] = False
        result["threshold_pct"] = np.nan
        return result
    median = float(changes.median())
    mad = float((changes - median).abs().median())
    threshold = max(10.0, 3.0 * 1.4826 * mad)
    result["unusual"] = result["change_pct"].abs().gt(threshold)
    result["threshold_pct"] = threshold
    return result
