import json
import pytest
from pathlib import Path
import csv
from app.services.generator import FinancialDataGenerator


def test_financial_data_generator(tmp_path):
    """Test generating dataset files and ground truth annotation consistency."""
    raw_dir = tmp_path / "raw"
    gt_dir = tmp_path / "ground_truth"

    generator = FinancialDataGenerator(seed=123)
    summary = generator.generate_dataset(
        num_orders=50,
        anomaly_rate=0.20,
        output_dir=raw_dir,
        ground_truth_dir=gt_dir,
    )

    assert summary["num_orders"] == 50
    assert summary["num_anomalies"] > 0
    assert (raw_dir / "orders.csv").exists()
    assert (raw_dir / "payments.csv").exists()
    assert (raw_dir / "settlements.csv").exists()
    assert (gt_dir / "ground_truth.json").exists()

    with open(raw_dir / "orders.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        orders_rows = list(reader)
        fieldnames = reader.fieldnames
    assert len(orders_rows) == 50
    assert "order_id" in fieldnames
    assert "amount" in fieldnames

    with open(gt_dir / "ground_truth.json", "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    assert len(gt_data) == 50
    matched_items = [item for item in gt_data if item["expected_status"] == "MATCHED"]
    exception_items = [item for item in gt_data if item["expected_status"] == "EXCEPTION"]

    assert len(matched_items) > 0
    assert len(exception_items) == summary["num_anomalies"]
