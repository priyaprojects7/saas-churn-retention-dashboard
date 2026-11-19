from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data.generate import generate_subscriptions
from src.metrics.subscription_metrics import monthly_metrics, cohort_retention, what_if_revenue, validate_subscriptions
from src.pipeline.build_warehouse import run_pipeline

st.set_page_config(page_title="SaaS Retention Intelligence", layout="wide")
st.title("SaaS Churn & Retention Intelligence")
st.caption("Executive view of recurring revenue, customer retention, and churn scenarios.")

if not (ROOT / "data/warehouse/fact_subscription_monthly.csv").exists():
    run_pipeline()

uploaded = st.sidebar.file_uploader("Upload subscriptions CSV", type=["csv"])
data_path = ROOT / "data/raw/subscriptions.csv"
if uploaded:
    df = pd.read_csv(uploaded, parse_dates=["signup_date", "churn_date"])
elif data_path.exists():
    df = pd.read_csv(data_path, parse_dates=["signup_date", "churn_date"])
else:
    df = generate_subscriptions()
    data_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(data_path, index=False)

try:
    validate_subscriptions(df)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

if "plan" in df:
    options = sorted(df.plan.unique())
    selected = st.sidebar.multiselect("Plan", options, default=options)
    df = df[df.plan.isin(selected)]

m = monthly_metrics(df)
if m.empty:
    st.warning("No records for these filters.")
    st.stop()
latest = m.iloc[-1]
a,b,c,d = st.columns(4)
a.metric("Active customers", f"{int(latest.active_customers):,}")
b.metric("MRR", f"${latest.mrr:,.0f}")
c.metric("Monthly churn", f"{latest.monthly_churn_rate:.1%}")
d.metric("ARPA", f"${latest.arpa:,.2f}")

overview, cohorts, drivers, scenario = st.tabs(["Executive overview","Cohorts","Churn drivers","What-if scenario"])
with overview:
    left,right = st.columns(2)
    left.plotly_chart(px.line(m,x="month",y="mrr",markers=True,title="Monthly recurring revenue"),use_container_width=True)
    right.plotly_chart(px.line(m,x="month",y="active_customers",markers=True,title="Active customers"),use_container_width=True)
    st.plotly_chart(px.line(m,x="month",y="monthly_churn_rate",markers=True,title="Monthly churn rate"),use_container_width=True)
    st.download_button("Download monthly metrics",m.to_csv(index=False),"monthly_metrics.csv")
with cohorts:
    matrix = cohort_retention(df)
    st.plotly_chart(px.imshow(matrix,aspect="auto",color_continuous_scale="Blues",labels={"x":"Months since signup","y":"Signup cohort","color":"Retention"}),use_container_width=True)
    st.download_button("Download cohort matrix",matrix.to_csv(),"cohort_retention.csv")
with drivers:
    churned = df[df.status.eq("Churned")]
    if "churn_reason" in churned:
        counts = churned.churn_reason.value_counts().rename_axis("reason").reset_index(name="customers")
        st.plotly_chart(px.bar(counts,x="reason",y="customers",title="Churn reasons"),use_container_width=True)
    st.dataframe(churned.groupby(["plan","churn_reason"]).size().reset_index(name="customers"),use_container_width=True)
with scenario:
    reduction = st.slider("Monthly churn reduction (percentage points)",0.0,5.0,2.0,0.5)
    horizon = st.slider("Scenario horizon (months)",3,24,12)
    churn = float(m.monthly_churn_rate.tail(3).mean())
    result = what_if_revenue(int(latest.active_customers),float(latest.arpa),churn,reduction,horizon)
    x,y,z = st.columns(3)
    x.metric("Baseline modeled revenue",f"${result['baseline_revenue']:,.0f}")
    y.metric("Scenario modeled revenue",f"${result['scenario_revenue']:,.0f}")
    z.metric("Incremental modeled revenue",f"${result['incremental_revenue']:,.0f}")
    st.caption("Illustrative scenario only: constant ARPA and churn, no acquisition, no discounting. Not realized savings or a forecast.")
