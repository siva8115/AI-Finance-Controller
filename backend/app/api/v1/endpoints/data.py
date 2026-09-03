import io
import csv
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Body
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.schemas.common import APIResponse
from app.schemas.financial import (
    DataGenerationRequest,
    DataGenerationSummary,
    IngestionSummary,
    SystemOverview,
    CSVPayloadRequest,
    ValidationSummary,
    ValidationMessage,
)
from app.services.generator import FinancialDataGenerator
from app.services.ingestion import DataIngestionService
from app.models.financial import (
    Order, Payment, Settlement, ReconciliationRun, ReconciliationResult,
    ExceptionRecord, AIInvestigation, EvaluationRun, Resolution, ResolutionEvent,
)

router = APIRouter(prefix="/data", tags=["Data Management"])


@router.post("/generate", response_model=APIResponse[DataGenerationSummary])
def generate_synthetic_data(payload: DataGenerationRequest = DataGenerationRequest()):
    """Generates synthetic multi-source financial datasets (Orders, Payments, Settlements, Ground Truth)."""
    try:
        generator = FinancialDataGenerator(seed=payload.seed)
        summary = generator.generate_dataset(
            num_orders=payload.num_orders,
            anomaly_rate=payload.anomaly_rate,
        )
        
        # Tag dataset source as DEMO
        try:
            raw_dir = settings.RAW_DATA_DIR
            raw_dir.mkdir(parents=True, exist_ok=True)
            with open(raw_dir / "dataset_source.txt", "w", encoding="utf-8") as f:
                f.write("DEMO")
        except Exception:
            pass

        return APIResponse(
            success=True,
            message=f"Successfully generated dataset with {summary['num_orders']} orders and {summary['num_anomalies']} anomalies.",
            data=DataGenerationSummary(**summary),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate synthetic data: {str(e)}",
        )


@router.post("/validate", response_model=APIResponse[ValidationSummary])
def validate_csv_data(payload: CSVPayloadRequest):
    """Validates raw CSV headers, data types, and cross-references before ingestion."""
    messages = []
    file_statuses = {"orders": "NOT_PROVIDED", "payments": "NOT_PROVIDED", "settlements": "NOT_PROVIDED"}
    orders_count = 0
    payments_count = 0
    settlements_count = 0
    potential_issues = 0
    has_error = False

    order_ids = set()
    payment_ids = set()
    settlement_ids = set()

    # Required column schemas
    REQ_ORDER_COLS = {"order_id", "customer_id", "amount"}
    REQ_PAYMENT_COLS = {"payment_id", "order_id", "amount"}
    REQ_SETTLEMENT_COLS = {"settlement_id", "payment_id", "gross_amount", "net_amount"}

    # Helper for date checking
    def check_date(val: str, field_name: str, record_id: str, file_type: str):
        nonlocal potential_issues
        if not val or val.lower() in ("nan", "nat", "none", "null"):
            return
        try:
            datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            potential_issues += 1
            messages.append(ValidationMessage(
                level="WARNING",
                message=f"{file_type} {record_id} has non-standard/unparseable date '{val}' in {field_name}.",
                file_type=file_type
            ))

    # 1. Validate Orders
    if payload.orders_csv and payload.orders_csv.strip():
        try:
            reader = csv.DictReader(io.StringIO(payload.orders_csv))
            headers = set(reader.fieldnames or [])
            missing_cols = REQ_ORDER_COLS - headers
            if missing_cols:
                has_error = True
                file_statuses["orders"] = "ERROR"
                messages.append(ValidationMessage(
                    level="ERROR",
                    message=f"Orders CSV is missing required columns: {', '.join(missing_cols)}",
                    file_type="ORDERS"
                ))
            else:
                rows = list(reader)
                orders_count = len(rows)
                file_statuses["orders"] = "VALID"
                seen_oids = set()
                for idx, row in enumerate(rows, 1):
                    oid = row.get("order_id", "").strip()
                    if oid:
                        if oid in seen_oids:
                            potential_issues += 1
                            messages.append(ValidationMessage(
                                level="WARNING",
                                message=f"Duplicate order_id '{oid}' found in Orders CSV at row {idx}.",
                                file_type="ORDERS"
                            ))
                        seen_oids.add(oid)
                        order_ids.add(oid)
                    
                    try:
                        amt = float(row.get("amount", 0))
                        if amt <= 0:
                            potential_issues += 1
                            messages.append(ValidationMessage(
                                level="WARNING",
                                message=f"Order {oid or idx} has non-positive amount (${amt:.2f}).",
                                file_type="ORDERS"
                            ))
                    except ValueError:
                        potential_issues += 1
                        messages.append(ValidationMessage(
                            level="WARNING",
                            message=f"Order {oid or idx} has invalid non-numeric amount.",
                            file_type="ORDERS"
                        ))

                    if row.get("created_at"):
                        check_date(row["created_at"], "created_at", oid or str(idx), "ORDERS")

                messages.append(ValidationMessage(
                    level="VALID",
                    message=f"Orders CSV contains {orders_count} valid order records.",
                    file_type="ORDERS"
                ))
        except Exception as err:
            has_error = True
            file_statuses["orders"] = "ERROR"
            messages.append(ValidationMessage(level="ERROR", message=f"Failed to parse Orders CSV: {str(err)}", file_type="ORDERS"))
    else:
        messages.append(ValidationMessage(level="WARNING", message="No Orders CSV provided.", file_type="ORDERS"))

    # 2. Validate Payments
    if payload.payments_csv and payload.payments_csv.strip():
        try:
            reader = csv.DictReader(io.StringIO(payload.payments_csv))
            headers = set(reader.fieldnames or [])
            missing_cols = REQ_PAYMENT_COLS - headers
            if missing_cols:
                has_error = True
                file_statuses["payments"] = "ERROR"
                messages.append(ValidationMessage(
                    level="ERROR",
                    message=f"Payments CSV is missing required columns: {', '.join(missing_cols)}",
                    file_type="PAYMENTS"
                ))
            else:
                rows = list(reader)
                payments_count = len(rows)
                file_statuses["payments"] = "VALID"
                seen_pids = set()
                for idx, row in enumerate(rows, 1):
                    pid = row.get("payment_id", "").strip()
                    oid = row.get("order_id", "").strip()
                    if pid:
                        if pid in seen_pids:
                            potential_issues += 1
                            messages.append(ValidationMessage(
                                level="WARNING",
                                message=f"Duplicate payment_id '{pid}' found in Payments CSV at row {idx}.",
                                file_type="PAYMENTS"
                            ))
                        seen_pids.add(pid)
                        payment_ids.add(pid)

                    try:
                        amt = float(row.get("amount", 0))
                        if amt <= 0:
                            potential_issues += 1
                            messages.append(ValidationMessage(
                                level="WARNING",
                                message=f"Payment {pid or idx} has non-positive amount (${amt:.2f}).",
                                file_type="PAYMENTS"
                            ))
                    except ValueError:
                        potential_issues += 1
                        messages.append(ValidationMessage(
                            level="WARNING",
                            message=f"Payment {pid or idx} has invalid non-numeric amount.",
                            file_type="PAYMENTS"
                        ))

                    if row.get("timestamp"):
                        check_date(row["timestamp"], "timestamp", pid or str(idx), "PAYMENTS")

                    if order_ids and oid and oid not in order_ids:
                        potential_issues += 1
                        messages.append(ValidationMessage(
                            level="WARNING",
                            message=f"Payment {pid or idx} references order '{oid}' not present in Orders CSV (potential MISSING_PAYMENT anomaly).",
                            file_type="PAYMENTS"
                        ))
                messages.append(ValidationMessage(
                    level="VALID",
                    message=f"Payments CSV contains {payments_count} valid payment records.",
                    file_type="PAYMENTS"
                ))
        except Exception as err:
            has_error = True
            file_statuses["payments"] = "ERROR"
            messages.append(ValidationMessage(level="ERROR", message=f"Failed to parse Payments CSV: {str(err)}", file_type="PAYMENTS"))
    else:
        messages.append(ValidationMessage(level="WARNING", message="No Payments CSV provided.", file_type="PAYMENTS"))

    # 3. Validate Settlements
    if payload.settlements_csv and payload.settlements_csv.strip():
        try:
            reader = csv.DictReader(io.StringIO(payload.settlements_csv))
            headers = set(reader.fieldnames or [])
            missing_cols = REQ_SETTLEMENT_COLS - headers
            if missing_cols:
                has_error = True
                file_statuses["settlements"] = "ERROR"
                messages.append(ValidationMessage(
                    level="ERROR",
                    message=f"Settlements CSV is missing required columns: {', '.join(missing_cols)}",
                    file_type="SETTLEMENTS"
                ))
            else:
                rows = list(reader)
                settlements_count = len(rows)
                file_statuses["settlements"] = "VALID"
                seen_sids = set()
                for idx, row in enumerate(rows, 1):
                    sid = row.get("settlement_id", "").strip()
                    pid = row.get("payment_id", "").strip()
                    if sid:
                        if sid in seen_sids:
                            potential_issues += 1
                            messages.append(ValidationMessage(
                                level="WARNING",
                                message=f"Duplicate settlement_id '{sid}' found in Settlements CSV at row {idx}.",
                                file_type="SETTLEMENTS"
                            ))
                        seen_sids.add(sid)
                        settlement_ids.add(sid)

                    try:
                        gross = float(row.get("gross_amount", 0))
                        net = float(row.get("net_amount", 0))
                        if gross <= 0 or net <= 0:
                            potential_issues += 1
                            messages.append(ValidationMessage(
                                level="WARNING",
                                message=f"Settlement {sid or idx} has non-positive amount (Gross: ${gross:.2f}, Net: ${net:.2f}).",
                                file_type="SETTLEMENTS"
                            ))
                    except ValueError:
                        potential_issues += 1
                        messages.append(ValidationMessage(
                            level="WARNING",
                            message=f"Settlement {sid or idx} has invalid non-numeric amount values.",
                            file_type="SETTLEMENTS"
                        ))

                    if row.get("settlement_date"):
                        check_date(row["settlement_date"], "settlement_date", sid or str(idx), "SETTLEMENTS")

                    if payment_ids and pid and pid not in payment_ids:
                        potential_issues += 1
                        messages.append(ValidationMessage(
                            level="WARNING",
                            message=f"Settlement {sid or idx} references payment '{pid}' not in Payments CSV (potential UNMATCHED_SETTLEMENT anomaly).",
                            file_type="SETTLEMENTS"
                        ))
                messages.append(ValidationMessage(
                    level="VALID",
                    message=f"Settlements CSV contains {settlements_count} valid settlement records.",
                    file_type="SETTLEMENTS"
                ))
        except Exception as err:
            has_error = True
            file_statuses["settlements"] = "ERROR"
            messages.append(ValidationMessage(level="ERROR", message=f"Failed to parse Settlements CSV: {str(err)}", file_type="SETTLEMENTS"))
    else:
        messages.append(ValidationMessage(level="WARNING", message="No Settlements CSV provided.", file_type="SETTLEMENTS"))

    summary = ValidationSummary(
        orders_count=orders_count,
        payments_count=payments_count,
        settlements_count=settlements_count,
        total_valid_records=orders_count + payments_count + settlements_count,
        potential_issues_count=potential_issues,
        file_statuses=file_statuses,
        messages=messages,
        is_reconcilable=not has_error and (orders_count > 0 or payments_count > 0 or settlements_count > 0),
    )

    return APIResponse(
        success=not has_error,
        message="CSV validation complete.",
        data=summary,
    )


@router.post("/upload", response_model=APIResponse[IngestionSummary])
def upload_and_ingest_csvs(
    payload: CSVPayloadRequest = Body(...),
    db: Session = Depends(get_db),
):
    """Saves user-uploaded CSV string data into backend files and runs DataIngestionService."""
    try:
        raw_dir = settings.RAW_DATA_DIR
        raw_dir.mkdir(parents=True, exist_ok=True)

        if payload.orders_csv is not None:
            with open(raw_dir / "orders.csv", "w", encoding="utf-8") as f:
                f.write(payload.orders_csv)

        if payload.payments_csv is not None:
            with open(raw_dir / "payments.csv", "w", encoding="utf-8") as f:
                f.write(payload.payments_csv)

        if payload.settlements_csv is not None:
            with open(raw_dir / "settlements.csv", "w", encoding="utf-8") as f:
                f.write(payload.settlements_csv)

        # Tag dataset source as UPLOADED
        with open(raw_dir / "dataset_source.txt", "w", encoding="utf-8") as f:
            f.write("UPLOADED")

        service = DataIngestionService()
        result = service.ingest_all(db=db, raw_data_dir=raw_dir)

        return APIResponse(
            success=True,
            message=f"Successfully uploaded and ingested {result['total_records']} financial records into database.",
            data=IngestionSummary(**result),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload and ingestion failed: {str(e)}",
        )


@router.post("/reset", response_model=APIResponse[Dict[str, str]])
def reset_database(db: Session = Depends(get_db)):
    """Clears all financial transaction records and operational logs from the SQLite database."""
    try:
        db.query(ResolutionEvent).delete()
        db.query(Resolution).delete()
        db.query(AIInvestigation).delete()
        db.query(EvaluationRun).delete()
        db.query(ExceptionRecord).delete()
        db.query(ReconciliationResult).delete()
        db.query(ReconciliationRun).delete()
        db.query(Settlement).delete()
        db.query(Payment).delete()
        db.query(Order).delete()
        db.commit()

        # Tag dataset source as EMPTY
        try:
            source_file = settings.RAW_DATA_DIR / "dataset_source.txt"
            if source_file.exists():
                source_file.unlink()
        except Exception:
            pass

        return APIResponse(
            success=True,
            message="Database operational records cleared successfully.",
            data={"status": "CLEARED"},
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database reset failed: {str(e)}",
        )


@router.post("/ingest", response_model=APIResponse[IngestionSummary])
def ingest_data_to_db(db: Session = Depends(get_db)):
    """Ingests generated raw CSV files into SQLite database tables."""
    try:
        service = DataIngestionService()
        result = service.ingest_all(db=db)
        return APIResponse(
            success=True,
            message=f"Successfully ingested {result['total_records']} financial records into database.",
            data=IngestionSummary(**result),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data ingestion failed: {str(e)}",
        )


@router.get("/summary", response_model=APIResponse[SystemOverview])
def get_data_summary(db: Session = Depends(get_db)):
    """Gets overview counts of stored orders, payments, settlements, and exceptions."""
    try:
        overview = DataIngestionService.get_system_overview(db=db)
        return APIResponse(
            success=True,
            message="System overview retrieved successfully.",
            data=SystemOverview(**overview),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system overview: {str(e)}",
        )
