"""Data generation and ingestion API integration tests."""
from tests.conftest import client


def test_data_generation_and_ingestion_api():
    """Test POST /api/v1/data/generate and POST /api/v1/data/ingest endpoints.
    
    Uses seed=999 to avoid raw CSV collision with other test modules that may
    call /generate with different parameters (e.g. test_evaluation uses seed=42).
    """
    # Generate data with unique seed
    response = client.post(
        "/api/v1/data/generate",
        json={"num_orders": 30, "anomaly_rate": 0.10, "seed": 999},
    )
    assert response.status_code == 200
    gen_data = response.json()
    assert gen_data["success"] is True
    assert gen_data["data"]["num_orders"] == 30

    # Ingest data into DB
    ingest_resp = client.post("/api/v1/data/ingest")
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert ingest_data["success"] is True
    # All 30 orders should be ingested (in-memory DB is fresh per test via setup_db fixture)
    assert ingest_data["data"]["orders_ingested"] == 30

    # Get data summary
    summary_resp = client.get("/api/v1/data/summary")
    assert summary_resp.status_code == 200
    summary_data = summary_resp.json()["data"]
    assert summary_data["total_orders_in_db"] == 30
    assert summary_data["total_payments_in_db"] > 0
    assert summary_data["total_settlements_in_db"] > 0

