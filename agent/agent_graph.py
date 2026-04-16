from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    input: dict
    messages: List[Dict[str, Any]]
    tool_results: Dict[str, Any]
    decision: str

    next_tool: str
    final_output: dict

    all_risk_signals: list
    decision_trace: list

async def agent_node(state: AgentState) -> dict:
    from langchain_groq import ChatGroq
    import os
    import json
    import re

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    txn = state["input"]

    prompt = f"""
    You are a fraud investigation agent.

    Your job is to decide the NEXT STEP in investigation.

    Available tools:
    - transaction_history
    - merchant_risk
    - velocity_check
    - geolocation_check
    - profile_check
    - finish

    Already executed tools:
    {list(state.get("tool_results", {}).keys())}

    Transaction:
    {json.dumps(txn, indent=2)}

    Rules:
    - You must choose ONE tool at a time
    - DO NOT repeat tools already executed
    - If you do not have enough information → choose a tool
    - Only choose "finish" if you are confident investigation is complete

    Respond ONLY in JSON:
    {{ "next_tool": "<tool_name>" }}
    """

    response = await llm.ainvoke(prompt)
    content = response.content

    match = re.search(r"\{.*\}", content, re.DOTALL)

    if not match:
        tool = "transaction_history"
    else:
        try:
            data = json.loads(match.group())
            tool = data.get("next_tool", "transaction_history")

            allowed = [
                "transaction_history",
                "merchant_risk",
                "velocity_check",
                "geolocation_check",
                "profile_check",
                "finish"
            ]

            if tool not in allowed:
                tool = "transaction_history"

        except Exception:
            tool = "transaction_history"

    # ✅ ADD DECISION TRACE HERE (after tool is finalized)
    decision_trace = state.get("decision_trace", [])
    decision_trace.append(f"Selected tool: {tool}")

    return {
        "next_tool": tool,
        "decision_trace": decision_trace
    }
    
import logging
logger = logging.getLogger("argus.agent")

async def tool_executor_node(state: AgentState) -> dict:
    state.setdefault("all_risk_signals", [])
    tool = state.get("next_tool")

    logger.info(f"🔧 Executing tool: {tool}")

    # map input → transaction (required by tools)
    state["transaction"] = state["input"]

    from agent.graph import (
        node_transaction_history,
        node_merchant_risk,
        node_velocity_check,
        node_geolocation_check,
        node_profile_check,
    )

    tool_map = {
        "transaction_history": node_transaction_history,
        "merchant_risk": node_merchant_risk,
        "velocity_check": node_velocity_check,
        "geolocation_check": node_geolocation_check,
        "profile_check": node_profile_check,
    }

    # safety check
    if tool not in tool_map:
        return {"tool_results": state.get("tool_results", {})}

    # execute tool
    result = await tool_map[tool](state)

    tool_results = state.get("tool_results", {})

    # ✅ FIX: correct key mapping
    key_map = {
        "transaction_history": "transaction_history",
        "merchant_risk": "merchant_risk",
        "velocity_check": "velocity",
        "geolocation_check": "geolocation",
        "profile_check": "cardholder_profile",
    }

    key = key_map.get(tool)

    if isinstance(result, dict) and key in result:
        clean_result = result[key]
    else:
        clean_result = result  # fallback safety

    tool_results[tool] = clean_result

    return {
        "tool_results": tool_results
    }


async def finish_node(state: AgentState) -> dict:
    return {
        "final_output": state["tool_results"]
    }

async def synthesise_node(state: AgentState) -> dict:
    from langchain_groq import ChatGroq
    import os, json

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    prompt = f"""
You are a fraud detection expert.

You have results from multiple investigation tools.

TOOL RESULTS:
{json.dumps(state.get("tool_results", {}), indent=2)}

RISK SIGNALS:
{state.get("all_risk_signals", [])}

Generate a final fraud investigation decision.

Respond in JSON with:
{{
  "recommendation": "BLOCK" or "ALLOW" or "ESCALATE",
  "confidence_score": float (0 to 1),
  "risk_level": "LOW" or "MEDIUM" or "HIGH" or "CRITICAL",
  "reasoning": "short explanation",
  "risk_signals": [list of key signals]
}}
"""

    response = await llm.ainvoke(prompt)
    content = response.content

    import re
    match = re.search(r"\{.*\}", content, re.DOTALL)

    if not match:
        return {"final_output": {}}

    try:
        data = json.loads(match.group())
        return {"final_output": data}
    except:
        return {"final_output": {}}

def build_agent_graph():
    builder = StateGraph(AgentState)

    # existing agent node
    builder.add_node("agent", agent_node)


    builder.add_node("tool_executor", tool_executor_node)
    builder.add_node("finish", finish_node)
    builder.add_node("synthesise", synthesise_node)

    # entry
    builder.set_entry_point("agent")

   
    builder.add_conditional_edges(
        "agent",
        lambda state: state.get("next_tool", "finish"),
        {
            "transaction_history": "tool_executor",
            "merchant_risk": "tool_executor",
            "velocity_check": "tool_executor",
            "geolocation_check": "tool_executor",
            "profile_check": "tool_executor",
            "finish": "synthesise",
        }
    )

    builder.add_edge("tool_executor", "agent")

    builder.add_edge("synthesise", END)

    return builder.compile()


agent_graph = build_agent_graph()