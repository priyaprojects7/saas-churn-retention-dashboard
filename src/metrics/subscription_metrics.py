import numpy as np
import pandas as pd

REQUIRED={"customer_id","signup_date","monthly_price","status","churn_date"}

def validate_subscriptions(df):
    missing=REQUIRED-set(df.columns)
    if missing: raise ValueError(f"Missing required columns: {sorted(missing)}")
    if df.customer_id.duplicated().any(): raise ValueError("customer_id must be unique")
    if (df.monthly_price<0).any(): raise ValueError("monthly_price cannot be negative")

def monthly_metrics(df):
    """Build monthly customer, MRR, ARPA, and churn metrics."""
    validate_subscriptions(df)
    d=df.copy()
    d["signup_date"]=pd.to_datetime(d.signup_date)
    d["churn_date"]=pd.to_datetime(d.churn_date)
    first=d.signup_date.min().to_period("M").to_timestamp()
    last=max(d.signup_date.max(),d.churn_date.max() if d.churn_date.notna().any() else d.signup_date.max())
    months=pd.date_range(first,last.to_period("M").to_timestamp(),freq="MS")
    rows=[]
    for month in months:
        month_end=month+pd.offsets.MonthEnd(0)
        opening=(d.signup_date<month)&(d.churn_date.isna()|(d.churn_date>=month))
        active_mask=(d.signup_date<=month_end)&(d.churn_date.isna()|(d.churn_date>month_end))
        churned=int(d.churn_date.between(month,month_end).sum())
        active=int(active_mask.sum())
        mrr=float(d.loc[active_mask,"monthly_price"].sum())
        opening_count=int(opening.sum())
        rows.append({"month":month,"active_customers":active,"mrr":mrr,
          "arpa":mrr/active if active else 0.0,
          "new_customers":int(d.signup_date.between(month,month_end).sum()),
          "churned_customers":churned,
          "monthly_churn_rate":churned/opening_count if opening_count else 0.0})
    return pd.DataFrame(rows)

def cohort_retention(df):
    """Return a cohort-by-age retention matrix."""
    validate_subscriptions(df)
    d=df.copy()
    d["signup_date"]=pd.to_datetime(d.signup_date)
    d["churn_date"]=pd.to_datetime(d.churn_date)
    d["cohort"]=d.signup_date.dt.to_period("M")
    d["churn_month"]=d.churn_date.dt.to_period("M")
    rows=[]
    latest=d.signup_date.max().to_period("M")+24
    for cohort,group in d.groupby("cohort"):
        for age in range(25):
            period=cohort+age
            if period>latest: break
            lost=(group.churn_month.notna()&(group.churn_month<=period)).sum()
            rows.append({"cohort":str(cohort),"age_month":age,"retention":(len(group)-int(lost))/len(group)})
    return pd.DataFrame(rows).pivot(index="cohort",columns="age_month",values="retention")

def estimate_ltv(arpa,monthly_churn):
    """Simple LTV proxy; excludes margin, discounting, and expansion."""
    if arpa<0 or monthly_churn<0: raise ValueError("Inputs must be non-negative")
    return float("nan") if monthly_churn==0 else arpa/monthly_churn

def what_if_revenue(active_customers,arpa,monthly_churn,reduction_pp=2.0,months=12):
    """Compare modeled retained subscription revenue under lower monthly churn."""
    if active_customers<0 or arpa<0 or months<1: raise ValueError("Invalid scenario inputs")
    if not 0<=monthly_churn<=1: raise ValueError("monthly_churn must be between 0 and 1")
    improved=max(0.0,monthly_churn-reduction_pp/100)
    periods=np.arange(1,months+1)
    base=float((active_customers*(1-monthly_churn)**periods).sum()*arpa)
    scenario=float((active_customers*(1-improved)**periods).sum()*arpa)
    return {"baseline_revenue":base,"scenario_revenue":scenario,
      "incremental_revenue":scenario-base,"scenario_churn_rate":improved}
