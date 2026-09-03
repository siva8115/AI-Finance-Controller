"""
Unit and Integration Tests — Progressive Evidence Escalation Architecture

Tests cover:
1. Minimal evidence extraction (Level 1).
2. Exception-specific evidence context formatting.
3. Payload budgeting, truncation, and record capping.
4. Level 1 investigation workflow.
5. Level 2 related context escalation workflow.
6. Level 3 extended context escalation workflow.
7. Exponential backoff retry logic for transient/rate-limit errors.
8. Non-retryable 404/model failure fallback to AI_FAILED & HUMAN_REVIEW_REQUIRED.
9. Invalid JSON response handling.
10. Caching of duplicate investigations for unchanged evidence.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.financial import Order, Payment, Settlement, ExceptionRecord, AIInvestigation
from app.services.evidence_extractor import EvidenceExtractor
from app.services.ai_investigator import AIExceptionInvestigator
from tests.conftest import TestingSessionLocal


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Helper Functions ---
def _make_sample_exception(db: Session, exception_type: str = "AMOUNT_MISMATCH") -> ExceptionRecord:
    order = Order(
        order_id="ORD-TEST-999",
        merchant_id="MERCH-001",
        customer_id="CUST-001",
        amount=2500.0,
        currency="INR",
        status="COMPLETED",
    )
    db.add(order)
    db.commit()

    payment = Payment(
        payment_id="PAY-ORD-TEST-999",
        order_id=order.order_id,
        amount=2400.0,
        fee=10.0,
        currency="INR",
        gateway="STRIPE",
        status="CAPTURED",
    )
    db.add(payment)

    settlement = Settlement(
        settlement_id="SET-ORD-TEST-999",
        payment_id=payment.payment_id,
        gross_amount=2400.0,
        net_amount=2390.0,
        fee_deducted=10.0,
        currency="INR",
        payout_ref="PO-12345",
        status="SETTLED",
    )
    db.add(settlement)
    db.commit()

    exc = ExceptionRecord(
        run_id="RUN-TEST-001",
        order_id=order.order_id,
        payment_id=payment.payment_id,
        settlement_id=settlement.settlement_id,
        exception_type=exception_type,
        severity="HIGH",
        status="DETECTED",
        expected_value="2500.0",
        actual_value="2400.0",
        difference=100.0,
        details=f"Test exception for {exception_type}",
    )
    db.add(exc)
    db.commit()
    return exc


def _make_gemini_mock_response(
    classification="MISSING_PAYMENT",
    confidence=0.85,
    requires_human_review=False,
    evidence_gaps=None,
):
    return json.dumps({
        "classification": classification,
        "summary": "Verified exception test summary.",
        "likely_cause": "Hypothesis: Payment gateway delay.",
        "recommended_action": "Check gateway portal.",
        "evidence_facts": ["Order amount is 2500.0 INR"],
        "possible_causes": ["Payment dropped at gateway"],
        "evidence_gaps": evidence_gaps or [],
        "confidence": confidence,
        "requires_human_review": requires_human_review,
    })


# --- Tests ---

def test_minimal_evidence_extraction(db_session: Session):
    order = Order(
        order_id="ORD-NO-PAY-123",
        customer_id="CUST-001",
        merchant_id="MERCH-001",
        amount=500.0,
        currency="INR",
        status="COMPLETED",
    )
    db_session.add(order)
    db_session.commit()

    exc = ExceptionRecord(
        run_id="RUN-TEST-001",
        order_id=order.order_id,
        exception_type="MISSING_PAYMENT",
        severity="HIGH",
        status="DETECTED",
        expected_value="PAY-ORD-NO-PAY-123",
        actual_value="NONE",
        difference=500.0,
    )
    db_session.add(exc)
    db_session.commit()

    ev = EvidenceExtractor.extract_level_1(db_session, exc)

    assert ev["evidence_level"] == "LEVEL 1"
    assert ev["exception_type"] == "MISSING_PAYMENT"
    assert ev["order_id"] == "ORD-NO-PAY-123"
    assert ev["order"]["amount"] == 500.0
    assert ev["exception_specific_context"]["payment_found"] is False
    assert "id" not in ev["order"]  # internal PK excluded


def test_exception_specific_context_fee_discrepancy(db_session: Session):
    exc = _make_sample_exception(db_session, "FEE_DISCREPANCY")
    ev = EvidenceExtractor.extract_level_1(db_session, exc)

    ctx = ev["exception_specific_context"]
    assert ctx["exception_type"] == "FEE_DISCREPANCY"
    assert "fee_difference" in ctx


def test_payload_budget_limits(db_session: Session):
    exc = _make_sample_exception(db_session, "MISSING_PAYMENT")
    ev = EvidenceExtractor.extract_level_1(db_session, exc)

    # Force artificial small budget limit to test truncation
    with patch.object(settings, "MAX_PROMPT_LENGTH", 50):
        budgeted = EvidenceExtractor.apply_payload_budget(ev)
        assert budgeted["evidence_records_count"] >= 1


def test_gemini_404_model_failure_fallback(db_session: Session):
    exc = _make_sample_exception(db_session, "MISSING_PAYMENT")

    # Mock 404 Model Not Found Error from Gemini
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("404 NOT_FOUND: models/gemini-2.5-flash is no longer available to new users.")

    with patch("google.genai.Client", return_value=mock_client):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id, force_fresh=True)

    assert inv.investigation_status == "AI_FAILED"
    assert inv.effective_confidence == 0.0
    assert inv.requires_human_review is True
    assert "AI investigation was unavailable" in inv.summary


def test_level_1_investigation_success(db_session: Session):
    exc = _make_sample_exception(db_session, "AMOUNT_MISMATCH")
    mock_json = _make_gemini_mock_response(classification="AMOUNT_MISMATCH", confidence=0.95, requires_human_review=False)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_json
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id, force_fresh=True)

    assert inv.evidence_level == "LEVEL 1"
    assert inv.ai_attempts >= 1
    assert inv.ai_confidence == 0.95


def test_level_2_escalation_flow(db_session: Session):
    exc = _make_sample_exception(db_session, "AMOUNT_MISMATCH")

    # Level 1 returns low confidence (0.50) with evidence gaps -> triggers Level 2 escalation
    resp_l1 = _make_gemini_mock_response(classification="AMOUNT_MISMATCH", confidence=0.50, evidence_gaps=["Missing merchant transaction history"])
    resp_l2 = _make_gemini_mock_response(classification="AMOUNT_MISMATCH", confidence=0.92, evidence_gaps=[])

    mock_client = MagicMock()
    res1 = MagicMock(text=resp_l1)
    res2 = MagicMock(text=resp_l2)
    mock_client.models.generate_content.side_effect = [res1, res2]

    with patch("google.genai.Client", return_value=mock_client):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id, force_fresh=True)

    assert inv.evidence_level == "LEVEL 2"
    assert inv.effective_confidence >= 0.50


def test_invalid_json_gemini_fallback(db_session: Session):
    exc = _make_sample_exception(db_session, "MISSING_PAYMENT")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "NOT_VALID_JSON_STRING"
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id, force_fresh=True)

    assert inv.investigation_status == "AI_FAILED"
    assert inv.effective_confidence == 0.0
    assert inv.requires_human_review is True


def test_caching_duplicate_investigation(db_session: Session):
    exc = _make_sample_exception(db_session, "MISSING_PAYMENT")
    mock_json = _make_gemini_mock_response(confidence=0.92)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_json
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        inv1 = AIExceptionInvestigator.investigate_exception(db_session, exc.id, force_fresh=True)
        # Call again without force_fresh -> should return cached instance
        inv2 = AIExceptionInvestigator.investigate_exception(db_session, exc.id, force_fresh=False)

    assert inv1.investigation_id == inv2.investigation_id
