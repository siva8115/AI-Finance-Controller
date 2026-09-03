import random
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple
from app.core.config import settings


class FinancialDataGenerator:
    """Generates synthetic multi-source financial dataset with realistic anomalies."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(self.seed)
        self.gateways = ["Stripe", "PayPal", "Adyen"]
        self.anomaly_types = [
            "FEE_DISCREPANCY",
            "AMOUNT_MISMATCH",
            "MISSING_PAYMENT",
            "UNMATCHED_SETTLEMENT",
            "TIMING_DELAY",
            "DUPLICATE_PAYMENT",
            "UNACCOUNTED_REFUND",
        ]

    def _calculate_standard_fee(self, amount: float, gateway: str) -> float:
        """Calculates standard gateway fees."""
        if gateway == "Stripe":
            fee = amount * 0.029 + 0.30
        elif gateway == "PayPal":
            fee = amount * 0.034 + 0.49
        else:  # Adyen
            fee = amount * 0.025 + 0.20
        return round(fee, 2)

    def generate_dataset(
        self,
        num_orders: int = 100,
        anomaly_rate: float = 0.15,
        output_dir: Path = None,
        ground_truth_dir: Path = None,
    ) -> Dict[str, Any]:
        """Generates orders.csv, payments.csv, settlements.csv, and ground_truth.json."""
        output_dir = output_dir or settings.RAW_DATA_DIR
        ground_truth_dir = ground_truth_dir or settings.GROUND_TRUTH_DIR

        output_dir.mkdir(parents=True, exist_ok=True)
        ground_truth_dir.mkdir(parents=True, exist_ok=True)

        base_time = datetime.utcnow() - timedelta(days=7)

        orders: List[Dict[str, Any]] = []
        payments: List[Dict[str, Any]] = []
        settlements: List[Dict[str, Any]] = []
        ground_truth: List[Dict[str, Any]] = []

        anomaly_breakdown: Dict[str, int] = {k: 0 for k in self.anomaly_types}
        anomaly_breakdown["EXACT_MATCH"] = 0

        # Determine which order indexes will have anomalies
        num_anomalies = int(num_orders * anomaly_rate)
        anomaly_indices = set(random.sample(range(num_orders), num_anomalies)) if num_anomalies > 0 else set()

        for i in range(1, num_orders + 1):
            order_id = f"ORD-{10000 + i}"
            customer_id = f"CUST-{random.randint(100, 999)}"
            merchant_id = "MERCHANT_001"
            amount = round(random.uniform(15.0, 450.0), 2)
            currency = "USD"
            order_time = base_time + timedelta(minutes=random.randint(10, 10000))

            order_record = {
                "order_id": order_id,
                "customer_id": customer_id,
                "merchant_id": merchant_id,
                "amount": amount,
                "currency": currency,
                "status": "COMPLETED",
                "created_at": order_time.isoformat(),
            }
            orders.append(order_record)

            payment_id = f"PAY-{20000 + i}"
            settlement_id = f"SET-{30000 + i}"
            payout_ref = f"POUT-{random.randint(500, 999)}"
            gateway = random.choice(self.gateways)

            standard_fee = self._calculate_standard_fee(amount, gateway)
            payment_amount = amount
            payment_fee = standard_fee
            payment_status = "CAPTURED"
            payment_time = order_time + timedelta(seconds=random.randint(2, 60))

            settlement_gross = amount
            settlement_fee = standard_fee
            settlement_net = round(settlement_gross - settlement_fee, 2)
            settlement_date = payment_time + timedelta(days=random.randint(1, 3))
            settlement_status = "SETTLED"

            has_anomaly = (i - 1) in anomaly_indices
            anomaly_type = "EXACT_MATCH"
            description = "Exact 3-way match across internal orders, payment gateway, and bank settlement."

            if has_anomaly:
                anomaly_type = random.choice(self.anomaly_types)

                if anomaly_type == "FEE_DISCREPANCY":
                    # Gateway charged higher fee than contracted rate
                    payment_fee = round(standard_fee * random.uniform(1.8, 2.5), 2)
                    settlement_fee = payment_fee
                    settlement_net = round(settlement_gross - settlement_fee, 2)
                    description = f"Gateway fee anomaly: charged ${payment_fee} instead of contracted fee ${standard_fee}."

                elif anomaly_type == "AMOUNT_MISMATCH":
                    # Payment captured does not equal order amount (e.g. promo code missed or partial charge)
                    payment_amount = round(amount - random.uniform(5.0, 25.0), 2)
                    settlement_gross = payment_amount
                    settlement_fee = self._calculate_standard_fee(payment_amount, gateway)
                    settlement_net = round(settlement_gross - settlement_fee, 2)
                    description = f"Amount mismatch: Order is ${amount}, but Payment captured was ${payment_amount}."

                elif anomaly_type == "MISSING_PAYMENT":
                    # Order exists, but gateway payment record missing
                    description = f"Missing payment: Order {order_id} has no corresponding payment gateway record."

                elif anomaly_type == "UNMATCHED_SETTLEMENT":
                    # Payment recorded, but bank settlement missing or payout failed
                    description = f"Unmatched settlement: Payment {payment_id} captured but no bank payout received."

                elif anomaly_type == "TIMING_DELAY":
                    # Settlement delayed by over 14 days
                    settlement_date = payment_time + timedelta(days=21)
                    description = f"Timing delay: Settlement delayed by 21 days beyond standard 3-day window."

                elif anomaly_type == "DUPLICATE_PAYMENT":
                    # Gateway recorded duplicate payment charge
                    description = f"Duplicate payment: Gateway captured 2 transactions for order {order_id}."

                elif anomaly_type == "UNACCOUNTED_REFUND":
                    # Order refunded on gateway but internal order status not updated
                    payment_status = "REFUNDED"
                    settlement_gross = 0.0
                    settlement_net = -payment_amount
                    settlement_fee = 0.0
                    description = f"Unaccounted refund: Payment {payment_id} was refunded on gateway, but order remains COMPLETED."

            anomaly_breakdown[anomaly_type] += 1

            # Build Payment & Settlement records based on anomaly rules
            if anomaly_type != "MISSING_PAYMENT":
                payment_record = {
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "gateway": gateway,
                    "amount": payment_amount,
                    "fee": payment_fee,
                    "currency": currency,
                    "status": payment_status,
                    "transaction_ref": f"TXN-{random.randint(100000, 999999)}",
                    "timestamp": payment_time.isoformat(),
                }
                payments.append(payment_record)

                if anomaly_type == "DUPLICATE_PAYMENT":
                    dup_payment_id = f"PAY-{20000 + i}-DUP"
                    payments.append({
                        "payment_id": dup_payment_id,
                        "order_id": order_id,
                        "gateway": gateway,
                        "amount": payment_amount,
                        "fee": payment_fee,
                        "currency": currency,
                        "status": payment_status,
                        "transaction_ref": f"TXN-{random.randint(100000, 999999)}",
                        "timestamp": (payment_time + timedelta(seconds=1)).isoformat(),
                    })

                if anomaly_type != "UNMATCHED_SETTLEMENT":
                    settlement_record = {
                        "settlement_id": settlement_id,
                        "payment_id": payment_id,
                        "payout_ref": payout_ref,
                        "gross_amount": settlement_gross,
                        "net_amount": settlement_net,
                        "fee_deducted": settlement_fee,
                        "currency": currency,
                        "settlement_date": settlement_date.isoformat(),
                        "status": settlement_status,
                    }
                    settlements.append(settlement_record)
            else:
                payment_id = None
                settlement_id = None

            ground_truth.append({
                "order_id": order_id,
                "payment_id": payment_id,
                "settlement_id": settlement_id,
                "anomaly_type": anomaly_type,
                "expected_status": "MATCHED" if anomaly_type == "EXACT_MATCH" else "EXCEPTION",
                "description": description,
            })

        # Save CSV files using standard csv module
        orders_csv_path = output_dir / "orders.csv"
        payments_csv_path = output_dir / "payments.csv"
        settlements_csv_path = output_dir / "settlements.csv"
        ground_truth_path = ground_truth_dir / "ground_truth.json"

        def write_csv(path, data):
            if not data:
                return
            headers = data[0].keys()
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)

        write_csv(orders_csv_path, orders)
        write_csv(payments_csv_path, payments)
        write_csv(settlements_csv_path, settlements)

        with open(ground_truth_path, "w", encoding="utf-8") as f:
            json.dump(ground_truth, f, indent=2)

        return {
            "num_orders": len(orders),
            "num_payments": len(payments),
            "num_settlements": len(settlements),
            "num_anomalies": sum(v for k, v in anomaly_breakdown.items() if k != "EXACT_MATCH"),
            "anomaly_breakdown": anomaly_breakdown,
            "files_generated": [
                str(orders_csv_path),
                str(payments_csv_path),
                str(settlements_csv_path),
                str(ground_truth_path),
            ],
        }
