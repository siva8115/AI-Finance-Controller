from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# Order Schemas
class OrderBase(BaseModel):
    order_id: str
    customer_id: str
    merchant_id: Optional[str] = "MERCHANT_001"
    amount: float
    currency: str = "USD"
    status: str = "COMPLETED"


class OrderCreate(OrderBase):
    pass


class OrderResponse(OrderBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Payment Schemas
class PaymentBase(BaseModel):
    payment_id: str
    order_id: str
    gateway: str = "Stripe"
    amount: float
    fee: float = 0.0
    currency: str = "USD"
    status: str = "CAPTURED"
    transaction_ref: Optional[str] = None


class PaymentCreate(PaymentBase):
    timestamp: Optional[datetime] = None


class PaymentResponse(PaymentBase):
    id: int
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Settlement Schemas
class SettlementBase(BaseModel):
    settlement_id: str
    payment_id: str
    payout_ref: str
    gross_amount: float
    net_amount: float
    fee_deducted: float = 0.0
    currency: str = "USD"
    status: str = "SETTLED"


class SettlementCreate(SettlementBase):
    settlement_date: Optional[datetime] = None


class SettlementResponse(SettlementBase):
    id: int
    settlement_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)



# Data Generation Schemas
class DataGenerationRequest(BaseModel):
    num_orders: int = Field(default=100, ge=10, le=10000, description="Total number of orders to generate")
    anomaly_rate: float = Field(default=0.15, ge=0.0, le=0.5, description="Fraction of transactions with injected anomalies")
    seed: Optional[int] = Field(default=42, description="Random seed for reproducible dataset generation")


class DataGenerationSummary(BaseModel):
    num_orders: int
    num_payments: int
    num_settlements: int
    num_anomalies: int
    anomaly_breakdown: Dict[str, int]
    files_generated: List[str]


# Ingestion Summary Schema
class IngestionSummary(BaseModel):
    orders_ingested: int
    payments_ingested: int
    settlements_ingested: int
    total_records: int
    status: str


# Overview Summary Schema
class SystemOverview(BaseModel):
    total_orders_in_db: int
    total_payments_in_db: int
    total_settlements_in_db: int
    total_reconciliation_runs: int
    total_open_exceptions: int
    dataset_source: Optional[str] = Field(default="DEMO", description="Source of current data: DEMO, UPLOADED, or EMPTY")


# CSV Upload & Validation Schemas
class CSVPayloadRequest(BaseModel):
    orders_csv: Optional[str] = Field(default=None, description="Raw CSV string content for orders")
    payments_csv: Optional[str] = Field(default=None, description="Raw CSV string content for payments")
    settlements_csv: Optional[str] = Field(default=None, description="Raw CSV string content for settlements")


class ValidationMessage(BaseModel):
    level: str  # VALID | WARNING | ERROR
    message: str
    file_type: str  # ORDERS | PAYMENTS | SETTLEMENTS | CROSS_REFERENCE


class ValidationSummary(BaseModel):
    orders_count: int
    payments_count: int
    settlements_count: int
    total_valid_records: int
    potential_issues_count: int
    file_statuses: Dict[str, str]  # orders, payments, settlements -> VALID | WARNING | ERROR
    messages: List[ValidationMessage]
    is_reconcilable: bool
