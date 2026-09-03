"""
AI Exception Investigator — Progressive Evidence Escalation Architecture

Architecture:
  Deterministic Exception
        ↓
  Evidence Extractor (Level 1: Minimal)
        ↓
  Gemini API Call (gemini-3.6-flash + exponential backoff retries)
        ↓
  Confidence & Safety Evaluation
        ↓
  Progressive Escalation (Level 2 / Level 3 if confidence low or gaps exist)
        ↓
  Deterministic Safety Gates (authoritative, backend-controlled)
        ↓
  Dual Confidence & Immutable Resolution Routing
        ↓
  Persist AIInvestigation (with escalation metadata & evidence audit)
"""

import json
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.core.config import settings
from app.models.financial import Order, Payment, Settlement, ExceptionRecord, AIInvestigation
from app.schemas.ai import GeminiInvestigationSchema
from app.services.evidence_extractor import EvidenceExtractor

logger = logging.getLogger(__name__)

# Safety gate thresholds
REFUND_SAFETY_CAP = 0.59          # Max effective_confidence when refund ambiguity exists
NEGATIVE_SETTLEMENT_CAP = 0.59    # Max effective_confidence for negative settlement values
MISSING_TRANSACTION_CAP = 0.59    # Max effective_confidence when payment/settlement is absent
DUPLICATE_AMBIGUITY_CAP = 0.59    # Max effective_confidence for duplicate payment cases
CLASSIFICATION_DISAGREE_CAP = 0.59 # Max effective_confidence when AI disagrees with deterministic type

ALLOWED_EXCEPTION_TYPES = {
    "AMOUNT_MISMATCH",
    "MISSING_PAYMENT",
    "UNMATCHED_SETTLEMENT",
    "FEE_DISCREPANCY",
    "TIMING_DELAY",
    "DUPLICATE_PAYMENT",
    "UNACCOUNTED_REFUND",
    "UNKNOWN_EXCEPTION",
}

PROMPT_VERSION = "v3-escalation"

SYSTEM_PROMPT_TEMPLATE = """You are a financial operations investigation assistant.

You are given verified transaction evidence produced by a deterministic reconciliation engine.

Your job is to EXPLAIN the detected exception and recommend the NEXT INTERNAL OPERATIONAL ACTION.

STRICT RULES:
- Do NOT invent facts that are not in the supplied evidence.
- Do NOT change financial amounts.
- Do NOT perform authoritative financial calculations.
- Do NOT assert behaviour of external systems (e.g. Stripe, PayPal) unless the evidence directly proves it.
- Do NOT recommend filing external disputes unless the evidence clearly supports it.
- If evidence is insufficient, say so explicitly in evidence_gaps.
- Separate CONFIRMED FACTS from HYPOTHESES in your response.
- If payment_status is REFUNDED, note it in evidence_facts and treat cause analysis as hypothetical.

You must return valid JSON only — no markdown, no extra text.

Allowed classification values:
  AMOUNT_MISMATCH | MISSING_PAYMENT | UNMATCHED_SETTLEMENT | FEE_DISCREPANCY |
  TIMING_DELAY | DUPLICATE_PAYMENT | UNACCOUNTED_REFUND | UNKNOWN_EXCEPTION

JSON Response Schema (all fields required):
{{
  "classification": "<one of the allowed values above>",
  "summary": "<1-2 sentence neutral summary referencing only supplied amounts>",
  "likely_cause": "<concise root cause hypothesis; label as hypothesis if uncertain>",
  "recommended_action": "<specific internal investigation step — not an external action>",
  "evidence_facts": [
    "<confirmed fact from evidence, e.g. Payment fee is $12.92>",
    ...
  ],
  "possible_causes": [
    "<hypothesis that may explain the exception — label clearly as hypothesis>",
    ...
  ],
  "evidence_gaps": [
    "<missing information that prevents confident conclusion>",
    ...
  ],
  "confidence": <float 0.0–1.0, where 1.0 = complete certainty based on supplied evidence only>,
  "requires_human_review": <true|false>
}}

Evidence Context (prompt version {prompt_version}):
{evidence_json}
"""


class AIExceptionInvestigator:

    @staticmethod
    def collect_evidence(
        db: Session, order_id: str, exception_record: ExceptionRecord
    ) -> Dict[str, Any]:
        """Backward-compatible evidence collection method wrapper for legacy tests."""
        order = db.query(Order).filter(Order.order_id == order_id).first() if order_id else None
        if not order:
            return {}

        payments = db.query(Payment).filter(Payment.order_id == order_id).all()
        payment_ids = [p.payment_id for p in payments]
        settlements = (
            db.query(Settlement).filter(Settlement.payment_id.in_(payment_ids)).all()
            if payment_ids
            else []
        )

        payment_id = payments[0].payment_id if payments else None
        settlement_id = settlements[0].settlement_id if settlements else None

        return {
            "order_id": order.order_id,
            "payment_id": payment_id,
            "settlement_id": settlement_id,
            "order_amount": order.amount,
            "payment_amount": sum(p.amount for p in payments) if payments else 0.0,
            "payment_fee": sum(p.fee for p in payments) if payments else 0.0,
            "settlement_gross_amount": sum(s.gross_amount for s in settlements) if settlements else 0.0,
            "settlement_net_amount": sum(s.net_amount for s in settlements) if settlements else 0.0,
            "settlement_fee": sum(s.fee_deducted for s in settlements) if settlements else 0.0,
            "exception_type": exception_record.exception_type,
            "amount_difference": exception_record.difference or 0.0,
            "payment_status": payments[0].status if payments else None,
            "settlement_status": settlements[0].status if settlements else None,
        }

    @staticmethod
    def call_gemini(
        evidence: Dict[str, Any],
        model_override: Optional[str] = None,
    ) -> Tuple[Optional[GeminiInvestigationSchema], str, str]:
        """
        Calls the Gemini API using gemini-3.6-flash or configured model.
        Returns (parsed_result, error_message, error_category).
        
        Error categories: TRANSIENT_ERROR, RATE_LIMIT, TIMEOUT, MODEL_NOT_FOUND, INVALID_RESPONSE, CONFIGURATION_ERROR
        """
        if not settings.GEMINI_API_KEY:
            logger.warning("Gemini API key is not set. Bypassing Gemini call.")
            return None, "API Key is missing", "CONFIGURATION_ERROR"

        model_name = model_override or getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash")

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)

            prompt = SYSTEM_PROMPT_TEMPLATE.format(
                prompt_version=PROMPT_VERSION,
                evidence_json=json.dumps(evidence, indent=2),
            )

            # Log safe metadata — zero sensitive keys or PII
            logger.info(
                f"Calling Gemini API (model={model_name}, level={evidence.get('evidence_level')}, records={evidence.get('evidence_records_count')})"
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GeminiInvestigationSchema,
                    temperature=0.0,
                ),
            )

            raw_text = response.text
            if not raw_text:
                return None, "Empty response from Gemini API", "INVALID_RESPONSE"

            parsed = GeminiInvestigationSchema.model_validate_json(raw_text)

            if not (0.0 <= parsed.confidence <= 1.0):
                return None, f"Confidence {parsed.confidence} is out of bounds [0, 1]", "INVALID_RESPONSE"

            return parsed, "", ""

        except ValidationError as val_err:
            logger.error(f"Gemini output validation error: {val_err}")
            return None, f"Validation error: {val_err}", "INVALID_RESPONSE"
        except Exception as exc:
            err_str = str(exc)
            logger.error(f"Unexpected error calling Gemini API: {err_str}")

            if "404" in err_str or "NOT_FOUND" in err_str or "no longer available" in err_str:
                return None, f"Model error: {err_str}", "MODEL_NOT_FOUND"
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota" in err_str:
                return None, f"Rate limit error: {err_str}", "RATE_LIMIT"
            elif "timeout" in err_str.lower():
                return None, f"Timeout error: {err_str}", "TIMEOUT"
            else:
                return None, f"Transient error: {err_str}", "TRANSIENT_ERROR"

    @staticmethod
    def call_gemini_with_retry(
        evidence: Dict[str, Any],
        max_attempts: int = 3,
    ) -> Tuple[Optional[GeminiInvestigationSchema], str, int]:
        """
        Executes Gemini API call with exponential backoff retries for transient/rate-limit/timeout errors.
        Returns (parsed_result, error_msg, attempts_used).
        """
        attempt = 0
        last_error = ""
        
        while attempt < max_attempts:
            attempt += 1
            result, err_msg, category = AIExceptionInvestigator.call_gemini(evidence)

            if result is not None:
                return result, "", attempt

            last_error = err_msg

            # Non-retryable errors stop immediately
            if category in ("MODEL_NOT_FOUND", "CONFIGURATION_ERROR"):
                logger.error(f"Non-retryable Gemini error ({category}): {err_msg}. Stopping retries.")
                break

            # Retryable errors wait with exponential backoff
            if attempt < max_attempts:
                sleep_time = 0.5 * (2 ** (attempt - 1))
                logger.info(f"Gemini call attempt {attempt} failed ({category}). Retrying in {sleep_time}s...")
                time.sleep(sleep_time)

        return None, last_error or "Exhausted all retries", attempt

    @staticmethod
    def apply_safety_gates(
        evidence: Dict[str, Any],
        ai_result: Optional[GeminiInvestigationSchema],
        deterministic_exception_type: str,
    ) -> Tuple[float, List[str], bool]:
        """
        Returns (effective_confidence, safety_flags, requires_human_review).
        All financial safety decisions are made here — never delegated to the LLM.
        """
        if ai_result is None:
            return 0.0, ["AI_FAILED"], True

        ai_confidence = ai_result.confidence
        effective_confidence = ai_confidence
        safety_flags: List[str] = []
        requires_human_review = ai_result.requires_human_review

        # Check summary metrics from evidence
        metrics = evidence.get("summary_metrics", {})
        payments = evidence.get("payments", [])
        
        payment_status = (payments[0].get("status") if payments else "").upper()
        if payment_status == "REFUNDED":
            safety_flags.append("REFUND_PRESENT")
            effective_confidence = min(effective_confidence, REFUND_SAFETY_CAP)
            requires_human_review = True

        settlement_net = metrics.get("settlement_total_net", 0.0)
        settlement_gross = metrics.get("settlement_total_gross", 0.0)
        if settlement_net < 0.0 or settlement_gross < 0.0:
            safety_flags.append("NEGATIVE_SETTLEMENT")
            effective_confidence = min(effective_confidence, NEGATIVE_SETTLEMENT_CAP)
            requires_human_review = True

        if not evidence.get("payment_id"):
            safety_flags.append("MISSING_PAYMENT_RECORD")
            effective_confidence = min(effective_confidence, MISSING_TRANSACTION_CAP)
            requires_human_review = True

        if not evidence.get("settlement_id"):
            safety_flags.append("MISSING_SETTLEMENT_RECORD")
            effective_confidence = min(effective_confidence, MISSING_TRANSACTION_CAP)
            requires_human_review = True

        if deterministic_exception_type == "DUPLICATE_PAYMENT":
            safety_flags.append("DUPLICATE_PAYMENT_AMBIGUITY")
            effective_confidence = min(effective_confidence, DUPLICATE_AMBIGUITY_CAP)
            requires_human_review = True

        ai_classification = ai_result.classification
        if ai_classification != deterministic_exception_type:
            safety_flags.append("AI_DETERMINISTIC_DISAGREEMENT")
            effective_confidence = min(effective_confidence, CLASSIFICATION_DISAGREE_CAP)
            requires_human_review = True

        return effective_confidence, safety_flags, requires_human_review

    @staticmethod
    def compute_status(
        effective_confidence: float,
        requires_human_review: bool,
        safety_flags: List[str],
    ) -> Tuple[str, str]:
        """Returns (confidence_level, investigation_status)."""
        if effective_confidence >= settings.CONFIDENCE_HIGH_THRESHOLD:
            confidence_level = "HIGH"
            if not requires_human_review and not safety_flags:
                investigation_status = "AUTO_RESOLVED"
            else:
                investigation_status = "REVIEW_RECOMMENDED"
        elif effective_confidence >= settings.CONFIDENCE_MEDIUM_THRESHOLD:
            confidence_level = "MEDIUM"
            investigation_status = "REVIEW_RECOMMENDED"
        else:
            confidence_level = "LOW"
            investigation_status = "HUMAN_REVIEW_REQUIRED"

        return confidence_level, investigation_status

    @staticmethod
    def _build_failed_investigation(
        run_id: str,
        order_id: str,
        exception_id: int,
        exception_type: str,
        reason: str,
        attempts: int = 1,
        level: str = "LEVEL 1",
    ) -> AIInvestigation:
        return AIInvestigation(
            investigation_id=f"INV-{uuid.uuid4().hex[:8].upper()}",
            reconciliation_run_id=run_id,
            order_id=order_id,
            exception_id=exception_id,
            exception_type=exception_type,
            summary="AI investigation was unavailable. No AI conclusion was generated. This case was safely escalated to human review.",
            likely_cause=f"AI Service Failure: {reason}",
            recommended_action="Route to human review team for manual investigation.",
            ai_classification=None,
            ai_classification_matches_deterministic=False,
            evidence_facts=json.dumps([]),
            possible_causes=json.dumps([]),
            evidence_gaps=json.dumps(["AI investigation unavailable due to API error or configuration issue."]),
            ai_confidence=0.0,
            effective_confidence=0.0,
            confidence_level="LOW",
            requires_human_review=True,
            investigation_status="AI_FAILED",
            safety_flags=json.dumps(["AI_FAILED"]),
            evidence_level=level,
            evidence_records_count=0,
            ai_attempts=attempts,
            escalation_history=json.dumps([
                {"level": level, "status": "AI_FAILED", "reason": reason, "attempts": attempts}
            ]),
            created_at=datetime.utcnow(),
        )

    @staticmethod
    def investigate_exception(db: Session, exception_id: int, force_fresh: bool = False) -> AIInvestigation:
        """
        Runs Progressive Evidence Escalation Pipeline on single ExceptionRecord.
        
        Workflow:
        1. Check duplicate caching (re-use if evidence hash matches).
        2. Level 1: Minimal Evidence -> Call Gemini.
        3. Evaluate confidence & evidence gaps.
        4. If uncertain: Escalate to Level 2 (Related Evidence) -> Call Gemini.
        5. If still uncertain: Escalate to Level 3 (Extended Evidence) -> Call Gemini.
        6. Apply authoritative safety gates.
        7. Persist AIInvestigation & update ExceptionRecord.
        """
        exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id).first()
        if not exc:
            raise ValueError(f"ExceptionRecord with id={exception_id} not found.")

        # --- Check for caching / previous investigation ---
        if not force_fresh:
            existing = (
                db.query(AIInvestigation)
                .filter(AIInvestigation.exception_id == exception_id)
                .order_by(AIInvestigation.created_at.desc())
                .first()
            )
            if existing and existing.investigation_status != "AI_FAILED":
                logger.info(f"Re-using cached investigation {existing.investigation_id} for exception {exception_id}")
                return existing

        # --- Level 1 Evidence Extraction ---
        level1_evidence = EvidenceExtractor.extract_level_1(db, exc)
        if not level1_evidence.get("order") and not level1_evidence.get("payments") and not level1_evidence.get("settlements"):
            inv_failed = AIExceptionInvestigator._build_failed_investigation(
                run_id=exc.run_id,
                order_id=exc.order_id or "UNKNOWN",
                exception_id=exc.id,
                exception_type=exc.exception_type,
                reason="Could not collect evidence — order/transaction not found.",
            )
            db.add(inv_failed)
            exc.ai_investigated = True
            exc.ai_confidence = 0.0
            exc.ai_root_cause = inv_failed.likely_cause
            exc.ai_recommendation = inv_failed.recommended_action
            db.commit()
            return inv_failed

        current_evidence = level1_evidence
        current_level = "LEVEL 1"
        total_attempts = 0
        escalation_history: List[Dict[str, Any]] = []

        # --- Progressive Escalation Loop ---
        ai_result: Optional[GeminiInvestigationSchema] = None
        last_error_msg = ""

        # Step 1: Attempt Level 1
        res, err, attempts = AIExceptionInvestigator.call_gemini_with_retry(
            current_evidence, max_attempts=settings.MAX_INVESTIGATION_ATTEMPTS
        )
        total_attempts += attempts

        if res is not None:
            ai_result = res
            eff_conf, flags, req_rev = AIExceptionInvestigator.apply_safety_gates(
                current_evidence, res, exc.exception_type
            )
            escalation_history.append({
                "level": "LEVEL 1",
                "records_analyzed": current_evidence.get("evidence_records_count", 0),
                "ai_confidence": res.confidence,
                "effective_confidence": eff_conf,
                "evidence_gaps_count": len(res.evidence_gaps),
                "status": "COMPLETED",
            })

            # Check if escalation to Level 2 is needed (low confidence or evidence gaps exist)
            if eff_conf < settings.CONFIDENCE_HIGH_THRESHOLD or len(res.evidence_gaps) > 0:
                logger.info(f"Escalating exception {exc.id} to LEVEL 2 (Level 1 confidence={eff_conf})")
                level2_evidence = EvidenceExtractor.extract_level_2(db, exc, level1_evidence)
                current_evidence = level2_evidence
                current_level = "LEVEL 2"

                res2, err2, attempts2 = AIExceptionInvestigator.call_gemini_with_retry(
                    current_evidence, max_attempts=settings.MAX_INVESTIGATION_ATTEMPTS
                )
                total_attempts += attempts2

                if res2 is not None:
                    ai_result = res2
                    eff_conf2, flags2, req_rev2 = AIExceptionInvestigator.apply_safety_gates(
                        current_evidence, res2, exc.exception_type
                    )
                    escalation_history.append({
                        "level": "LEVEL 2",
                        "records_analyzed": current_evidence.get("evidence_records_count", 0),
                        "ai_confidence": res2.confidence,
                        "effective_confidence": eff_conf2,
                        "evidence_gaps_count": len(res2.evidence_gaps),
                        "status": "COMPLETED",
                    })

                    # Check if escalation to Level 3 is needed
                    if eff_conf2 < settings.CONFIDENCE_HIGH_THRESHOLD or len(res2.evidence_gaps) > 0:
                        logger.info(f"Escalating exception {exc.id} to LEVEL 3 (Level 2 confidence={eff_conf2})")
                        level3_evidence = EvidenceExtractor.extract_level_3(db, exc, level2_evidence)
                        current_evidence = level3_evidence
                        current_level = "LEVEL 3"

                        res3, err3, attempts3 = AIExceptionInvestigator.call_gemini_with_retry(
                            current_evidence, max_attempts=settings.MAX_INVESTIGATION_ATTEMPTS
                        )
                        total_attempts += attempts3

                        if res3 is not None:
                            ai_result = res3
                            eff_conf3, _, _ = AIExceptionInvestigator.apply_safety_gates(
                                current_evidence, res3, exc.exception_type
                            )
                            escalation_history.append({
                                "level": "LEVEL 3",
                                "records_analyzed": current_evidence.get("evidence_records_count", 0),
                                "ai_confidence": res3.confidence,
                                "effective_confidence": eff_conf3,
                                "evidence_gaps_count": len(res3.evidence_gaps),
                                "status": "COMPLETED",
                            })
        else:
            last_error_msg = err

        # --- Handle Failure / Fallback ---
        if ai_result is None:
            inv_failed = AIExceptionInvestigator._build_failed_investigation(
                run_id=exc.run_id,
                order_id=exc.order_id or "UNKNOWN",
                exception_id=exc.id,
                exception_type=exc.exception_type,
                reason=last_error_msg,
                attempts=total_attempts,
                level=current_level,
            )
            db.add(inv_failed)
            exc.ai_investigated = True
            exc.ai_confidence = 0.0
            exc.ai_root_cause = inv_failed.likely_cause
            exc.ai_recommendation = inv_failed.recommended_action
            db.commit()
            return inv_failed

        # --- Apply final safety gates on selected evidence & result ---
        effective_confidence, safety_flags, requires_human_review = AIExceptionInvestigator.apply_safety_gates(
            evidence=current_evidence,
            ai_result=ai_result,
            deterministic_exception_type=exc.exception_type,
        )

        confidence_level, investigation_status = AIExceptionInvestigator.compute_status(
            effective_confidence=effective_confidence,
            requires_human_review=requires_human_review,
            safety_flags=safety_flags,
        )

        ai_matches = ai_result.classification == exc.exception_type

        investigation = AIInvestigation(
            investigation_id=f"INV-{uuid.uuid4().hex[:8].upper()}",
            reconciliation_run_id=exc.run_id,
            order_id=exc.order_id,
            exception_id=exc.id,
            exception_type=exc.exception_type,
            summary=ai_result.summary,
            likely_cause=ai_result.likely_cause,
            recommended_action=ai_result.recommended_action,
            ai_classification=ai_result.classification,
            ai_classification_matches_deterministic=ai_matches,
            evidence_facts=json.dumps(ai_result.evidence_facts),
            possible_causes=json.dumps(ai_result.possible_causes),
            evidence_gaps=json.dumps(ai_result.evidence_gaps),
            ai_confidence=ai_result.confidence,
            effective_confidence=effective_confidence,
            confidence_level=confidence_level,
            requires_human_review=requires_human_review,
            investigation_status=investigation_status,
            safety_flags=json.dumps(safety_flags),
            evidence_level=current_level,
            evidence_records_count=current_evidence.get("evidence_records_count", 0),
            ai_attempts=total_attempts,
            escalation_history=json.dumps(escalation_history),
            created_at=datetime.utcnow(),
        )

        db.add(investigation)

        # Update ExceptionRecord
        exc.ai_investigated = True
        exc.ai_confidence = effective_confidence
        exc.ai_root_cause = ai_result.likely_cause
        exc.ai_recommendation = ai_result.recommended_action

        db.commit()
        return investigation
