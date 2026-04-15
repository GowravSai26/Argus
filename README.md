# 👁 Argus — Autonomous Fraud Investigation Agent

> *Named after Argus Panoptes — the 100-eyed giant of Greek mythology who never slept, assigned to guard something priceless.*

**Visa processes 700 million transactions a day. Human fraud analysts investigate flagged cases manually, using 6 different internal tools, taking 15–30 minutes per case. Argus replicates that entire investigation workflow autonomously — pulling transaction history, checking merchant risk, validating geolocation plausibility, and detecting velocity anomalies — producing a full investigation report with verdict and confidence score in under 2.5 seconds.**

[![Precision](https://img.shields.io/badge/Precision-100%25-10B981?style=flat)](/)
[![Recall](https://img.shields.io/badge/Recall-100%25-10B981?style=flat)](/)
[![Evals](https://img.shields.io/badge/Evals-10%2F10-F59E0B?style=flat)](/)
[![Live](https://img.shields.io/badge/Live-Railway-6B6BF9?style=flat)](https://argus-production-7aa3.up.railway.app)

---

## 🔴 Live Demo

**[argus.vercel.app](https://argus.vercel.app)** — Submit a real transaction. Watch the agent investigate it.

**API:** `https://argus-production-7aa3.up.railway.app` — Live on Railway. Full Swagger docs at `/docs`.

---

## The Problem

Fraud analysts at payment networks spend 15–30 minutes per flagged case, manually cross-referencing:
- Transaction history across multiple systems
- Merchant risk databases
- Cardholder behavioral profiles
- Geolocation plausibility
- Velocity and pattern signals

At scale, this is impossible. Argus solves it.

---

## What Argus Does

When a suspicious transaction is flagged, Argus:

1. **Receives** the transaction as a structured event via REST API
2. **Autonomously invokes tools** — no human direction needed:
   - `get_transaction_history` — last N transactions for this card
   - `check_merchant_risk` — fraud rate, category, country risk score
   - `check_velocity` — transaction count in sliding time window
   - `check_geolocation_plausibility` — is this travel physically possible?
   - `get_cardholder_profile` — behavioral baseline, home country, spend patterns
   - `flag_for_human_review` — escalation when confidence is below threshold
3. **Reasons** over collected signals using Claude with full tool-use
4. **Delivers a verdict**: `BLOCK` · `ALLOW` · `ESCALATE`
5. **Returns** a structured investigation report with confidence score and full justification

Total time: **< 2.5 seconds**. Every step is traced in LangSmith.

---

## Evaluation Results

```
============================================================
  ARGUS EVALUATION HARNESS — 10 Cases
============================================================
  eval_001  Impossible travel — US card used in Nigeria 30 min after US usage
            ✓ expected=BLOCK     predicted=BLOCK     confidence=0.90
  eval_002  Normal grocery purchase in home country
            ✓ expected=ALLOW     predicted=ALLOW     confidence=0.80
  eval_003  High-value electronics at new merchant abroad
            ✓ expected=BLOCK     predicted=BLOCK     confidence=0.90
  eval_004  Regular coffee shop — cardholder known to travel
            ✓ expected=ALLOW     predicted=ALLOW     confidence=0.80
  eval_005  Card testing — 5 micro-transactions in 20 minutes
            ✓ expected=BLOCK     predicted=BLOCK     confidence=0.90
  eval_006  Ambiguous cross-border — plausible timing
            ✓ expected=ESCALATE  predicted=ESCALATE  confidence=0.60
  eval_007  Crypto exchange — high risk category, large amount
            ✓ expected=BLOCK     predicted=BLOCK     confidence=0.90
  eval_008  Pharmacy — low amount, home country
            ✓ expected=ALLOW     predicted=ALLOW     confidence=0.80
  eval_009  Wire transfer at odd hour from foreign country
            ✓ expected=BLOCK     predicted=BLOCK     confidence=0.90
  eval_010  Utilities bill — predictable recurring charge
            ✓ expected=ALLOW     predicted=ALLOW     confidence=0.80
============================================================
  Precision : 1.0000    Recall : 1.0000    F1 : 1.0000
  10/10 correct — EVAL PASSED
============================================================
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT / API                         │
│              POST /investigate  {transaction}               │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    FastAPI (api/main.py)                    │
│              Pydantic schema validation                     │
│              Request routing + error handling               │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 LangGraph Agent (agent/graph.py)            │
│                                                             │
│   [START] → [investigate_node] → [tool_node] → [END]        │
│                     ↑                  │                    │
│                     └──────────────────┘                    │
│               (loops until agent stops calling tools)       │
│                                                             │
│   Tools available to agent:                                 │
│   • get_transaction_history(card_id, limit)                 │
│   • check_merchant_risk(merchant_id)                        │
│   • check_velocity(card_id, window_minutes)                 │
│   • check_geolocation_plausibility(loc_a, loc_b, minutes)   │
│   • get_cardholder_profile(card_id)                         │
│   • flag_for_human_review(case_id, reason)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼───────┐         ┌─────────▼────────┐
│  PostgreSQL   │         │   Claude API     │
│  Transaction  │         │   (tool-use)     │
│  history +    │         │   Reasoning ove  │
│  cardholder   │         │   collected      │
│  profiles     │         │   signals        │
└───────────────┘         └──────────────────┘
        │
┌───────▼───────────────────────────────────────────────────┐
│                      LangSmith                            │
│   Full trace of every agent run — tool calls, LLM         │
│   responses, latency per step, token usage                │
└───────────────────────────────────────────────────────────┘
```

---

## Scaling to Production

Argus is designed to scale horizontally. Here's how it grows:

| Scale | Architecture |
|---|---|
| **Current** | Single FastAPI instance on Railway, PostgreSQL |
| **10× traffic** | Add Gunicorn workers, read replicas for PostgreSQL |
| **100× traffic** | Kubernetes deployment, Redis cache for cardholder profiles, async task queue (Celery/ARQ) |
| **Visa-scale** | Kafka event streaming, feature store (Feast), model serving (Triton), multi-region deployment |

Key design decisions that enable scaling:
- **Stateless API** — each request carries all context, horizontal scaling is trivial
- **Connection pooling** — SQLAlchemy pool, no connection exhaustion under load
- **Tool isolation** — each tool is a pure function, independently cacheable
- **Async-ready** — FastAPI async endpoints, non-blocking I/O throughout

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Agent framework | LangGraph | State machine with explicit nodes/edges — inspectable, debuggable, production-ready |
| LLM | Claude API (tool-use) | Best-in-class tool-use reliability and reasoning quality |
| Backend | FastAPI + Pydantic v2 | Fully typed, async, automatic OpenAPI docs |
| Database | PostgreSQL | ACID compliance, complex queries on transaction history |
| Observability | LangSmith | Full agent trace — every tool call, every LLM response, latency, cost |
| Containerization | Docker + docker-compose | One-command local setup, production parity |
| Deployment | Railway | Zero-config PostgreSQL + app hosting |
| CI/CD | GitHub Actions | Lint → test → build on every push |
| Code quality | ruff + pre-commit | Zero lint warnings, consistent formatting enforced at commit |

---

## Project Structure

```
argus/
├── .github/
│   └── workflows/
│       └── ci.yml               # Lint → test → docker build on every push
├── agent/
│   ├── graph.py                 # LangGraph state machine definition
│   ├── nodes.py                 # Agent reasoning nodes
│   ├── state.py                 # Typed agent state (TypedDict)
│   └── tools/
│       ├── transaction.py       # Transaction history lookup
│       ├── merchant.py          # Merchant risk scoring
│       ├── velocity.py          # Velocity / rate detection
│       ├── geolocation.py       # Travel plausibility check
│       ├── profile.py           # Cardholder behavioral profile
│       └── escalation.py        # Human review flagging
├── api/
│   ├── main.py                  # FastAPI app, CORS, lifespan
│   └── schemas.py               # Pydantic request/response models
├── data/
│   ├── generate.py              # Synthetic transaction data generator
│   └── seed.sql                 # DB schema + seed data
├── tests/
│   ├── unit/
│   │   ├── test_tools.py        # Tool functions tested in isolation
│   │   └── test_schemas.py      # Schema validation tests
│   └── evals/
│       ├── cases.json           # 10 labelled evaluation cases
│       └── run_evals.py         # Precision / recall measurement
├── docs/
│   └── ARCHITECTURE.md          # System design, decisions, scale analysis
├── docker-compose.yml           # App + PostgreSQL, one command
├── Dockerfile
├── pyproject.toml               # ruff config, pytest config, dependencies
├── .pre-commit-config.yaml      # Enforced before every commit
└── README.md
```

---

## Running Locally

```bash
# 1. Clone
git clone https://github.com/gowravsai/argus
cd argus

# 2. Set environment variables
cp .env.example .env
# Add your ANTHROPIC_API_KEY and LANGSMITH_API_KEY

# 3. Start everything
docker-compose up

# 4. Hit the API
curl -X POST http://localhost:8000/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_demo_001",
    "card_id": "card_US_001",
    "amount": 1850.00,
    "merchant_name": "Lagos Electronics Hub",
    "merchant_country": "NG",
    "cardholder_country": "US",
    "timestamp": "2024-01-15T14:30:00Z",
    "previous_transaction_country": "US",
    "previous_transaction_time": "2024-01-15T14:00:00Z"
  }'

# 5. Run evals
docker exec -w /app argus-api-1 python tests/evals/run_evals.py
```

---

## API Reference

### `POST /investigate`

Submit a transaction for autonomous investigation.

**Request:**
```json
{
  "transaction_id": "txn_001",
  "card_id": "card_123",
  "amount": 1850.00,
  "merchant_name": "Merchant Name",
  "merchant_country": "NG",
  "cardholder_country": "US",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

**Response:**
```json
{
  "verdict": "BLOCK",
  "confidence": 0.90,
  "findings": [
    "Impossible travel: card used in US at 14:00, Nigeria at 14:30 — 8,000km in 30 minutes",
    "High-risk merchant category: Electronics in elevated-risk country",
    "Transaction amount $1,850 exceeds cardholder's 90-day average by 340%"
  ],
  "investigation_report": "Full reasoning chain...",
  "tools_invoked": ["get_transaction_history", "check_geolocation_plausibility", "check_merchant_risk", "get_cardholder_profile"],
  "investigation_time_ms": 1847
}
```

Full interactive docs: **[argus-production-7aa3.up.railway.app/docs](https://argus-production-7aa3.up.railway.app/docs)**

---

## The Name

In Greek mythology, **Argus Panoptes** (Ἄργος Πανόπτης — "the all-seeing") was a giant with 100 eyes. He never slept. He was assigned to guard something of immense value, watching from every angle simultaneously.

Visa guards $13 trillion in annual payment volume. Argus watches every flagged transaction the same way — with 100 eyes, never sleeping, never missing a signal.

---

## Author

**Gowrav Sai Veeramallu**
Agentic AI Engineer · Gen AI

[LinkedIn](https://linkedin.com/in/gowravsai) · [GitHub](https://github.com/gowravsai)
