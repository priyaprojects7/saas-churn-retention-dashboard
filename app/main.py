from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data.generate import generate_subscriptions
from src.metrics.subscription_metrics import monthly_metrics, cohort_retention, what_if_revenue, validate_subscriptions
from src.metrics.customer_health import score_customer_health, retention_opportunity
from src.pipeline.build_warehouse import run_pipeline

st.set_page_config(page_title="SaaS Retention Command Center", page_icon="📈", layout="wide")
st.title("SaaS Retention Command Center")
st.caption("Find accounts at risk, understand why they may leave, and prioritize the next retention action.")

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
    selected = st.sidebar.multiselect("Subscription plan", options, default=options)
    df = df[df.plan.isin(selected)]

metrics = monthly_metrics(df)
if metrics.empty:
    st.warning("No records for these filters.")
    st.stop()
latest = metrics.iloc[-1]
scored = score_customer_health(df)
active_scored = scored[scored.status.eq("Active")].copy()
overview, command, cohorts, drivers, scenario = st.tabs([
    "Executive overview", "Retention command center", "Cohort retention",
    "Churn drivers", "Revenue simulator"
])

with overview:
    st.subheader("Subscription business health")
    a,b,c,d = st.columns(4)
    a.metric("Active customers", f"{int(latest.active_customers):,}")
    b.metric("Monthly recurring revenue", f"${latest.mrr:,.0f}")
    c.metric("Monthly churn", f"{latest.monthly_churn_rate:.1%}")
    d.metric("Average revenue per account", f"${latest.arpa:,.2f}")
    left,right = st.columns(2)
    left.plotly_chart(px.line(metrics,x="month",y="mrr",markers=True,title="Monthly recurring revenue"),use_container_width=True)
    right.plotly_chart(px.line(metrics,x="month",y="active_customers",markers=True,title="Active customers"),use_container_width=True)
    st.plotly_chart(px.line(metrics,x="month",y="monthly_churn_rate",markers=True,title="Monthly churn rate"),use_container_width=True)
    st.download_button("Download monthly metrics",metrics.to_csv(index=False),"monthly_metrics.csv")

with command:
    st.subheader("Who should the customer-success team contact first?")
    st.write("An explainable health score combines product usage, usage trend, support burden, payment failures, and NPS. Higher scores mean higher modeled churn risk.")
    opportunity = retention_opportunity(scored, 100, 30)
    a,b,c = st.columns(3)
    a.metric("High-risk active accounts", f"{opportunity['high_risk_customers']:,}")
    b.metric("Risk-adjusted monthly revenue", f"${opportunity['revenue_at_risk']:,.0f}")
    c.metric("Accounts assessed", f"{len(active_scored):,}")
    high = active_scored[active_scored.risk_band.eq("High")].sort_values("revenue_at_risk",ascending=False)
    if high.empty:
        st.info("No high-risk accounts in the current sample and filters.")
    else:
        st.plotly_chart(px.histogram(active_scored,x="risk_band",color="risk_band",category_orders={"risk_band":["Low","Medium","High"]},title="Active account risk distribution"),use_container_width=True)
        view = high[["customer_id","plan","monthly_price","risk_score","revenue_at_risk","product_usage_score","usage_change_pct","support_tickets_90d","payment_failures_90d","nps_score","recommended_action"]]
        st.dataframe(view.head(50),use_container_width=True,hide_index=True)
        st.download_button("Export prioritized retention queue",view.to_csv(index=False),"retention_action_queue.csv")
    st.markdown("**How the score works**")
    st.caption("30% product usage · 20% usage decline · 15% support burden · 20% payment failures · 15% NPS. This is a transparent heuristic, not a trained or validated prediction model.")

with cohorts:
    st.subheader("Do customers stay after they sign up?")
    matrix = cohort_retention(df)
    st.plotly_chart(px.imshow(matrix,aspect="auto",color_continuous_scale="Blues",labels={"x":"Months since signup","y":"Signup cohort","color":"Retention"}),use_container_width=True)
    st.download_button("Download cohort matrix",matrix.to_csv(),"cohort_retention.csv")

with drivers:
    st.subheader("Why did customers cancel?")
    churned = df[df.status.eq("Churned")]
    if "churn_reason" in churned:
        counts = churned.churn_reason.value_counts().rename_axis("reason").reset_index(name="customers")
        st.plotly_chart(px.bar(counts,x="reason",y="customers",title="Reported churn reasons"),use_container_width=True)
    st.dataframe(churned.groupby(["plan","churn_reason"]).size().reset_index(name="customers"),use_container_width=True)

with scenario:
    st.subheader("Retention intervention simulator")
    st.write("Estimate the possible value of a targeted retention campaign. These assumptions are editable and illustrative.")
    coverage = st.slider("Share of high-risk accounts contacted",0,100,80,5)
    save_rate = st.slider("Assumed save rate among contacted accounts",0,100,25,5)
    result = retention_opportunity(scored,coverage,save_rate)
    x,y,z = st.columns(3)
    x.metric("Revenue at risk",f"${result['revenue_at_risk']:,.0f}")
    y.metric("Accounts to contact",f"{round(result['high_risk_customers']*coverage/100):,}")
    z.metric("Modeled revenue retained",f"${result['modeled_revenue_retained']:,.0f}")
    st.caption("This is a what-if estimate using a rule-based risk score and an assumed save rate. It is not a causal impact estimate, forecast, or guaranteed saving.")
