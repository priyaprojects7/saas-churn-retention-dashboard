from src.pipeline.build_warehouse import create_raw_sources,clean_and_model

def test_pipeline_detects_and_cleans_source_issues(tmp_path,monkeypatch):
    import src.pipeline.build_warehouse as pipeline
    monkeypatch.setattr(pipeline,"RAW",tmp_path/"raw")
    monkeypatch.setattr(pipeline,"PROCESSED",tmp_path/"processed")
    monkeypatch.setattr(pipeline,"WAREHOUSE",tmp_path/"warehouse")
    report=clean_and_model(create_raw_sources())
    assert report["issues_detected"]["duplicate_subscription_rows"]>=1
    assert report["issues_detected"]["invalid_negative_prices"]>=1
    assert report["issues_detected"]["missing_customer_industry"]>=1
    assert (tmp_path/"warehouse/fact_subscription_monthly.csv").exists()
    assert report["rows_after_cleaning"]["fact_subscription_monthly"]>0
