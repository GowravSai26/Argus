"""
Argus Fraud Investigation Agent — FastAPI application.

Exposes two endpoints:
  POST /investigate  — triggers the agent on a flagged transaction
  GET  /health       — liveness check for Railway / load balancers
"""

from __future__ import annotations

import time
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.schemas import (
    HealthResponse,
    InvestigateRequest,
    InvestigateResponse,
    InvestigationStatus,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("argus.api")


# ---------------------------------------------------------------------------
# Lifespan — runs once on startup and shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup: validate environment variables, warm up DB connection pool.
    Shutdown: close connections cleanly.
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    required_vars = ["ANTHROPIC_API_KEY", "LANGSMITH_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.warning(
            f"Missing environment variables: {missing}. "
            "Agent will not function without these."
        )

    logger.info("Argus API starting up")
    yield
    logger.info("Argus API shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Argus — Autonomous Fraud Investigation Agent",
    description=(
        "When a suspicious transaction is flagged, Argus investigates it like a "
        "human fraud analyst — checking transaction history, merchant risk, "
        "geolocation plausibility, velocity patterns, and cardholder behaviour — "
        "then produces a structured investigation report with a confidence score "
        "and recommendation (BLOCK / ALLOW / ESCALATE)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware — request timing
# ---------------------------------------------------------------------------


@app.middleware("http")
async def add_timing_header(request: Request, call_next):  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs for details."},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health() -> HealthResponse:
    """
    Liveness endpoint.
    Railway and any load balancer will ping this to confirm the service is up.
    """
    return HealthResponse()


@app.post(
    "/investigate",
    response_model=InvestigateResponse,
    tags=["Investigation"],
    summary="Investigate a flagged transaction",
    response_description="Structured investigation report with recommendation",
)
async def investigate(request: InvestigateRequest) -> InvestigateResponse:
    """
    Accepts a flagged transaction and runs the full autonomous investigation.

    The agent will:
    1. Pull transaction history for the card
    2. Score merchant risk
    3. Check velocity patterns
    4. Validate geolocation plausibility
    5. Compare against cardholder's normal behaviour

    Returns a structured report with confidence score and BLOCK / ALLOW / ESCALATE
    recommendation. Every step is traced in LangSmith.
    """
    from agent.graph import run_investigation

    logger.info(
        f"Investigation requested | transaction_id={request.transaction.transaction_id} "
        f"| amount=${request.transaction.amount} "
        f"| merchant_country={request.transaction.merchant_country}"
    )

    try:
        report = await run_investigation(request.transaction)
        logger.info(
            f"Investigation complete | transaction_id={request.transaction.transaction_id} "
            f"| recommendation={report.recommendation} "
            f"| confidence={report.confidence_score:.2f}"
        )
        return InvestigateResponse(status=InvestigationStatus.COMPLETED, report=report)

    except Exception as exc:
        logger.error(
            f"Investigation failed | transaction_id={request.transaction.transaction_id} "
            f"| error={exc}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    
@app.post("/agent-investigate", response_model=InvestigateResponse)
async def agent_investigate(request: InvestigateRequest) -> InvestigateResponse:
    from agent.agent_graph import agent_graph
    from datetime import datetime
    import uuid

    try:
        result = await agent_graph.ainvoke({
            "input": request.transaction.model_dump(mode="json"),
            "messages": [],
            "tool_results": {},
            "decision": "",
            "next_tool": "",
            "final_output": {},
            "all_risk_signals": [],
            "decision_trace": []
        })

        logger.info(f"Agent output: {result}")

        tool_results = result.get("tool_results", {})
        agent_output = result.get("final_output", {})

        # 🚨 Guardrail 1: Ensure tools ran
        if not tool_results:
            raise HTTPException(status_code=500, detail="No tools executed")

        if not agent_output:
            raise HTTPException(status_code=500, detail="Agent failed to produce output")

        # ───────────────────────────────
        # STEP 1: Collect signals
        # ───────────────────────────────
        all_signals = []
        for tool_data in tool_results.values():
            if isinstance(tool_data, dict):
                all_signals.extend(tool_data.get("risk_signals", []))

        raw_signals = list(set([s.lower().strip() for s in all_signals]))

        # ───────────────────────────────
        # STEP 2: Define signal weights
        # ───────────────────────────────
        SIGNAL_WEIGHTS = {
            "cross-border": 25,
            "high risk merchant": 25,
            "velocity": 35,
            "impossible travel": 40,
            "unknown merchant": 10,
        }

        MISSING_DATA = [
            "no transaction history",
            "no historical profile",
        ]

        # ───────────────────────────────
        # STEP 3: Score calculation
        # ───────────────────────────────
        score = 0
        used_signals = []

        for signal in raw_signals:

            # ❌ Ignore missing data (IMPORTANT FIX)
            if any(m in signal for m in MISSING_DATA):
                continue

            for key, weight in SIGNAL_WEIGHTS.items():
                if key in signal:
                    score += weight
                    used_signals.append(signal)
                    break

        # cap score to 100
        score = min(score, 100)

        # ───────────────────────────────
        # STEP 4: Detect user type
        # ───────────────────────────────
        txn_history = tool_results.get("transaction_history", {})
        is_new_user = txn_history.get("total_transactions_30d", 0) == 0

        # ───────────────────────────────
        # STEP 5: Decision logic
        # ───────────────────────────────
        if is_new_user:
            if score >= 70:
                recommendation = "BLOCK"
            elif score >= 40:
                recommendation = "ESCALATE"
            else:
                recommendation = "ALLOW"
        else:
            if score >= 60:
                recommendation = "BLOCK"
            elif score >= 30:
                recommendation = "ESCALATE"
            else:
                recommendation = "ALLOW"

        # ───────────────────────────────
        # STEP 6: Risk level
        # ───────────────────────────────
        if score >= 70:
            risk_level = "CRITICAL"
        elif score >= 40:
            risk_level = "HIGH"
        elif score >= 20:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # ───────────────────────────────
        # STEP 7: Confidence
        # ───────────────────────────────
        data_points = len(tool_results)
        confidence_score = round(0.6 + (0.1 * min(data_points, 4)), 2)

        # ───────────────────────────────
        # STEP 8: Reasoning
        # ───────────────────────────────
        base_reason = agent_output.get("reasoning", "")

        if recommendation == "BLOCK":
            reasoning = f"High-risk transaction detected (score={score}). {base_reason}"
        elif recommendation == "ESCALATE":
            reasoning = f"Moderate risk detected (score={score}), requires review. {base_reason}"
        else:
            reasoning = f"Low-risk transaction (score={score}). {base_reason}"

        logger.info(f"[Decision] score={score} new_user={is_new_user} -> {recommendation}")

        # ───────────────────────────────
        # FINAL RESPONSE
        # ───────────────────────────────
        report = {
            "investigation_id": str(uuid.uuid4()),
            "transaction_id": request.transaction.transaction_id,

            "recommendation": recommendation,
            "confidence_score": confidence_score,
            "risk_level": risk_level,
            "reasoning": reasoning,

            "risk_score": score,  # 🔥 NEW (0–100)

            "risk_signals": used_signals,

            "decision_trace": result.get("decision_trace", []),
            "tool_results": tool_results,

            "investigated_at": datetime.utcnow().isoformat(),
            "duration_ms": 0,
            "langsmith_run_url": None
        }

        return InvestigateResponse(
            status=InvestigationStatus.COMPLETED,
            report=report
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc