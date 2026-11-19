import pandas as pd
import pytest
from src.metrics.subscription_metrics import monthly_metrics,cohort_retention,estimate_ltv,what_if_revenue,validate_subscriptions

@pytest.fixture
def sample():
    return pd.DataFrame({"customer_id":["A","B","C"],
      "signup_date":pd.to_datetime(["2024-01-02","2024-01-10","2024-02-01"]),
      "monthly_price":[100.,200.,50.],"status":["Churned","Active","Active"],
      "churn_date":pd.to_datetime(["2024-02-15",None,None]),"plan":["Starter","Growth","Starter"]})

def test_duplicate_customer_ids_rejected(sample):
    sample.loc[1,"customer_id"]="A"
    with pytest.raises(ValueError,match="unique"): validate_subscriptions(sample)

def test_monthly_mrr_and_active_base(sample):
    result=monthly_metrics(sample)
    jan=result.loc[result.month.eq(pd.Timestamp("2024-01-01"))].iloc[0]
    assert jan.active_customers==2
    assert jan.mrr==300

def test_ltv_proxy():
    assert estimate_ltv(100,.05)==pytest.approx(2000)
    assert pd.isna(estimate_ltv(100,0))

def test_what_if_scenario_improves_revenue():
    result=what_if_revenue(100,50,.05,2,12)
    assert result["scenario_revenue"]>result["baseline_revenue"]

def test_cohort_matrix_has_signup_cohort(sample):
    assert "2024-01" in cohort_retention(sample).index
