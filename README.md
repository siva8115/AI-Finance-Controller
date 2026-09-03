# AI Finance Controller

An end-to-end AI-assisted financial reconciliation system that deterministically
reconciles orders, payments, and settlements — then uses Gemini AI to investigate
exceptions and route them to human reviewers through a safety-gated workflow.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript + Vite)                            │
│  Dashboard · Reconciliation · Exceptions                         │
│  AI Investigations · Review Queue · Audit Trail                  │
└────────────────────────┬─────────────────────────────────────────┘
                         │  HTTP / REST
┌────────────────────────▼─────────────────────────────────────────┐
│  Backend API (FastAPI + Python)                                   │
│  /api/v1/data · /reconciliation · /ai · /review                  │
│  /resolution · /audit · /evaluation                              │
└────────────────────────┬─────────────────────────────────────────┘
                         │  SQLAlchemy ORM
┌────────────────────────▼─────────────────────────────────────────┐
│  SQLite Database                                                  │
│  orders · payments · settlements · reconciliation_results        │
│  exception_records · ai_investigations · resolutions             │
│  resolution_events (audit trail)                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite 5 |
| Styling | Vanilla CSS (custom HSL dark-mode design system) |
| Backend | FastAPI, Python 3.11 |
| ORM | SQLAlchemy 2.x |
| Database | SQLite (file-based, zero infrastructure) |
| AI | Google Gemini (`gemini-2.0-flash`) via `google-generativeai` |
| Testing | pytest, FastAPI TestClient |

---

## Core Workflow

```
Generate Synthetic Data
        ↓
Ingest CSV → SQLite
        ↓
Deterministic 3-Way Reconciliation (Order × Payment × Settlement)
        ↓
Exception Detection
        ↓
Evaluation Engine  ←── Ground Truth (isolated, evaluation-only)
        ↓
AI Exception Investigator (Gemini)
        ↓
Safety Gates (independent re-evaluation)
        ↓
Resolution Orchestrator (deterministic policy)
        ↓
AUTO_RESOLVED  ──or──  Human Review Queue
                               ↓
                      Approve / Reject / Reopen
                               ↓
                      Audit Trail (immutable events)
```

---

## Reconciliation

The reconciliation engine performs **deterministic 3-way matching**:

1. For each Order, locate all linked Payments (by `order_id`)
2. For each Payment, locate all linked Settlements (by `payment_id`)
3. Compare amounts, fees, and statuses across the three layers
4. Classify each record as:
   - `MATCHED` — all amounts agree within tolerance
   - `AMOUNT_MISMATCH` — order vs payment amount differs
   - `FEE_DISCREPANCY` — payment fee vs settlement fee differs
   - `MISSING_PAYMENT` — no payment found for an order
   - `UNMATCHED_SETTLEMENT` — settlement has no matching order/payment
   - `DUPLICATE_PAYMENT` — multiple payments for the same order
   - `TIMING_DELAY` — settlement date outside tolerance window
   - `UNACCOUNTED_REFUND` — refund present without original transaction

**Rule:** Deterministic reconciliation is always authoritative. AI cannot
change exception types or financial record values.

---

## AI Investigation

When exceptions are detected, the AI Exception Investigator calls Gemini to:

1. Analyse the financial evidence for the exception
2. Classify the root cause
3. Produce structured evidence facts, possible hypotheses, and evidence gaps
4. Assign a confidence score

The AI response is stored in `ai_investigations`. The raw AI confidence score
is preserved alongside a **safety-controlled effective confidence** score that
is reduced when safety gates are triggered.

**Important:** AI classifications are advisory. The deterministic exception
type is never overridden.

---

## Safety Architecture

The Resolution Orchestrator applies independent safety gates before any
auto-resolution decision:

| Safety Gate | Condition |
|---|---|
| Refund present | Any refunded payment or `UNACCOUNTED_REFUND` |
| Negative settlement | Settlement gross or net amount < 0 |
| Missing payment | No payment records found |
| Missing settlement | Payment exists but no settlement |
| Duplicate payment | More than one payment for the same order |
| Evidence gaps | AI reported missing evidence |
| AI failure | Gemini call failed |
| AI disagreement | AI classification ≠ deterministic type |
| Low confidence | Effective confidence below threshold |

Any triggered gate forces the case to `HUMAN_REVIEW_REQUIRED`.
Auto-resolution only occurs when **all** safety conditions pass and
effective confidence ≥ `CONFIDENCE_HIGH_THRESHOLD` (default 0.90).

---

## Human Review Workflow

Cases routed to human review appear in the Review Queue ordered by priority score.

Reviewers can:
- **Approve** — accept the proposed resolution (notes required)
- **Reject** — reject the resolution (reason required)
- **Reopen** — re-open a previously closed case (reason required)

Every action creates an immutable `ResolutionEvent` in the audit trail,
recording the actor, previous/new status, and the reviewer's notes.

**Financial records are never modified by the resolution workflow.**

---

## API Overview

| Endpoint | Description |
|---|---|
| `GET /health` | Backend health and database status |
| `GET /api/v1/data/summary` | System-wide record counts |
| `POST /api/v1/data/generate` | Generate synthetic data |
| `POST /api/v1/data/ingest` | Ingest CSV files into database |
| `POST /api/v1/reconciliation/run` | Run deterministic reconciliation |
| `GET /api/v1/reconciliation/results` | All reconciliation results |
| `GET /api/v1/reconciliation/exceptions` | All detected exceptions |
| `GET /api/v1/evaluation/run` | Evaluate accuracy vs ground truth |
| `GET /api/v1/ai/investigations` | All AI investigation records |
| `POST /api/v1/ai/investigate/{order_id}` | Trigger AI investigation for one order |
| `GET /api/v1/resolution/summary` | Resolution outcome summary |
| `POST /api/v1/resolution/run/{order_id}` | Run resolution for one order |
| `POST /api/v1/resolution/run` | Batch resolution for a run |
| `GET /api/v1/review/queue` | Human review queue |
| `POST /api/v1/review/{id}/approve` | Approve a resolution |
| `POST /api/v1/review/{id}/reject` | Reject a resolution |
| `POST /api/v1/review/{id}/unresolve` | Reopen a resolved case |
| `GET /api/v1/audit/events` | Full audit trail (all events) |
| `GET /api/v1/audit/events/resolution/{id}` | Events for one resolution |

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment (optional — defaults to http://localhost:8000)
cp .env.example .env

# Start the dev server
npm run dev
```

Frontend available at: http://localhost:5173

---

## Testing

```bash
cd backend

# Run all tests
pytest -q

# Expected: 153 passed
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `PROJECT_NAME` | No | Application name (default: AI Finance Controller) |
| `DATABASE_URL` | No | SQLAlchemy URL (default: `sqlite:///./finance.db`) |
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key for AI investigations |
| `CONFIDENCE_HIGH_THRESHOLD` | No | Min confidence for auto-resolution (default: 0.90) |
| `CONFIDENCE_MEDIUM_THRESHOLD` | No | Min confidence for review-recommended (default: 0.60) |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | No | Backend API URL (default: `http://localhost:8000`) |

**Never commit your `GEMINI_API_KEY` to version control.**

---

## Deployment Notes

The application is designed for simple single-server deployment.

**Recommended architecture:**

```
Nginx (reverse proxy)
  ├── / → serve frontend/dist/ (static files)
  └── /api/ → proxy to FastAPI on 127.0.0.1:8000
```

**Steps:**
1. Build the frontend: `cd frontend && npm run build`
2. Serve `frontend/dist/` from Nginx or any static file server
3. Run the backend with a production ASGI server: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. Set `VITE_API_BASE_URL` to the public-facing API URL before building

No database migration tooling is required — SQLAlchemy creates tables on first startup.

For production, consider replacing SQLite with PostgreSQL by updating `DATABASE_URL`.
The application uses SQLAlchemy ORM exclusively — no raw SQL queries.

---

## Demo Workflow

### Create demo data

```bash
cd backend
python ../scripts/create_demo_data.py
```

### Step-by-step demo

| Step | Action |
|---|---|
| 1 | Open **Dashboard** — view order/match/exception counts and resolution summary |
| 2 | Open **Reconciliation** — browse the reconciliation run, open a MATCHED record |
| 3 | Open **Exceptions** — select a high-severity exception to see financial breakdown |
| 4 | Open **AI Investigations** — review AI classification, confidence, safety flags |
| 5 | Open **Review Queue** — select a HUMAN_REVIEW_REQUIRED case, approve or reject it |
| 6 | Open **Audit Trail** — observe the HUMAN event recorded for the approval action |
| 7 | Return to **Dashboard** — verify resolution summary has updated |

### Key things to demonstrate

- AI raw confidence vs safety-controlled effective confidence
- Safety gates that block auto-resolution (refund, missing records, AI disagreement)
- Approve/Reject workflow with required notes
- Immutable audit events (SYSTEM and HUMAN actors)
- Financial records unchanged throughout the entire workflow
