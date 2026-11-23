from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data.generate import generate_subscriptions
from src.metrics.subscription_metrics import monthly_metrics, cohort_retention, validate_subscriptions
from src.metrics.customer_health import score_customer_health, retention_opportunity
from src.metrics.business_intelligence import segment_revenue_change, forecast_metric, detect_metric_changes

st.set_page_config(page_title="Business Investigation Workbench", page_icon="📊", layout="wide")
st.title("Business Investigation Workbench")
st.caption("Move from business data to an explanation, an estimate of what may happen next, and a decision someone can verify.")
st.info("Portfolio demo using synthetic subscription data. Forecasts and scenarios are estimates, not guarantees. The app does not prove that one factor caused another.")

uploaded = st.sidebar.file_uploader("Upload subscriptions CSV", type=["csv"])
st.sidebar.caption("Expected: one row per customer, with customer_id, signup_date, monthly_price, status and churn_date. Optional fields include plan, acquisition_channel, industry, product usage, support tickets, payment failures and NPS.")
data_path = ROOT / "data/raw/subscriptions.csv"
if uploaded:
    try:
        df = pd.read_csv(uploaded)
        for col in ["signup_date", "churn_date"]:
            if col in df:
                df[col] = pd.to_datetime(df[col], errors="coerce")
    except Exception as exc:
        st.error(f"Could not read this CSV: {exc}")
        st.stop()
elif data_path.exists():
    df = pd.read_csv(data_path, parse_dates=["signup_date", "churn_date"])
else:
    df = generate_subscriptions()

try:
    validate_subscriptions(df)
except (ValueError, KeyError, TypeError) as exc:
    st.error(f"The data needs attention before analysis: {exc}")
    st.stop()

if "plan" in df:
    options = sorted(df.plan.dropna().unique())
    selected = st.sidebar.multiselect("Subscription plan", options, default=options)
    df = df[df.plan.isin(selected)]

metrics = monthly_metrics(df)
if metrics.empty:
    st.warning("There are no records for the selected filters.")
    st.stop()
latest = metrics.iloc[-1]
previous = metrics.iloc[-2] if len(metrics) > 1 else None
scored = score_customer_health(df)
active_scored = scored[scored.status.eq("Active")].copy()

def money(value):
    return "$" + format(value, ",.0f")

overview, investigate, forecast_tab, alerts, command, cohorts, decisions, briefing = st.tabs([
    "Business overview", "Why did it change?", "What happens next?", "Early warnings",
    "Customer actions", "Customer retention", "What-if decisions", "Business briefing"
])

with overview:
    st.subheader("Current business position")
    a, b, c, d = st.columns(4)
    a.metric("Active customers", f"{int(latest.active_customers):,}", delta=(int(latest.active_customers - previous.active_customers) if previous is not None else None))
    b.metric("Monthly recurring revenue", money(latest.mrr), delta=(money(latest.mrr - previous.mrr) if previous is not None else None))
    c.metric("Monthly churn", f"{latest.monthly_churn_rate:.1%}")
    d.metric("Average revenue per customer", money(latest.arpa))
    st.caption("MRR is recurring subscription revenue at month end. Churn is the share of customers active at the start of the month who cancelled during it.")
    left, right = st.columns(2)
    left.plotly_chart(px.line(metrics, x="month", y="mrr", markers=True, title="Monthly recurring revenue"), use_container_width=True)
    right.plotly_chart(px.line(metrics, x="month", y="active_customers", markers=True, title="Active customers"), use_container_width=True)
    st.plotly_chart(px.line(metrics, x="month", y="monthly_churn_rate", markers=True, title="Monthly customer churn"), use_container_width=True)
    st.download_button("Download monthly business metrics", metrics.to_csv(index=False), "monthly_metrics.csv")

with investigate:
    st.subheader("Investigate a change in the business")
    st.write("Choose a measure and a business area. The app compares the latest month with the month before it and shows which groups contributed most to the change.")
    if previous is None:
        st.warning("At least two months are needed to investigate a change.")
    else:
        measure = st.selectbox("What changed?", ["Monthly recurring revenue", "Active customers", "Monthly churn rate"])
        dims = [c for c in ["plan", "acquisition_channel", "industry"] if c in df.columns]
        if not dims:
            st.warning("Add a plan, acquisition_channel or industry column to investigate differences between groups.")
        else:
            dimension = st.selectbox("Break it down by", dims, format_func=lambda x: x.replace("_", " ").title())
            if measure == "Monthly recurring revenue":
                breakdown = segment_revenue_change(df, latest.month, previous.month, dimension)
                delta = float(latest.mrr - previous.mrr)
                st.metric("Overall MRR change", money(delta))
                st.write("Groups with the largest declines appear first. A group's change is its current recurring revenue minus its previous-month recurring revenue.")
                display = breakdown.rename(columns={dimension: "Group", "current_revenue": "Current MRR", "previous_revenue": "Previous MRR", "change": "Change", "change_pct": "Change %"})
                st.dataframe(display.style.format({"Current MRR": "$" + "{:,.0f}", "Previous MRR": "$" + "{:,.0f}", "Change": "$" + "{:,.0f}", "Change %": "{:.1f}%"}), use_container_width=True, hide_index=True)
                if not breakdown.empty:
                    worst = breakdown.iloc[0]
                    if worst["change"] < 0:
                        st.warning(f"{worst[dimension]} had the largest decline: {money(worst['change'])}. This identifies where to investigate; it does not prove why the decline happened.")
                    else:
                        st.success("No segment in this breakdown had a revenue decline.")
                    st.plotly_chart(px.bar(breakdown, x=dimension, y="change", title="MRR change by group", labels={"change": "Change in MRR"}), use_container_width=True)
            elif measure == "Active customers":
                st.metric("Change in active customers", f"{int(latest.active_customers - previous.active_customers):+,}")
                st.write("Customer counts are compared at each month end. Segment-level customer movement is a planned extension.")
            else:
                st.metric("Change in churn rate", f"{latest.monthly_churn_rate - previous.monthly_churn_rate:+.1%}")
                st.write(f"Churn moved from {previous.monthly_churn_rate:.1%} to {latest.monthly_churn_rate:.1%}. Check Customer Retention for cancellation patterns and customer signals.")
    st.caption("Business impact is measured in subscription revenue and customer counts. Other effects, such as support cost or brand impact, are not included unless those data are supplied.")

with forecast_tab:
    st.subheader("Estimate what may happen next")
    st.write("This first version extends the recent trend. It is a baseline estimate, not a machine-learning model or a promise of future results.")
    choice = st.selectbox("Forecast", ["Monthly recurring revenue", "Active customers"])
    column = "mrr" if choice == "Monthly recurring revenue" else "active_customers"
    horizon = st.slider("Months to estimate", 3, 12, 6)
    try:
        projection = forecast_metric(metrics, column, horizon)
        history = metrics[["month", column]].rename(columns={column: "value"})
        history["series"] = "Historical"
        future = projection[["month", "forecast"]].rename(columns={"forecast": "value"})
        future["series"] = "Trend estimate"
        combined = pd.concat([history, future], ignore_index=True)
        st.plotly_chart(px.line(combined, x="month", y="value", color="series", markers=True, title=f"{choice}: history and trend estimate"), use_container_width=True)
        shown = projection.rename(columns={"month": "Month", "forecast": "Expected", "lower_estimate": "Lower estimate", "upper_estimate": "Upper estimate"})
        st.dataframe(shown.style.format({"Expected": "{:,.0f}", "Lower estimate": "{:,.0f}", "Upper estimate": "{:,.0f}"}), use_container_width=True, hide_index=True)
        st.caption("The estimate range is based on past trend errors, not a formal guarantee. Seasonality, market changes, pricing and new customer activity can make the estimate wrong.")
    except ValueError as exc:
        st.warning(str(exc))

with alerts:
    st.subheader("Early warning signals")
    st.write("These checks flag unusually large month-to-month movements. They help decide where to look; they do not identify the cause.")
    alert_data = detect_metric_changes(metrics, "mrr")
    unusual = alert_data[alert_data.unusual]
    if unusual.empty:
        st.success("No unusually large MRR changes were flagged by the current rule.")
    else:
        for _, item in unusual.iterrows():
            direction = "increased" if item.change > 0 else "decreased"
            st.warning(f"{pd.Timestamp(item.month).strftime('%B %Y')}: MRR {direction} by {abs(item.change_pct):.1f}% ({money(item.change)}). Review the investigation tab for segment breakdowns.")
    st.dataframe(alert_data.tail(12).rename(columns={"month": "Month", "mrr": "MRR", "change": "Dollar change", "change_pct": "Percent change", "unusual": "Flagged"}), use_container_width=True, hide_index=True)
    st.caption("The flag uses the historical median and spread of percentage changes, with a minimum 10% threshold. It is a screening rule, not a trained anomaly detector.")

with command:
    st.subheader("Which customers need attention?")
    st.write("This ranks active accounts using product usage, usage decline, support tickets, failed payments and NPS. It is a rule-based score, not a validated prediction of who will cancel.")
    opportunity = retention_opportunity(scored, 100, 30)
    a, b, c = st.columns(3)
    a.metric("High-risk active accounts", f"{opportunity['high_risk_customers']:,}")
    b.metric("Risk-weighted monthly revenue", money(opportunity["revenue_at_risk"]))
    c.metric("Active accounts assessed", f"{len(active_scored):,}")
    with st.expander("How the customer risk score works"):
        st.markdown("The score runs from 0 to 100. It combines product usage (30%), recent usage decline (20%), support tickets (15%), failed payments (20%) and NPS (15%). Higher scores mean more warning signs under these hand-set rules.")
    if not active_scored.empty:
        bands = active_scored.risk_band.value_counts().reindex(["Low", "Medium", "High"], fill_value=0).rename_axis("Risk level").reset_index(name="Customers")
        st.plotly_chart(px.bar(bands, x="Risk level", y="Customers", title="Active customers by risk level"), use_container_width=True)
        high = active_scored[active_scored.risk_band.eq("High")].sort_values("revenue_at_risk", ascending=False)
        if not high.empty:
            cols = ["customer_id", "plan", "monthly_price", "risk_score", "revenue_at_risk", "product_usage_score", "usage_change_pct", "support_tickets_90d", "payment_failures_90d", "nps_score", "recommended_action"]
            st.dataframe(high[cols].head(50), use_container_width=True, hide_index=True)
            st.download_button("Export customer follow-up list", high[cols].to_csv(index=False), "customer_follow_up.csv")
        else:
            st.info("No active accounts are in the High-risk band under these rules.")
    st.caption("Risk-weighted revenue is monthly price multiplied by risk score. It is a prioritization aid, not revenue certain to be lost.")

with cohorts:
    st.subheader("Do customers stay after signing up?")
    matrix = cohort_retention(df)
    if matrix.empty:
        st.info("There is not enough signup history to build a cohort view.")
    else:
        st.plotly_chart(px.imshow(matrix, aspect="auto", color_continuous_scale="Blues", labels={"x": "Months since signup", "y": "Signup month", "color": "Still active"}, title="Customer retention by signup month"), use_container_width=True)
        st.caption("Each row is a group of customers who signed up in the same month. Each column shows how many months have passed since signup. Darker cells mean more customers stayed.")
        st.download_button("Download retention table", matrix.to_csv(), "cohort_retention.csv")

with decisions:
    st.subheader("Test a business decision before acting")
    st.write("Change the assumptions to see how a lower churn rate or a price change could affect recurring revenue. This is a simplified scenario, not a causal forecast.")
    customers = max(0, int(latest.active_customers))
    arpa = float(latest.arpa)
    churn = float(latest.monthly_churn_rate)
    reduction = st.slider("Assumed monthly churn reduction (percentage points)", 0.0, 5.0, 1.0, 0.25)
    price_change = st.slider("Assumed price change (%)", -10, 15, 0, 1)
    scenario_churn = max(0.0, churn - reduction / 100)
    baseline = sum(customers * ((1-churn) ** m) * arpa for m in range(1, 13))
    scenario = sum(customers * ((1-scenario_churn) ** m) * arpa * (1+price_change/100) for m in range(1, 13))
    impact = scenario - baseline
    x, y, z = st.columns(3)
    x.metric("Baseline 12-month revenue", money(baseline))
    y.metric("Scenario 12-month revenue", money(scenario))
    z.metric("Modeled difference", money(impact), delta=money(impact))
    st.write(f"Assumptions: {customers:,} current customers, {churn:.1%} monthly churn and {money(arpa)} average monthly revenue per customer. The model holds new signups and customer mix constant.")
    st.caption("This does not model customer reactions to price changes, seasonality, costs, discounts or acquisition. Do not use it as a financial forecast.")

with briefing:
    st.subheader("Business briefing")
    st.write("A draft summary of the current dataset that an analyst can review and share.")
    if previous is not None:
        mrr_delta = float(latest.mrr - previous.mrr)
        customer_delta = int(latest.active_customers - previous.active_customers)
        churn_delta = float(latest.monthly_churn_rate - previous.monthly_churn_rate)
        lines = [
            "## Subscription business update",
            f"**Latest month:** {pd.Timestamp(latest.month).strftime('%B %Y')}",
            f"- Monthly recurring revenue: {money(latest.mrr)} ({money(mrr_delta)} vs. previous month).",
            f"- Active customers: {int(latest.active_customers):,} ({customer_delta:+,} vs. previous month).",
            f"- Monthly churn: {latest.monthly_churn_rate:.1%} ({churn_delta:+.1%} vs. previous month).",
        ]
        by_plan = segment_revenue_change(df, latest.month, previous.month, "plan") if "plan" in df else pd.DataFrame()
        if not by_plan.empty:
            worst = by_plan.iloc[0]
            lines.append(f"- Largest plan-level MRR decline: {worst['plan']} ({money(worst['change'])}). This is a place to investigate, not proof of cause.")
        lines.append(f"- Unusual MRR movements flagged: {int(detect_metric_changes(metrics, 'mrr').unusual.sum())}.")
        lines.append("- Limitations: data is synthetic; risk scores are rule-based; forecasts are simple trend estimates; segment differences do not prove causation.")
        report = "\n".join(lines)
        st.markdown(report)
        st.download_button("Download business briefing", report, "business_briefing.md")
    else:
        st.info("A previous month is needed to prepare a month-over-month briefing.")
