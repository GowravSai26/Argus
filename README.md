# 👁 Argus — Autonomous Fraud Investigation Agent

> *Named after Argus Panoptes, the hundred-eyed giant of Greek mythology who never slept.*

When a card transaction is flagged, a human fraud analyst spends 15–30 minutes checking it by hand: transaction history, the merchant, where the card was last used, how fast it is being used. **Argus does that investigation with an AI agent.** The agent decides which checks to run, collects the evidence from a Postgres database, and a deterministic scoring engine turns that evidence into a **risk score (0–100)** and a verdict: `BLOCK`, `ALLOW` or `ESCALATE`.

The one design decision that matters most: **the LLM gathers evidence, but it does not make the final call.** A plain, testable scoring function does.

[![Live demo](https://img.shields.io/badge/Live_demo-Vercel-000?style=flat)](https://argus-seven-black.vercel.app/)
[![API](https://img.shields.io/badge/API-Render-46E3B7?style=flat)](https://argus-api-08ws.onrender.com/docs)
[![CI](https://github.com/GowravSai26/Argus/actions/workflows/ci.yml/badge.svg)](https://github.com/GowravSai26/Argus/actions/workflows/ci.yml)

---

## 🔴 Live Demo

**[argus-seven-black.vercel.app](https://argus-seven-black.vercel.app/)** — pick a scenario or edit the transaction JSON and watch the agent investigate it.

> The API runs on Render's free tier, which sleeps when nobody uses it. The page wakes it up as soon as it opens; the first investigation can take up to a minute. After that, an investigation typically takes about 10 seconds (the agent makes six LLM calls, and Groq's free tier rate-limits them).

Interactive API docs: **[argus-api-08ws.onrender.com/docs](https://argus-api-08ws.onrender.com/docs)**

---

## How it works

1. A flagged transaction arrives at the FastAPI endpoint and is validated with Pydantic.
2. A **LangGraph** agent (GPT-OSS 120B on Groq, set by `GROQ_MODEL`) decides which tools to call, one at a time, based on what it has seen so far:

   | Tool | What it checks |
   |---|---|
   | `get_transaction_history` | 30-day spend, transaction count, amount anomalies |
   | `check_merchant_risk` | Merchant fraud rate, chargeback rate, high-risk category |
   | `check_velocity` | Transactions in the last 1h / 24h (card testing) |
   | `check_geolocation_plausibility` | Is the travel since the last transaction physically possible? |
   | `get_cardholder_profile` | Home country, usual categories, account age |

3. Every tool returns structured data plus human-readable **risk signals**.
4. The **scoring engine** (in `api/main.py`) weights those signals, ignores missing data, and returns the verdict.

## 🧠 Scoring engine (deterministic guardrail)

| Signal | Weight |
|---|---|
| Impossible travel | +40 |
| Velocity anomaly | +35 |
| Cross-border transaction | +25 |
| High-risk merchant / category | +25 |
| Amount anomaly | +25 |
| High daily volume | +25 |
| Unusual country | +20 |
| Rapid country change | +20 |
| Unusual category | +15 |
| New account | +15 |
| High chargeback rate | +15 |
| Unknown merchant | +10 |

The score is capped at 100.

| Score | Verdict |
|---|---|
| 0–29 | ALLOW |
| 30–59 | ESCALATE |
| 60+ | BLOCK |

**Absence of data is not a fraud signal.** A brand-new card with no history is treated as *uncertain*, not *risky*, so new customers are not blocked just for being new.

Why not let the LLM decide? LLM verdicts can change between runs and are hard to audit. Splitting the job means the LLM handles the open-ended part (which evidence to gather), while the decision is repeatable and can be unit-tested and explained line by line.

---

## Evaluation

`tests/evals/run_evals.py` sends 10 hand-labelled cases (`tests/evals/cases.json`) to a running API's `POST /agent-investigate` — the same agent + scoring engine the demo uses. Latest run, against the **live API** on 2026-11-14:

| Case | Scenario | Expected | Got |
|---|---|---|---|
| eval_001 | US card used in Nigeria 30 min after a US purchase | BLOCK | ✅ BLOCK |
| eval_002 | Normal grocery purchase in home country | ALLOW | ✅ ALLOW |
| eval_003 | High-value electronics at a new merchant abroad | BLOCK | ✅ BLOCK |
| eval_004 | Coffee shop, cardholder known to travel | ALLOW | ✅ ALLOW |
| eval_005 | Card testing — 5 micro-transactions in 20 minutes | BLOCK | ❌ ESCALATE (score 35) |
| eval_006 | Ambiguous cross-border, plausible timing | ESCALATE | ✅ ESCALATE |
| eval_007 | Crypto exchange, large amount | BLOCK | ❌ ESCALATE (score 35) |
| eval_008 | Pharmacy, low amount, home country | ALLOW | ✅ ALLOW |
| eval_009 | Wire transfer at an odd hour from abroad | BLOCK | ✅ BLOCK |
| eval_010 | Recurring utilities bill | ALLOW | ✅ ALLOW |

**8/10 correct.** No legitimate transaction was blocked (precision 1.0); two fraud cases were escalated to a human instead of blocked (recall 0.6). Each case took 7–16 s on the free tier.

**Limitations, stated plainly:**
- **The eval cases' cards and merchants are not in the seed database.** Every case therefore runs with no transaction history and an unknown merchant, so velocity, impossible-travel and profile checks never fire — the verdicts come only from category, country and amount signals. That is why the card-testing case (eval_005) misses, and why eval_001 is "right" without actually detecting impossible travel. Adding matching history to `data/seed.sql` is the next step.
- These are 10 scenarios I wrote myself, on synthetic data from `data/generate.py`. They show the pipeline behaves as designed; they are **not** a measure of real-world fraud detection accuracy.
- `confidence_score` currently reflects how many tools returned data, not a calibrated probability.
- Signals are matched to weights by keyword, so a reworded signal from a tool would not be scored.
- The API has no authentication or rate limiting, and allows any origin (CORS `*`).

Next steps: seed history for the eval cards, evaluate on a public labelled dataset (e.g. the Kaggle credit-card fraud set), calibrate confidence, and replace keyword matching with typed signal codes.

---

## Architecture

```
            POST /agent-investigate  {transaction}
                          │
┌─────────────────────────▼───────────────────────────┐
│ FastAPI (api/main.py) — Pydantic validation         │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│ LangGraph agent (agent/agent_graph.py)              │
│   LLM picks next tool → tool runs → repeat → done   │
└──────────┬──────────────────────────────┬───────────┘
           │                              │
┌──────────▼──────────┐       ┌───────────▼──────────┐
│ PostgreSQL (Neon)   │       │ Groq — GPT-OSS 120B  │
│ transactions,       │       │ tool selection +     │
│ merchants, profiles │       │ written reasoning    │
└─────────────────────┘       └──────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│ Scoring engine → risk score, verdict, risk level    │
└─────────────────────────────────────────────────────┘
```

There are two endpoints:
- `POST /agent-investigate` — the agentic flow above, used by the demo.
- `POST /investigate` — an earlier fixed pipeline (`agent/graph.py`) that runs every tool in order; it supports optional LangSmith tracing.

---

## Tech stack

| Layer | Technology |
|---|---|
| Agent | LangGraph |
| LLM | GPT-OSS 120B via Groq (any Groq model via `GROQ_MODEL`) |
| API | FastAPI + Pydantic v2 |
| Database | PostgreSQL (asyncpg) |
| Frontend | Single static HTML page on Vercel |
| Hosting | Render (API, free tier) + Neon (Postgres, free tier) |
| Containers | Docker, docker-compose |
| CI | GitHub Actions — ruff lint, unit tests, Docker build |

---

## Project structure

```
argus/
├── .github/workflows/ci.yml   # Lint + unit tests on every push
├── agent/
│   ├── agent_graph.py         # LangGraph agent used by /agent-investigate
│   ├── graph.py               # Fixed pipeline used by /investigate
│   ├── db.py                  # DB connection settings + first-run seeding
│   └── tools/                 # transaction, merchant, velocity, geolocation, profile
├── api/
│   ├── main.py                # FastAPI app + scoring engine
│   └── schemas.py             # Request / response models
├── data/
│   ├── generate.py            # Synthetic data generator
│   └── seed.sql               # Schema + seed data
├── frontend/index.html        # Demo UI
├── tests/
│   ├── unit/test_tools.py     # Tools tested with a mocked database
│   ├── unit/test_agent_graph.py # The tool-picking loop always ends
│   └── evals/                 # 10 labelled cases + runner (calls the API)
├── Dockerfile
├── docker-compose.yml
└── render.yaml                # Render deploy blueprint
```

---

## Run locally

```bash
git clone https://github.com/GowravSai26/Argus
cd Argus
cp .env.example .env        # add your free GROQ_API_KEY from console.groq.com
docker-compose up
```

Then open http://localhost:8000/docs, or try:

```bash
curl -X POST http://localhost:8000/agent-investigate \
  -H "Content-Type: application/json" \
  -d '{"transaction": {
        "transaction_id": "txn_demo_001",
        "card_id": "card_US_001",
        "amount": 1850.00,
        "merchant_id": "merch_NG_001",
        "merchant_name": "Lagos Electronics Hub",
        "merchant_category": "Electronics",
        "merchant_country": "NG",
        "merchant_city": "Lagos",
        "transaction_country": "NG",
        "cardholder_country": "US",
        "timestamp": "2026-06-19T10:30:00Z",
        "is_online": false
      }}'
```

Run the evals against the local API, or the live one:

```bash
python tests/evals/run_evals.py
python tests/evals/run_evals.py --api https://argus-api-08ws.onrender.com --pause 15
```

## Deploy for free (Render + Neon)

1. **Database:** create a free project at [neon.com](https://neon.com) and copy its connection string.
2. **API:** on [render.com](https://render.com), choose *New → Blueprint* and pick this repo. Render reads `render.yaml` and asks for two values: `DATABASE_URL` (the Neon string) and `GROQ_API_KEY`.
3. On first start, the API loads `data/seed.sql` into the empty database by itself.
4. If Render gives your service a different URL than `argus-api-08ws.onrender.com`, update `API_BASE` near the bottom of `frontend/index.html`.

---

## Example response

```json
{
  "recommendation": "BLOCK",
  "risk_score": 75,
  "risk_level": "CRITICAL",
  "confidence_score": 1.0,
  "reasoning": "High-risk transaction detected (score=75). ...",
  "risk_signals": [
    "cross-border transaction: card from in, used in ae",
    "high-risk merchant category: electronics",
    "amount anomaly: ..."
  ],
  "tool_results": { "transaction_history": {}, "merchant_risk": {}, "velocity": {}, "geolocation": {}, "cardholder_profile": {} }
}
```

---

## Author

**Gowrav Sai Veeramallu** — Agentic AI Engineer · Gen AI
[LinkedIn](https://www.linkedin.com/in/Gowrav-Sai-Veeramallu) · [GitHub](https://github.com/GowravSai26)
