import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.models.base import Base
from app.models.financial import Order, Payment, Settlement, ReconciliationRun, ExceptionRecord


class DataIngestionService:
    """Service to load raw financial CSV files into database models."""

    @staticmethod
    def _parse_datetime(val: Any) -> datetime:
        """Parses date string or returns datetime object."""
        if val is None or val == "" or str(val).lower() in ("nan", "nat", "none", "null"):
            return datetime.utcnow()
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val))

    def ingest_all(self, db: Session, raw_data_dir: Path = None) -> Dict[str, Any]:
        """Ingests orders.csv, payments.csv, and settlements.csv into SQLite database."""
        # Ensure database tables exist on target session
        Base.metadata.create_all(bind=db.get_bind())
        raw_data_dir = raw_data_dir or settings.RAW_DATA_DIR


        orders_file = raw_data_dir / "orders.csv"
        payments_file = raw_data_dir / "payments.csv"
        settlements_file = raw_data_dir / "settlements.csv"

        if not orders_file.exists() or not payments_file.exists() or not settlements_file.exists():
            raise FileNotFoundError(
                f"Missing raw CSV files in {raw_data_dir}. Ensure data generator has run."
            )

        def read_csv(path):
            with open(path, "r", encoding="utf-8") as f:
                return list(csv.DictReader(f))

        orders_rows = read_csv(orders_file)
        payments_rows = read_csv(payments_file)
        settlements_rows = read_csv(settlements_file)

        def get_str(row, key, default=""):
            val = row.get(key)
            if val is None or val == "":
                return default
            return str(val)

        def get_float(row, key, default=0.0):
            val = row.get(key)
            if val is None or val == "":
                return default
            try:
                return float(val)
            except ValueError:
                return default

        # Ingest Orders
        orders_ingested = 0
        for row in orders_rows:
            existing = db.query(Order).filter(Order.order_id == get_str(row, "order_id")).first()
            if not existing:
                order_obj = Order(
                    order_id=get_str(row, "order_id"),
                    customer_id=get_str(row, "customer_id"),
                    merchant_id=get_str(row, "merchant_id", "MERCHANT_001"),
                    amount=get_float(row, "amount"),
                    currency=get_str(row, "currency", "USD"),
                    status=get_str(row, "status", "COMPLETED"),
                    created_at=self._parse_datetime(row.get("created_at")),
                )
                db.add(order_obj)
                orders_ingested += 1
            else:
                existing.amount = get_float(row, "amount")
                existing.status = get_str(row, "status", "COMPLETED")

        # Ingest Payments
        payments_ingested = 0
        for row in payments_rows:
            existing = db.query(Payment).filter(Payment.payment_id == get_str(row, "payment_id")).first()
            if not existing:
                payment_obj = Payment(
                    payment_id=get_str(row, "payment_id"),
                    order_id=get_str(row, "order_id"),
                    gateway=get_str(row, "gateway", "Stripe"),
                    amount=get_float(row, "amount"),
                    fee=get_float(row, "fee", 0.0),
                    currency=get_str(row, "currency", "USD"),
                    status=get_str(row, "status", "CAPTURED"),
                    transaction_ref=get_str(row, "transaction_ref", ""),
                    timestamp=self._parse_datetime(row.get("timestamp")),
                )
                db.add(payment_obj)
                payments_ingested += 1
            else:
                existing.amount = get_float(row, "amount")
                existing.fee = get_float(row, "fee", 0.0)
                existing.status = get_str(row, "status", "CAPTURED")

        # Ingest Settlements
        settlements_ingested = 0
        for row in settlements_rows:
            existing = db.query(Settlement).filter(Settlement.settlement_id == get_str(row, "settlement_id")).first()
            if not existing:
                settlement_obj = Settlement(
                    settlement_id=get_str(row, "settlement_id"),
                    payment_id=get_str(row, "payment_id"),
                    payout_ref=get_str(row, "payout_ref", ""),
                    gross_amount=get_float(row, "gross_amount"),
                    net_amount=get_float(row, "net_amount"),
                    fee_deducted=get_float(row, "fee_deducted", 0.0),
                    currency=get_str(row, "currency", "USD"),
                    settlement_date=self._parse_datetime(row.get("settlement_date")),
                    status=get_str(row, "status", "SETTLED"),
                )
                db.add(settlement_obj)
                settlements_ingested += 1
            else:
                existing.gross_amount = get_float(row, "gross_amount")
                existing.net_amount = get_float(row, "net_amount")
                existing.fee_deducted = get_float(row, "fee_deducted", 0.0)

        db.commit()

        total_records = orders_ingested + payments_ingested + settlements_ingested

        return {
            "orders_ingested": orders_ingested,
            "payments_ingested": payments_ingested,
            "settlements_ingested": settlements_ingested,
            "total_records": total_records,
            "status": "SUCCESS",
        }

    @staticmethod
    def get_system_overview(db: Session) -> Dict[str, Any]:
        """Returns database counts and dataset source for system overview."""
        total_orders = db.query(func.count(Order.id)).scalar() or 0
        total_payments = db.query(func.count(Payment.id)).scalar() or 0
        total_settlements = db.query(func.count(Settlement.id)).scalar() or 0
        
        # Check source indicator file
        source = "DEMO"
        source_file = settings.RAW_DATA_DIR / "dataset_source.txt"
        if total_orders == 0 and total_payments == 0 and total_settlements == 0:
            source = "EMPTY"
        elif source_file.exists():
            try:
                source = source_file.read_text(encoding="utf-8").strip() or "DEMO"
            except Exception:
                source = "DEMO"

        return {
            "total_orders_in_db": total_orders,
            "total_payments_in_db": total_payments,
            "total_settlements_in_db": total_settlements,
            "total_reconciliation_runs": db.query(func.count(ReconciliationRun.id)).scalar() or 0,
            "total_open_exceptions": db.query(func.count(ExceptionRecord.id)).filter(ExceptionRecord.status == "OPEN").scalar() or 0,
            "dataset_source": source,
        }
