from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.generate import generate_subscriptions
from src.metrics.subscription_metrics import (
    monthly_metrics, cohort_retention, validate_subscriptions,
)
from src.metrics.customer_health import score_customer_health, retention_opportunity

st.set_page_config(page_title="SaaS Retention Command Center", page_icon="📈", layout="wide")
st.title("SaaS Retention Command Center")
st.caption(
    "A practical guide to subscription health: understand revenue, find accounts at risk, "
    "and decide where a customer-success team should investigate."
)
st.info(
    "Demo dataset: this app uses synthetic subscription data. The figures demonstrate how "
    "the analysis works; they are not results from a real company."
)

uploaded = st.sidebar.file_uploader("Upload subscriptions CSV", type=["csv"])
st.sidebar.caption(
    "Use a CSV with one row per customer. Required fields: customer_id, signup_date, "
    "monthly_price, status, churn_date. Optional engagement fields improve the risk score."
)
data_path = ROOT / "data/raw/subscriptions.csv"
if uploaded:
    try:
        df = pd.read_csv(uploaded, parse_dates=["signup_date", "churn_date"])
    except Exception as exc:
        st.error(f"Could not read this CSV: {exc}")
        st.stop()
elif data_path.exists():
    df = pd.read_csv(data_path, parse_dates=["signup_date", "churn_date"])
else:
    df = generate_subscriptions()
    data_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(data_path, index=False)

try:
    validate_subscriptions(df)
except ValueError as exc:
    st.error(f"The uploaded data needs attention: {exc}")
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
overview, command, cohorts, drivers, scenario = st.tabs([
    "Executive overview", "Retention command center", "Cohort retention",
    "Churn drivers", "Revenue simulator"
])

def money(value):
    return f"${value:,.0f}"

with overview:
    st.subheader("Subscription business health")
    st.write(
        "Start here for a snapshot of the business. These measures describe the latest month "
        "in the dataset after applying the plan filter."
    )
    a, b, c, d = st.columns(4)
    a.metric("Active customers", f"{int(latest.active_customers):,}",
             delta=(int(latest.active_customers - previous.active_customers) if previous is not None else None))
    b.metric("Monthly recurring revenue (MRR)", money(latest.mrr),
             delta=(money(latest.mrr - previous.mrr) if previous is not None else None))
    c.metric("Monthly customer churn", f"{latest.monthly_churn_rate:.1%}")
    d.metric("Average revenue per account (ARPA)", f"${latest.arpa:,.2f}")
    with st.expander("What do these four numbers mean?"):
        st.markdown(
            "- **Active customers:** customers with an active subscription at month end.\n"
            "- **MRR:** monthly subscription revenue from active customers. It excludes one-time fees.\n"
            "- **Monthly customer churn:** customers who cancelled during the month divided by customers active at the start of that month.\n"
            "- **ARPA:** MRR divided by active customers. It is the average monthly subscription revenue per active account."
        )
    left, right = st.columns(2)
    left.plotly_chart(px.line(metrics, x="month", y="mrr", markers=True,
                              title="Monthly recurring revenue (MRR)"), use_container_width=True)
    right.plotly_chart(px.line(metrics, x="month", y="active_customers", markers=True,
                               title="Active customers over time"), use_container_width=True)
    st.caption(
        "How to read these lines: each point represents one month. An upward MRR line means "
        "subscription revenue is growing; an upward active-customer line means the active base is growing."
    )
    st.plotly_chart(px.line(metrics, x="month", y="monthly_churn_rate", markers=True,
                            title="Monthly customer churn rate"), use_container_width=True)
    st.caption(
        "Lower is generally better. A spike means a larger share of the opening customer base cancelled "
        "in that month. Compare several months rather than judging one point alone."
    )
    if previous is not None:
        mrr_change = latest.mrr - previous.mrr
        active_change = latest.active_customers - previous.active_customers
        churn_direction = "higher" if latest.monthly_churn_rate > previous.monthly_churn_rate else "lower"
        st.markdown("**What the latest month shows**")
        st.write(
            f"Compared with the previous month, MRR is {money(abs(mrr_change))} "
            f"{'higher' if mrr_change >= 0 else 'lower'} and the active customer count is "
            f"{abs(int(active_change))} {'higher' if active_change >= 0 else 'lower'}. "
            f"The churn rate is {churn_direction} than the previous month."
        )
    else:
        st.info("Only one month is available, so a month-over-month comparison is not possible.")
    st.download_button("Download monthly metrics", metrics.to_csv(index=False),
                       "monthly_metrics.csv", help="Export the monthly figures shown above.")

with command:
    st.subheader("Who should the customer-success team contact first?")
    st.write(
        "This section ranks active accounts by a rule-based risk score. It helps a team decide "
        "which customers to investigate first; it does not predict with certainty who will cancel."
    )
    opportunity = retention_opportunity(scored, 100, 30)
    a, b, c = st.columns(3)
    a.metric("High-risk active accounts", f"{opportunity['high_risk_customers']:,}")
    b.metric("Risk-adjusted monthly revenue", money(opportunity["revenue_at_risk"]))
    c.metric("Active accounts assessed", f"{len(active_scored):,}")
    with st.expander("How the customer risk score is calculated"):
        st.markdown(
            "The score runs from **0 to 100**. Higher means more risk in this model. "
            "Each input is converted to a 0–100 risk value and combined using these weights:\n\n"
            "- Product usage: **30%**\n- Recent usage decline: **20%**\n"
            "- Support ticket volume: **15%**\n- Failed payments: **20%**\n- NPS feedback: **15%**\n\n"
            "Risk bands: **Low = 0–34**, **Medium = 35–64**, **High = 65–100**. "
            "These are hand-set rules for this portfolio demo, not statistically validated thresholds."
        )
    if not active_scored.empty:
        band_counts = (active_scored["risk_band"].value_counts()
                       .reindex(["Low", "Medium", "High"], fill_value=0)
                       .rename_axis("risk_band").reset_index(name="accounts"))
        st.plotly_chart(px.bar(band_counts, x="risk_band", y="accounts",
                               category_orders={"risk_band": ["Low", "Medium", "High"]},
                               title="Active accounts by modeled risk band"),
                        use_container_width=True)
        st.caption(
            "Each bar counts active customers in that risk band. A larger High bar means more "
            "accounts need review. Use the account table below to see the signals behind each score."
        )
        high = active_scored[active_scored.risk_band.eq("High")].sort_values(
            "revenue_at_risk", ascending=False
        )
        if high.empty:
            st.success("No active accounts fall into the High-risk band under the current rules.")
        else:
            st.markdown("**Accounts to review first**")
            st.write(
                "The list is ordered by risk-adjusted monthly revenue, so accounts with both a high "
                "score and a larger subscription value appear first."
            )
            view = high[[
                "customer_id", "plan", "monthly_price", "risk_score", "revenue_at_risk",
                "product_usage_score", "usage_change_pct", "support_tickets_90d",
                "payment_failures_90d", "nps_score", "recommended_action"
            ]]
            st.dataframe(view.head(50), use_container_width=True, hide_index=True)
            st.download_button("Export prioritized retention queue", view.to_csv(index=False),
                               "retention_action_queue.csv")
    else:
        st.info("No active accounts are available under the current filters.")
    st.caption(
        "Risk-adjusted monthly revenue = monthly subscription price × risk score ÷ 100. "
        "It is a prioritization estimate, not a forecast of revenue that will definitely be lost."
    )

with cohorts:
    st.subheader("Do customers stay after they sign up?")
    st.write(
        "A cohort is a group of customers who signed up in the same month. This view follows each "
        "group over the months after signup to show what share remains active."
    )
    matrix = cohort_retention(df)
    if matrix.empty:
        st.info("There is not enough signup history to build a cohort view.")
    else:
        st.plotly_chart(px.imshow(
            matrix, aspect="auto", color_continuous_scale="Blues",
            labels={"x": "Months since signup", "y": "Signup cohort", "color": "Retention"},
            title="Customer retention by signup cohort"
        ), use_container_width=True)
        st.caption(
            "How to read the heatmap: each row is a signup-month cohort; each column is the number "
            "of months since signup. Each cell is the percentage still active. Darker cells indicate "
            "higher retention. Compare the same column across rows to compare cohorts at the same age."
        )
        first_age = matrix.iloc[:, 0].dropna()
        last_age = matrix.apply(lambda row: row.dropna().iloc[-1] if row.notna().any() else float("nan"), axis=1)
        st.markdown("**What the cohort data shows**")
        if len(last_age.dropna()) > 1:
            best = last_age.idxmax()
            worst = last_age.idxmin()
            st.write(
                f"Among the displayed cohorts, **{best}** has the highest retention at its latest "
                f"observed age ({last_age.max():.0%}); **{worst}** has the lowest "
                f"({last_age.min():.0%}). Cohorts have different follow-up lengths, so compare "
                "the same month-since-signup column for a fair comparison."
            )
        else:
            st.write("More signup cohorts are needed before comparing retention patterns.")
        st.download_button("Download cohort matrix", matrix.to_csv(), "cohort_retention.csv")

with drivers:
    st.subheader("Why did customers cancel?")
    churned = df[df.status.eq("Churned")].copy()
    if churned.empty:
        st.info("No churned customers are present in this filtered dataset.")
    elif "churn_reason" not in churned.columns:
        st.warning("The uploaded data has no churn_reason field, so cancellation reasons cannot be analyzed.")
    else:
        counts = (churned["churn_reason"].fillna("Not recorded")
                  .value_counts().rename_axis("reason").reset_index(name="customers"))
        total = int(counts.customers.sum())
        counts["share"] = counts.customers / total
        top = counts.iloc[0]
        st.plotly_chart(px.bar(
            counts, x="reason", y="customers", text="customers",
            title="Customers who cancelled, grouped by reported reason",
            labels={"reason": "Reported cancellation reason", "customers": "Customers"}
        ), use_container_width=True)
        st.caption(
            "Each bar counts churned customers who gave that reason. The bars show frequency, "
            "not the financial impact of each reason and not proof of the underlying cause."
        )
        st.markdown("**What the cancellation data shows**")
        st.write(
            f"The most frequently recorded reason is **{top.reason}** "
            f"({int(top.customers)} of {total} cancellations, or {top.share:.1%}). "
            "This is a useful place to investigate first. It does not establish that this factor caused the cancellations."
        )
        st.markdown("**Cancellation reasons by subscription plan**")
        by_plan = (churned.assign(churn_reason=churned.churn_reason.fillna("Not recorded"))
                   .groupby(["plan", "churn_reason"], dropna=False).size()
                   .reset_index(name="customers"))
        st.caption(
            "Each row counts cancellations for one plan and one reported reason. Use it to see "
            "whether a reason is concentrated in a particular plan."
        )
        st.dataframe(by_plan, use_container_width=True, hide_index=True)
        st.download_button("Download churn breakdown", by_plan.to_csv(index=False),
                           "churn_reason_by_plan.csv")

with scenario:
    st.subheader("What if we contact at-risk customers?")
    st.write(
        "Change the two assumptions below to estimate how much risk-adjusted monthly revenue "
        "could be retained in a hypothetical outreach campaign."
    )
    coverage = st.slider("Share of high-risk accounts contacted", 0, 100, 80, 5)
    save_rate = st.slider("Assumed save rate among contacted accounts", 0, 100, 25, 5)
    result = retention_opportunity(scored, coverage, save_rate)
    x, y, z = st.columns(3)
    x.metric("Risk-adjusted monthly revenue", money(result["revenue_at_risk"]))
    y.metric("High-risk accounts to contact",
             f"{round(result['high_risk_customers'] * coverage / 100):,}")
    z.metric("Modeled monthly revenue retained", money(result["modeled_revenue_retained"]))
    st.markdown("**How this estimate is calculated**")
    st.write(
        "Risk-adjusted revenue × outreach coverage × assumed save rate. "
        "For example, 80% coverage means the team contacts an estimated 80% of high-risk accounts. "
        "A 25% save rate assumes one in four contacted accounts is retained."
    )
    st.caption(
        "This is an illustrative what-if calculation based on a rule-based risk score and user-entered "
        "assumptions. It is not a causal estimate, a forecast, or a guarantee of saved revenue."
    )
