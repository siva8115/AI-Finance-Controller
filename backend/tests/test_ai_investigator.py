"""
Tests for the AI Exception Investigator — Phase 5.1 (Hardened Safety)

All Gemini API calls are mocked. Live network calls are never made.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from tests.conftest import TestingSessionLocal, client
from app.models.financial import Order, Payment, Settlement, ExceptionRecord, AIInvestigation
from app.services.ai_investigator import AIExceptionInvestigator
from app.core.config import settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_exception(
    db: Session,
    *,
    order_id="ORD-100",
    exception_type="FEE_DISCREPANCY",
    payment_status="CAPTURED",
    order_amount=100.0,
    payment_amount=100.0,
    payment_fee=3.20,
    gross_amount=100.0,
    net_amount=96.0,
    settlement_fee=4.0,
    difference=0.80,
    run_id="RUN-1",
):
    """Helper that seeds a minimal order/payment/settlement + exception record."""
    order = Order(order_id=order_id, customer_id="CUST-1", amount=order_amount, status="COMPLETED")
    payment = Payment(
        payment_id=f"PAY-{order_id}",
        order_id=order_id,
        gateway="Stripe",
        amount=payment_amount,
        fee=payment_fee,
        status=payment_status,
    )
    settlement = Settlement(
        settlement_id=f"SET-{order_id}",
        payment_id=f"PAY-{order_id}",
        payout_ref="P-1",
        gross_amount=gross_amount,
        net_amount=net_amount,
        fee_deducted=settlement_fee,
    )
    exc = ExceptionRecord(
        run_id=run_id,
        order_id=order_id,
        payment_id=f"PAY-{order_id}",
        settlement_id=f"SET-{order_id}",
        exception_type=exception_type,
        severity="MEDIUM",
        status="DETECTED",
        expected_value=f"${payment_fee:.2f}",
        actual_value=f"${settlement_fee:.2f}",
        difference=difference,
    )
    db.add_all([order, payment, settlement, exc])
    db.commit()
    return exc


def _make_gemini_response(
    classification="FEE_DISCREPANCY",
    summary="Summary.",
    likely_cause="Cause.",
    recommended_action="Review internally.",
    evidence_facts=None,
    possible_causes=None,
    evidence_gaps=None,
    confidence=0.85,
    requires_human_review=True,
):
    """Builds a realistic Gemini mock JSON string."""
    return json.dumps({
        "classification": classification,
        "summary": summary,
        "likely_cause": likely_cause,
        "recommended_action": recommended_action,
        "evidence_facts": evidence_facts or ["Payment fee is $3.20.", "Settlement fee is $4.00."],
        "possible_causes": possible_causes or ["Gateway may have applied a different fee tier (hypothesis)."],
        "evidence_gaps": evidence_gaps or ["Refund transaction details are not available."],
        "confidence": confidence,
        "requires_human_review": requires_human_review,
    })


def _patch_gemini(mock_text: str):
    """Returns a context-manager that patches the google.genai.Client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_text
    mock_client.models.generate_content.return_value = mock_response
    return patch("google.genai.Client", return_value=mock_client)


# ===========================================================================
# SECTION 1 — Evidence Collection
# ===========================================================================

def test_collect_evidence_structure(db_session: Session):
    exc = _make_exception(db_session)
    ev = AIExceptionInvestigator.collect_evidence(db_session, "ORD-100", exc)

    assert ev["order_id"] == "ORD-100"
    assert ev["payment_id"] == "PAY-ORD-100"
    assert ev["settlement_id"] == "SET-ORD-100"
    assert ev["order_amount"] == 100.0
    assert ev["payment_fee"] == 3.20
    assert ev["settlement_fee"] == 4.0
    assert ev["exception_type"] == "FEE_DISCREPANCY"
    assert ev["payment_status"] == "CAPTURED"


def test_ground_truth_isolation(db_session: Session):
    exc = _make_exception(db_session)
    ev = AIExceptionInvestigator.collect_evidence(db_session, "ORD-100", exc)
    ev_str = json.dumps(ev)
    assert "ground_truth" not in ev_str
    assert ".json" not in ev_str


# ===========================================================================
# SECTION 2 — Valid AI Response (normal happy-path)
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_valid_ai_response_persists(db_session: Session):
    exc = _make_exception(db_session)

    mock_text = _make_gemini_response(confidence=0.85, requires_human_review=True)
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.investigation_id.startswith("INV-")
    assert inv.exception_type == "FEE_DISCREPANCY"   # deterministic type preserved
    assert inv.ai_classification == "FEE_DISCREPANCY"
    assert inv.ai_classification_matches_deterministic is True
    assert inv.ai_confidence == 0.85
    assert len(inv.evidence_facts) > 2   # stored as JSON string
    assert len(inv.possible_causes) > 2
    assert len(inv.evidence_gaps) > 2

    # ExceptionRecord audit fields updated — exception_type and status must remain unchanged
    db_session.refresh(exc)
    assert exc.ai_investigated is True
    assert exc.exception_type == "FEE_DISCREPANCY"   # deterministic type untouched
    assert exc.status == "DETECTED"                  # deterministic status untouched


# ===========================================================================
# SECTION 3 — AI Failure Modes
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_invalid_json_fallback(db_session: Session):
    exc = _make_exception(db_session)
    with _patch_gemini("this-is-not-valid-json"):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.investigation_status == "AI_FAILED"
    assert inv.requires_human_review is True
    assert inv.ai_confidence == 0.0
    assert inv.effective_confidence == 0.0
    assert "AI_FAILED" in json.loads(inv.safety_flags)


@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_invalid_classification_fallback(db_session: Session):
    exc = _make_exception(db_session)
    bad = json.dumps({
        "classification": "TOTALLY_MADE_UP_TYPE",
        "summary": "S", "likely_cause": "L", "recommended_action": "R",
        "evidence_facts": [], "possible_causes": [], "evidence_gaps": [],
        "confidence": 0.95, "requires_human_review": False,
    })
    with _patch_gemini(bad):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.investigation_status == "AI_FAILED"
    assert inv.requires_human_review is True


@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_confidence_out_of_bounds_fallback(db_session: Session):
    exc = _make_exception(db_session)
    bad = _make_gemini_response(confidence=1.5)
    with _patch_gemini(bad):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.investigation_status == "AI_FAILED"
    assert inv.requires_human_review is True


@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "")
def test_missing_api_key(db_session: Session):
    exc = _make_exception(db_session)
    inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.investigation_status == "AI_FAILED"
    assert inv.requires_human_review is True
    assert inv.effective_confidence == 0.0


@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_api_exception_fallback(db_session: Session):
    exc = _make_exception(db_session)
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("Connection timeout")
    with patch("google.genai.Client", return_value=mock_client):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.investigation_status == "AI_FAILED"
    assert inv.requires_human_review is True


# ===========================================================================
# SECTION 4 — Confidence Threshold Routing (clean cases)
# ===========================================================================

@pytest.mark.parametrize("confidence,expected_status,expected_level", [
    (0.95, "AUTO_RESOLVED", "HIGH"),
    (0.75, "REVIEW_RECOMMENDED", "MEDIUM"),
    (0.40, "HUMAN_REVIEW_REQUIRED", "LOW"),
])
@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_confidence_threshold_routing_clean(
    db_session: Session, confidence, expected_status, expected_level
):
    # Use a "clean" exception with CAPTURED status (no safety flags expected)
    exc = _make_exception(db_session, payment_status="CAPTURED",
                          exception_type="AMOUNT_MISMATCH",
                          net_amount=96.0, gross_amount=100.0)
    mock_text = _make_gemini_response(
        classification="AMOUNT_MISMATCH",
        confidence=confidence,
        requires_human_review=confidence < settings.CONFIDENCE_HIGH_THRESHOLD,
    )
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.confidence_level == expected_level
    assert inv.investigation_status == expected_status


# ===========================================================================
# SECTION 5 — Refund Safety Gate
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_refund_case_cannot_be_auto_resolved(db_session: Session):
    """REFUNDED payment must never produce AUTO_RESOLVED, even with ai_confidence=0.99."""
    exc = _make_exception(
        db_session, payment_status="REFUNDED",
        net_amount=-100.0, gross_amount=0.0,
    )
    mock_text = _make_gemini_response(
        confidence=0.99, requires_human_review=False  # AI says confident + no review
    )
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.investigation_status != "AUTO_RESOLVED"
    assert inv.requires_human_review is True
    assert "REFUND_PRESENT" in json.loads(inv.safety_flags)
    assert inv.effective_confidence <= 0.59
    assert inv.ai_confidence == 0.99      # raw AI confidence preserved for audit


@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_refund_confidence_cap_applied(db_session: Session):
    """Effective confidence must be capped at 0.59 for refund cases."""
    exc = _make_exception(db_session, payment_status="REFUNDED", net_amount=-100.0)
    mock_text = _make_gemini_response(confidence=0.95, requires_human_review=False)
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.ai_confidence == 0.95
    assert inv.effective_confidence <= 0.59
    assert inv.confidence_level == "LOW"


# ===========================================================================
# SECTION 6 — Negative Settlement Gate
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_negative_settlement_triggers_human_review(db_session: Session):
    exc = _make_exception(db_session, net_amount=-365.53, gross_amount=0.0)
    mock_text = _make_gemini_response(confidence=0.92, requires_human_review=False)
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.requires_human_review is True
    assert "NEGATIVE_SETTLEMENT" in json.loads(inv.safety_flags)
    assert inv.effective_confidence <= 0.59


# ===========================================================================
# SECTION 7 — AI Classification Disagreement Gate
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_ai_classification_disagreement_triggers_review(db_session: Session):
    """AI classifies as UNACCOUNTED_REFUND but deterministic says FEE_DISCREPANCY."""
    exc = _make_exception(db_session, exception_type="FEE_DISCREPANCY")
    mock_text = _make_gemini_response(
        classification="UNACCOUNTED_REFUND",   # disagrees with deterministic
        confidence=0.97, requires_human_review=False,
    )
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    # Deterministic type must be untouched
    assert inv.exception_type == "FEE_DISCREPANCY"
    assert inv.ai_classification == "UNACCOUNTED_REFUND"
    assert inv.ai_classification_matches_deterministic is False
    assert inv.requires_human_review is True
    assert inv.investigation_status != "AUTO_RESOLVED"
    assert "AI_DETERMINISTIC_DISAGREEMENT" in json.loads(inv.safety_flags)
    assert inv.effective_confidence <= 0.59


# ===========================================================================
# SECTION 8 — Structured AI Output Fields
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_evidence_facts_stored_and_returned(db_session: Session):
    exc = _make_exception(db_session)
    mock_text = _make_gemini_response(
        evidence_facts=["Payment fee is $3.20.", "Settlement fee is $4.00."],
        possible_causes=["Fee tier mismatch (hypothesis)."],
        evidence_gaps=["No refund confirmation in evidence."],
    )
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    facts = json.loads(inv.evidence_facts)
    causes = json.loads(inv.possible_causes)
    gaps = json.loads(inv.evidence_gaps)

    assert "Payment fee is $3.20." in facts
    assert "Settlement fee is $4.00." in facts
    assert any("hypothesis" in c.lower() for c in causes)
    assert len(gaps) >= 1


@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_api_response_includes_structured_fields():
    """Seeds through the shared client session so the endpoint can find the record."""
    shared_db = TestingSessionLocal()
    try:
        _make_exception(shared_db)
    finally:
        shared_db.close()

    mock_text = _make_gemini_response(
        classification="FEE_DISCREPANCY",
        confidence=0.85,
        requires_human_review=True,
        evidence_facts=["Payment fee is $3.20.", "Settlement fee is $4.00."],
        possible_causes=["Fee tier mismatch (hypothesis)."],
        evidence_gaps=["Gateway fee schedule not available."],
    )
    with _patch_gemini(mock_text), \
         patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key"):
        response = client.post("/api/v1/ai/investigate/ORD-100")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert isinstance(data["evidence_facts"], list)
    assert isinstance(data["possible_causes"], list)
    assert isinstance(data["evidence_gaps"], list)
    assert isinstance(data["safety_flags"], list)
    assert "ai_confidence" in data
    assert "effective_confidence" in data
    assert "ai_classification" in data
    assert "ai_classification_matches_deterministic" in data


# ===========================================================================
# SECTION 9 — Dual Confidence Audit
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_dual_confidence_values_stored(db_session: Session):
    """ai_confidence must preserve raw AI value; effective_confidence may be lower."""
    exc = _make_exception(db_session, payment_status="REFUNDED", net_amount=-100.0)
    mock_text = _make_gemini_response(confidence=0.92, requires_human_review=False)
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    assert inv.ai_confidence == 0.92           # raw AI score preserved
    assert inv.effective_confidence < inv.ai_confidence  # backend reduced it
    assert inv.effective_confidence <= 0.59


# ===========================================================================
# SECTION 10 — Deterministic Protection
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_deterministic_reconciliation_status_unchanged(db_session: Session):
    exc = _make_exception(db_session)
    mock_text = _make_gemini_response(confidence=0.95, requires_human_review=False)
    with _patch_gemini(mock_text):
        AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    db_session.refresh(exc)
    assert exc.exception_type == "FEE_DISCREPANCY"    # never changed by AI
    assert exc.status == "DETECTED"                   # reconciliation status untouched


# ===========================================================================
# SECTION 11 — Persistence
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_investigation_persisted_in_db(db_session: Session):
    exc = _make_exception(db_session)
    mock_text = _make_gemini_response(confidence=0.75, requires_human_review=True)
    with _patch_gemini(mock_text):
        inv = AIExceptionInvestigator.investigate_exception(db_session, exc.id)

    stored = db_session.query(AIInvestigation).filter(
        AIInvestigation.investigation_id == inv.investigation_id
    ).first()
    assert stored is not None
    assert stored.reconciliation_run_id == "RUN-1"
    assert stored.exception_id == exc.id
    assert stored.order_id == "ORD-100"


# ===========================================================================
# SECTION 12 — Batch API
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_batch_api(db_session: Session):
    exc = _make_exception(db_session)
    mock_text = _make_gemini_response(confidence=0.92, requires_human_review=False)
    with _patch_gemini(mock_text), \
         patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key"):
        response = client.post("/api/v1/ai/investigate", json={
            "reconciliation_run_id": "RUN-1",
            "max_cases": 5,
        })

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_exceptions"] == 1
    assert data["investigated_cases"] == 1


# ===========================================================================
# SECTION 13 — Filtering API
# ===========================================================================

@patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key")
def test_investigations_filter_by_status():
    """Seeds through the shared client session and uses client for full HTTP round-trip."""
    shared_db = TestingSessionLocal()
    try:
        _make_exception(shared_db)
    finally:
        shared_db.close()

    mock_text = _make_gemini_response(confidence=0.75, requires_human_review=True)
    with _patch_gemini(mock_text), \
         patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key"):
        post_res = client.post("/api/v1/ai/investigate/ORD-100")
    assert post_res.status_code == 200, post_res.text

    res = client.get("/api/v1/ai/investigations?investigation_status=REVIEW_RECOMMENDED")
    assert res.status_code == 200
    results = res.json()["data"]
    assert all(r["investigation_status"] == "REVIEW_RECOMMENDED" for r in results)
