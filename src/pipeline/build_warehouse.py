from pathlib import Path
import json
import pandas as pd
from src.data.generate import generate_subscriptions

RAW=Path("data/raw")
PROCESSED=Path("data/processed")
WAREHOUSE=Path("data/warehouse")

def create_raw_sources(seed=42):
    base=generate_subscriptions(n_customers=2500,seed=seed)
    customers=base[["customer_id","acquisition_channel","industry"]].copy()
    subs=base[["customer_id","signup_date","plan","monthly_price","status","churn_date","churn_reason","seats"]].copy()
    events=base[["customer_id","signup_date"]].rename(columns={"signup_date":"event_date"})
    events["event_type"]="subscription_started"
    events["source_system"]="billing_api"
    customers.loc[0,"industry"]=None
    customers.loc[1,"acquisition_channel"]=" paid search "
    subs.loc[2,"monthly_price"]=-10
    subs.loc[3,"plan"]="growth "
    subs=pd.concat([subs,subs.iloc[[4]]],ignore_index=True)
    events.loc[5,"event_date"]="not-a-date"
    events=pd.concat([events,events.iloc[[6]]],ignore_index=True)
    return {"customers_raw":customers,"subscriptions_raw":subs,"events_raw":events}

def clean_and_model(sources):
    customers=sources["customers_raw"].copy()
    subs=sources["subscriptions_raw"].copy()
    events=sources["events_raw"].copy()
    report={"source_rows":{k:int(len(v)) for k,v in sources.items()},"issues_detected":{},"rows_after_cleaning":{}}
    report["issues_detected"]={
      "duplicate_subscription_rows":int(subs.duplicated().sum()),
      "invalid_negative_prices":int((pd.to_numeric(subs.monthly_price,errors="coerce")<0).sum()),
      "missing_customer_industry":int(customers.industry.isna().sum()),
      "invalid_event_dates":int(pd.to_datetime(events.event_date,errors="coerce").isna().sum()),
      "noncanonical_plan_values":int((subs.plan.astype(str)!=subs.plan.astype(str).str.strip().str.title()).sum())}
    customers["acquisition_channel"]=customers.acquisition_channel.astype("string").str.strip().str.title()
    customers["industry"]=customers.industry.fillna("Unknown")
    customers=customers.drop_duplicates(subset=["customer_id"],keep="last").reset_index(drop=True)
    subs["plan"]=subs.plan.astype("string").str.strip().str.title()
    subs["monthly_price"]=pd.to_numeric(subs.monthly_price,errors="coerce")
    subs["signup_date"]=pd.to_datetime(subs.signup_date,errors="coerce")
    subs["churn_date"]=pd.to_datetime(subs.churn_date,errors="coerce")
    subs=subs.drop_duplicates()
    subs=subs[subs.monthly_price.notna()&(subs.monthly_price>=0)]
    subs=subs[subs.signup_date.notna()]
    events["event_date"]=pd.to_datetime(events.event_date,errors="coerce")
    events=events.dropna(subset=["event_date"]).drop_duplicates()
    customers["customer_key"]=customers.index+1
    customer_dim=customers[["customer_key","customer_id","acquisition_channel","industry"]]
    plan_dim=pd.DataFrame([
      {"plan_key":1,"plan":"Starter","list_monthly_price":49.0},
      {"plan_key":2,"plan":"Growth","list_monthly_price":149.0},
      {"plan_key":3,"plan":"Enterprise","list_monthly_price":499.0}])
    subs=subs[subs.customer_id.isin(customer_dim.customer_id)]
    subs=subs.merge(customer_dim[["customer_key","customer_id"]],on="customer_id")
    subs=subs.merge(plan_dim[["plan_key","plan"]],on="plan",how="left")
    subs=subs[subs.plan_key.notna()].copy()
    subs["plan_key"]=subs.plan_key.astype(int)
    first=subs.signup_date.min().to_period("M")
    last=max(subs.signup_date.max(),subs.churn_date.max() if subs.churn_date.notna().any() else subs.signup_date.max()).to_period("M")
    periods=pd.period_range(first,last,freq="M")
    fact_rows=[]
    for period in periods:
        month_end=period.end_time.normalize()
        active=(subs.signup_date<=month_end)&(subs.churn_date.isna()|(subs.churn_date>month_end))
        for row in subs.loc[active].itertuples():
            fact_rows.append({"month_key":int(period.strftime("%Y%m")),"customer_key":int(row.customer_key),
              "plan_key":int(row.plan_key),"active_customer_count":1,"mrr_amount":float(row.monthly_price),"seats":int(row.seats)})
    fact=pd.DataFrame(fact_rows)
    date_dim=pd.DataFrame([{"month_key":int(p.strftime("%Y%m")),"month_start":p.start_time.date().isoformat(),
      "calendar_year":p.year,"calendar_quarter":f"Q{p.quarter}","month_number":p.month,"month_name":p.strftime("%B")} for p in periods])
    report["rows_after_cleaning"]={"dim_customer":int(len(customer_dim)),"dim_plan":int(len(plan_dim)),
      "dim_month":int(len(date_dim)),"fact_subscription_monthly":int(len(fact)),"events_clean":int(len(events))}
    report["notes"]=["Synthetic source data includes duplicate, null, malformed, noncanonical, and negative-value examples.",
      "Negative monthly prices are excluded from the modeled fact.","The fact is a month-end active-subscription snapshot.",
      "The source data is synthetic and does not represent a real SaaS company."]
    for folder in (RAW,PROCESSED,WAREHOUSE): folder.mkdir(parents=True,exist_ok=True)
    customers.to_csv(PROCESSED/"customers_clean.csv",index=False)
    subs.to_csv(PROCESSED/"subscriptions_clean.csv",index=False)
    events.to_csv(PROCESSED/"events_clean.csv",index=False)
    customer_dim.to_csv(WAREHOUSE/"dim_customer.csv",index=False)
    plan_dim.to_csv(WAREHOUSE/"dim_plan.csv",index=False)
    date_dim.to_csv(WAREHOUSE/"dim_month.csv",index=False)
    fact.to_csv(WAREHOUSE/"fact_subscription_monthly.csv",index=False)
    (PROCESSED/"data_quality_report.json").write_text(json.dumps(report,indent=2))
    return report

def run_pipeline():
    sources=create_raw_sources()
    for name,frame in sources.items():
        RAW.mkdir(parents=True,exist_ok=True)
        frame.to_csv(RAW/f"{name}.csv",index=False)
    return clean_and_model(sources)

if __name__=="__main__":
    print(json.dumps(run_pipeline(),indent=2))
