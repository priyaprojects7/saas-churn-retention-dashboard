from pathlib import Path
import numpy as np
import pandas as pd

def generate_subscriptions(n_customers=2500,start="2023-01-01",end="2025-12-31",seed=42):
    """Generate deterministic synthetic subscription records."""
    rng=np.random.default_rng(seed)
    start_ts,end_ts=pd.Timestamp(start),pd.Timestamp(end)
    days=max(1,(end_ts-start_ts).days)
    signup=start_ts+pd.to_timedelta(rng.integers(0,days,n_customers),unit="D")
    plan=rng.choice(["Starter","Growth","Enterprise"],n_customers,p=[.55,.32,.13])
    prices=pd.Series(plan).map({"Starter":49.0,"Growth":149.0,"Enterprise":499.0}).to_numpy()
    hazard=np.select([plan=="Starter",plan=="Growth"],[.045,.027],default=.016)
    exposure=np.maximum(1,((end_ts-signup).days/30.4375).astype(int))
    churned=rng.random(n_customers)<(1-np.power(1-hazard,exposure))
    offsets=[rng.integers(1,max(2,m+1)) if c else 0 for c,m in zip(churned,exposure)]
    churn_date=[min(s+pd.DateOffset(months=int(o)),end_ts) if o else pd.NaT for s,o in zip(signup,offsets)]
    reason=rng.choice(["Price","Missing features","Low usage","Service issue","Other"],n_customers)
    return pd.DataFrame({
        "customer_id":[f"C{i:06d}" for i in range(1,n_customers+1)],
        "signup_date":pd.to_datetime(signup),"plan":plan,"monthly_price":prices,
        "status":np.where(churned,"Churned","Active"),"churn_date":pd.to_datetime(churn_date),
        "churn_reason":np.where(churned,reason,"Not applicable"),
        "acquisition_channel":rng.choice(["Organic","Paid Search","Partner","Referral"],n_customers),
        "industry":rng.choice(["Technology","Healthcare","Retail","Finance","Education"],n_customers),
        "seats":np.where(plan=="Starter",rng.integers(1,4,n_customers),rng.integers(3,30,n_customers))
    }).sort_values("signup_date").reset_index(drop=True)

if __name__=="__main__":
    out=Path("data/raw/subscriptions.csv")
    out.parent.mkdir(parents=True,exist_ok=True)
    generate_subscriptions().to_csv(out,index=False)
    print(f"Wrote synthetic data to {out}")
