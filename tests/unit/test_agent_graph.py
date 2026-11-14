"""
Tests for the tool-picking loop in agent/agent_graph.py.

The LLM picks one tool per step. If it repeats a tool or returns something
unparseable, the loop must still end after each tool has run once, instead of
spinning until LangGraph's recursion limit.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.agent_graph import ALL_TOOLS, agent_graph

TOOL_NODES = [
    "node_transaction_history",
    "node_merchant_risk",
    "node_velocity_check",
    "node_geolocation_check",
    "node_profile_check",
]


def _initial_state() -> dict:
    return {
        "input": {"transaction_id": "txn_loop", "amount": 10.0},
        "messages": [],
        "tool_results": {},
        "decision": "",
        "next_tool": "",
        "final_output": {},
        "all_risk_signals": [],
        "decision_trace": [],
    }


def _fake_llm(tool_replies: list[str], synthesis: str) -> MagicMock:
    """Answers tool-picking prompts from tool_replies (repeating the last one
    forever) and the final synthesis prompt with `synthesis`."""
    picks = iter(tool_replies)
    last = tool_replies[-1]

    async def ainvoke(prompt: str) -> MagicMock:
        if "final fraud investigation decision" in prompt:
            return MagicMock(content=synthesis)
        return MagicMock(content=next(picks, last))

    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=ainvoke)
    return llm


async def _run(tool_replies: list[str], synthesis: str) -> dict:
    llm = _fake_llm(tool_replies, synthesis)
    patches = [patch("langchain_groq.ChatGroq", return_value=llm)]
    for name in TOOL_NODES:
        patches.append(patch(f"agent.graph.{name}", AsyncMock(return_value={"risk_signals": []})))
    for p in patches:
        p.start()
    try:
        return await agent_graph.ainvoke(_initial_state())
    finally:
        for p in patches:
            p.stop()


@pytest.mark.parametrize(
    "reply",
    [
        "not json at all",  # unparseable → used to always fall back to transaction_history
        '{"next_tool": "transaction_history"}',  # repeats the same tool every time
    ],
)
async def test_loop_runs_each_tool_once_then_finishes(reply: str) -> None:
    result = await _run([reply], '{"recommendation": "ALLOW", "reasoning": "ok"}')

    assert set(result["tool_results"]) == set(ALL_TOOLS)
    assert result["final_output"]["recommendation"] == "ALLOW"


async def test_agent_can_finish_early() -> None:
    result = await _run(
        ['{"next_tool": "merchant_risk"}', '{"next_tool": "finish"}'],
        '{"recommendation": "BLOCK", "reasoning": "risky merchant"}',
    )

    assert list(result["tool_results"]) == ["merchant_risk"]
    assert result["final_output"]["recommendation"] == "BLOCK"
