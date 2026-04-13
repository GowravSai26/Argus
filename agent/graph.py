"""
Argus — LangGraph investigation state machine.

The agent moves through a fixed sequence of investigation nodes,
accumulating evidence at each step, then synthesises a final verdict.

State flows:
  START
    → transaction_history
    → merchant_risk
    → velocity_check
    → geolocation_check
    → profile_check
    → synthesise
  END
"""

from __future__ import annotations

import time
from typing import Any, TypedDict

from langchain_anthropic import ChatAnthropic
from langsmith import traceable
from langgraph.graph import END, START, StateGraph

from api.schemas import (
    InvestigationReport,
    Recommendation,
    RiskLevel,
    TransactionInput,
)


# ---------------------------------------------------------------------------
# Agent state — passed between every node
# ---------------------------------------------------------------------------


class InvestigationState(TypedDict):
    """
    Shared state object that flows through the LangGraph.

    Every node reads from this and writes back to it.
    The state accumulates evidence as the investigation progresses.
    """

    transaction: dict[str, Any]
    transaction_history: dict[str, Any] | None
    merchant_risk: dict[str, Any] | None
    velocity: dict[str, Any] | None
    geolocation: dict[str, Any] | None
    cardholder_profile: dict[str, Any] | None
    all_risk_signals: list[str]
    report: dict[str, Any] | None
    start_time_ms: int


# ---------------------------------------------------------------------------
# Node functions — one per investigation step
# ---------------------------------------------------------------------------


async def node_transaction_history(state: InvestigationState) -> dict[str, Any]:
    """Pull 30-day transaction history and detect velocity/amount anomalies."""
    from agent.tools.transaction import get_transaction_history

    txn = state["transaction"]
    result = await get_transaction_history(
        card_id=txn["card_id"],
        current_transaction_id=txn["transaction_id"],
    )
    return {
        "transaction_history": result.model_dump(),
        "all_risk_signals": state["all_risk_signals"] + result.risk_signals,
    }


async def node_merchant_risk(state: InvestigationState) -> dict[str, Any]:
    """Score the merchant's fraud rate, chargeback rate, and category risk."""
    from agent.tools.merchant import get_merchant_risk

    txn = state["transaction"]
    result = await get_merchant_risk(
        merchant_id=txn["merchant_id"],
        merchant_category=txn["merchant_category"],
        merchant_country=txn["merchant_country"],
    )
    return {
        "merchant_risk": result.model_dump(),
        "all_risk_signals": state["all_risk_signals"] + result.risk_signals,
    }


async def node_velocity_check(state: InvestigationState) -> dict[str, Any]:
    """Detect rapid repeated transactions — card testing and smurfing patterns."""
    from agent.tools.velocity import check_velocity

    txn = state["transaction"]
    result = await check_velocity(
        card_id=txn["card_id"],
        current_transaction_id=txn["transaction_id"],
    )
    return {
        "velocity": result.model_dump(),
        "all_risk_signals": state["all_risk_signals"] + result.risk_signals,
    }


async def node_geolocation_check(state: InvestigationState) -> dict[str, Any]:
    """Detect impossible travel between consecutive transactions."""
    from agent.tools.geolocation import check_geolocation
    from datetime import datetime

    txn = state["transaction"]
    timestamp = txn["timestamp"]
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)

    result = await check_geolocation(
        card_id=txn["card_id"],
        current_transaction_id=txn["transaction_id"],
        transaction_country=txn["merchant_country"],
        cardholder_country=txn["cardholder_country"],
        transaction_timestamp=timestamp,
    )
    return {
        "geolocation": result.model_dump(),
        "all_risk_signals": state["all_risk_signals"] + result.risk_signals,
    }


async def node_profile_check(state: InvestigationState) -> dict[str, Any]:
    """Compare transaction against cardholder's established behaviour profile."""
    from agent.tools.profile import get_cardholder_profile

    txn = state["transaction"]
    result = await get_cardholder_profile(
        card_id=txn["card_id"],
        current_transaction_id=txn["transaction_id"],
        current_amount=txn["amount"],
        current_category=txn["merchant_category"],
        current_country=txn["merchant_country"],
    )
    return {
        "cardholder_profile": result.model_dump(),
        "all_risk_signals": state["all_risk_signals"] + result.risk_signals,
    }


async def node_synthesise(state: InvestigationState) -> dict[str, Any]:
    """
    Call Claude to synthesise all evidence into a final verdict.

    Claude receives all tool outputs and risk signals, then produces:
    - A recommendation (BLOCK / ALLOW / ESCALATE)
    - A confidence score (0.0 – 1.0)
    - A human-readable reasoning paragraph
    """
    import json
    import os

    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=1024,
    )

    txn = state["transaction"]
    risk_signals = state["all_risk_signals"]

    evidence_summary = {
        "transaction": txn,
        "risk_signals_detected": risk_signals,
        "transaction_history": state.get("transaction_history"),
        "merchant_risk": state.get("merchant_risk"),
        "velocity": state.get("velocity"),
        "geolocation": state.get("geolocation"),
        "cardholder_profile": state.get("cardholder_profile"),
    }

    prompt = f"""You are Argus, an expert fraud analyst at a major payments company.

You have completed a full automated investigation of a flagged transaction.
Your job is to synthesise all evidence and deliver a final verdict.

TRANSACTION UNDER INVESTIGATION:
{json.dumps(txn, indent=2, default=str)}

INVESTIGATION EVIDENCE:
{json.dumps(evidence_summary, indent=2, default=str)}

Based on all evidence above, respond with a JSON object in exactly this format:
{{
  "recommendation": "BLOCK" | "ALLOW" | "ESCALATE",
  "confidence_score": <float between 0.0 and 1.0>,
  "reasoning": "<one clear paragraph explaining your decision, citing specific evidence>"
}}

Decision guide:
- BLOCK: Strong fraud signals, high confidence (confidence >= 0.75)
- ALLOW: Clean profile, no significant signals (confidence >= 0.75)
- ESCALATE: Ambiguous evidence, human review needed (confidence < 0.75)

Respond with valid JSON only. No preamble, no explanation outside the JSON."""

    response = await llm.ainvoke(prompt)
    content = response.content

    # Parse Claude's response
    import re
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if not json_match:
        raise ValueError(f"Claude returned non-JSON response: {content}")

    verdict = json.loads(json_match.group())

    # Derive risk level from confidence score and recommendation
    recommendation = Recommendation(verdict["recommendation"])
    confidence = float(verdict["confidence_score"])

    if recommendation == Recommendation.BLOCK:
        risk_level = RiskLevel.CRITICAL if confidence >= 0.9 else RiskLevel.HIGH
    elif recommendation == Recommendation.ESCALATE:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW

    duration_ms = int(time.time() * 1000) - state["start_time_ms"]

    report = InvestigationReport(
        transaction_id=txn["transaction_id"],
        recommendation=recommendation,
        confidence_score=confidence,
        risk_level=risk_level,
        reasoning=verdict["reasoning"],
        risk_signals=risk_signals,
        tool_results={
            "transaction_history": state.get("transaction_history"),
            "merchant_risk": state.get("merchant_risk"),
            "velocity": state.get("velocity"),
            "geolocation": state.get("geolocation"),
            "cardholder_profile": state.get("cardholder_profile"),
        },
        duration_ms=duration_ms,
    )

    return {"report": report.model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph investigation state machine."""
    graph = StateGraph(InvestigationState)

    # Register nodes
    graph.add_node("transaction_history", node_transaction_history)
    graph.add_node("merchant_risk", node_merchant_risk)
    graph.add_node("velocity_check", node_velocity_check)
    graph.add_node("geolocation_check", node_geolocation_check)
    graph.add_node("profile_check", node_profile_check)
    graph.add_node("synthesise", node_synthesise)

    # Define edges — fixed linear investigation pipeline
    graph.add_edge(START, "transaction_history")
    graph.add_edge("transaction_history", "merchant_risk")
    graph.add_edge("merchant_risk", "velocity_check")
    graph.add_edge("velocity_check", "geolocation_check")
    graph.add_edge("geolocation_check", "profile_check")
    graph.add_edge("profile_check", "synthesise")
    graph.add_edge("synthesise", END)

    return graph.compile()


# Compile once at module load — reused across all requests
investigation_graph = build_graph()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@traceable(name="argus-investigation")
async def run_investigation(transaction: TransactionInput) -> InvestigationReport:
    """
    Run a full fraud investigation for a flagged transaction.

    This is the single entry point called by the FastAPI route.
    Every invocation is automatically traced in LangSmith.

    Args:
        transaction: The flagged transaction to investigate.

    Returns:
        InvestigationReport with recommendation, confidence, and full reasoning.
    """
    initial_state: InvestigationState = {
        "transaction": transaction.model_dump(mode="json"),
        "transaction_history": None,
        "merchant_risk": None,
        "velocity": None,
        "geolocation": None,
        "cardholder_profile": None,
        "all_risk_signals": [],
        "report": None,
        "start_time_ms": int(time.time() * 1000),
    }

    final_state = await investigation_graph.ainvoke(initial_state)

    if final_state["report"] is None:
        raise RuntimeError("Investigation completed but produced no report")

    return InvestigationReport(**final_state["report"])