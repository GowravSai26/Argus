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