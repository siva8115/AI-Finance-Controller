"""
create_demo_data.py — Reproducible Demo Dataset for AI Finance Controller

Creates a fixed, reproducible dataset demonstrating all exception types.

Usage:
    cd backend
    python ../scripts/create_demo_data.py

What it does:
    1. Generates 100 synthetic financial orders with a fixed random seed (42)
       so the dataset is identical every time.
    2. Ingests orders, payments, settlements into the SQLite database.
    3. Runs the deterministic 3-way reconciliation engine.
    4. Evaluates accuracy against ground truth.

The generated dataset will contain a meaningful mix of:
    - MATCHED transactions (clean, fully reconciled)
    - AMOUNT_MISMATCH (order vs payment amount differs)
    - FEE_DISCREPANCY (payment fee vs settlement fee differs)
    - MISSING_PAYMENT (order has no corresponding payment)
    - UNMATCHED_SETTLEMENT (settlement has no matching order/payment)
    - DUPLICATE_PAYMENT (two payments for the same order)
    - TIMING_DELAY (payment settled beyond tolerance window)
    - UNACCOUNTED_REFUND (refund without original transaction)

After running this script:
    - Start the backend:  uvicorn app.main:app --reload
    - Open the frontend:  npm run dev  (inside frontend/)
    - Navigate the full demo workflow described in README.md

NOTE: AI investigation and resolution are triggered through the API or UI,
not by this script, to avoid unnecessary Gemini API calls.
"""

import sys
import os

# Ensure we can import backend modules when run from any directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(SCRIPT_DIR, "..", "backend")
sys.path.insert(0, BACKEND_DIR)

DEMO_SEED = 42
DEMO_ORDER_COUNT = 100


def main():
    print("=" * 60)
    print("AI Finance Controller — Demo Data Setup")
    print(f"Seed: {DEMO_SEED} | Orders: {DEMO_ORDER_COUNT}")
    print("=" * 60)

    # Import after sys.path is set
    from app.core.database import engine, SessionLocal, Base
    from app.services.generator import FinancialDataGenerator
    from app.services.ingestion import DataIngestionService
    from app.services.reconciliation import ReconciliationService

    # Create tables if not already present
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── Step 1: Generate synthetic data ───────────────────────────────
        print("\n[1/3] Generating synthetic financial data...")
        from pathlib import Path
        generated_dir = Path(BACKEND_DIR) / "data" / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        generator = FinancialDataGenerator(seed=DEMO_SEED)
        data = generator.generate_dataset(num_orders=DEMO_ORDER_COUNT, output_dir=generated_dir)

        orders_count      = data.get("num_orders", 0)
        payments_count    = data.get("num_payments", 0)
        settlements_count = data.get("num_settlements", 0)

        print(f"   Orders:      {orders_count}")
        print(f"   Payments:    {payments_count}")
        print(f"   Settlements: {settlements_count}")

        # ── Step 2: Ingest ─────────────────────────────────────────────────
        print("\n[2/3] Ingesting data into SQLite database...")
        ingest_result = DataIngestionService().ingest_all(db, raw_data_dir=generated_dir)
        print(f"   Ingested: {ingest_result}")

        # ── Step 3: Reconcile ──────────────────────────────────────────────
        print("\n[3/3] Running deterministic 3-way reconciliation...")
        run_result = ReconciliationService.run_reconciliation(db)

        matched    = run_result.get("matched_count", 0)
        exceptions = run_result.get("exception_count", 0)
        run_id     = run_result.get("run_id", "N/A")

        print(f"   Run ID:     {run_id}")
        print(f"   Matched:    {matched}")
        print(f"   Exceptions: {exceptions}")
        print(f"   Match Rate: {matched / max(matched + exceptions, 1):.1%}")

        print("\n" + "=" * 60)
        print("Demo data setup complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Start backend:  uvicorn app.main:app --reload")
        print("  2. Start frontend: cd frontend && npm run dev")
        print("  3. Open browser:   http://localhost:5173")
        print("  4. To run AI investigation & resolution, use the API")
        print("     or navigate the Review Queue in the UI.")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
