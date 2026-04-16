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
    from agent.graph import run_investigation
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
        logger.info(f"[TRACE] {result.get('decision_trace')}")
        logger.info(f"[TOOLS] {list(result.get('tool_results', {}).keys())}")

        agent_output = result.get("final_output", {})

        # 🚨 Guardrail 1: Ensure tools ran
        if len(result.get("tool_results", {})) == 0:
            raise HTTPException(status_code=500, detail="No tools executed")

        # fallback (optional — you can remove later)
        if not agent_output:
            raise HTTPException(status_code=500, detail="Agent failed to produce output")

        else:
            # 🚨 Guardrail 2: Extract real signals
            all_signals = []
            for tool_data in result.get("tool_results", {}).values():
                if isinstance(tool_data, dict):
                    all_signals.extend(tool_data.get("risk_signals", []))

            risk_signals = list(set(all_signals))

            # 🚨 Guardrail 3: Decide recommendation
            score = 0

            for signal in risk_signals:
                if "cross-border" in signal.lower():
                    score += 2
                elif "unknown merchant" in signal.lower():
                    score += 1
                elif "no transaction history" in signal.lower():
                    score += 1
                elif "no historical profile" in signal.lower():
                    score += 1

            # decision
            if score >= 4:
                recommendation = "BLOCK"
            elif score >= 2:
                recommendation = "ESCALATE"
            else:
                recommendation = "ALLOW"

            reasoning = agent_output.get("reasoning", "")

            if recommendation == "BLOCK":
                reasoning = f"Transaction blocked due to multiple high-risk signals. {reasoning}"
            elif recommendation == "ESCALATE":
                reasoning = "Transaction requires manual review. " + reasoning
            else:
                reasoning = "Transaction appears safe. " + reasoning

            # 🔍 Debug (very useful)

            if recommendation == "BLOCK":
                risk_level = "CRITICAL"
                confidence_score = 0.9
            elif recommendation == "ESCALATE":
                risk_level = "MEDIUM"
                confidence_score = 0.6
            else:
                risk_level = "LOW"
                confidence_score = 0.8

            logger.info(f"[Guardrail] signals={len(risk_signals)} -> recommendation={recommendation}")
            
            report = {
                "investigation_id": str(uuid.uuid4()),
                "transaction_id": request.transaction.transaction_id,

                "recommendation": recommendation,
                
                "confidence_score": confidence_score,
                "risk_level": risk_level,
                "reasoning": reasoning,

                "risk_signals": risk_signals,

                "decision_trace": result.get("decision_trace", []),
                "tool_results": result.get("tool_results", {}),

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