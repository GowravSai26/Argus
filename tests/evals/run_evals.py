"""
Argus evaluation harness.

Sends the 10 labelled cases in cases.json to a running Argus API's
POST /agent-investigate (the agent + scoring engine the demo uses) and
reports accuracy, precision and recall.

Usage:
    python tests/evals/run_evals.py                      # http://localhost:8000
    python tests/evals/run_evals.py --api https://argus-api-08ws.onrender.com
    python tests/evals/run_evals.py --pause 10           # stay under Groq rate limits
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_metrics(results: list[dict]) -> dict:
    """
    Compute precision, recall, and F1 for fraud detection.

    In fraud detection:
    - True Positive  (TP): predicted BLOCK, actually fraud
    - False Positive (FP): predicted BLOCK, actually legitimate
    - True Negative  (TN): predicted ALLOW, actually legitimate
    - False Negative (FN): predicted ALLOW, actually fraud
    - ESCALATE counts as correct when expected is ESCALATE,
      otherwise counts as a miss
    """
    tp = fp = tn = fn = escalate_correct = escalate_wrong = 0

    for r in results:
        predicted = r["predicted"]
        expected = r["expected"]

        if expected == "ESCALATE":
            if predicted == "ESCALATE":
                escalate_correct += 1
            else:
                escalate_wrong += 1
            continue

        is_fraud = expected == "BLOCK"

        if predicted == "BLOCK":
            if is_fraud:
                tp += 1
            else:
                fp += 1
        elif predicted == "ALLOW":
            if is_fraud:
                fn += 1
            else:
                tn += 1
        else:  # ESCALATE on non-escalate case
            if is_fraud:
                fn += 1  # missed fraud
            else:
                fp += 1  # false alarm

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn + escalate_correct) / len(results) if results else 0.0

    return {
        "total": len(results),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "escalate_correct": escalate_correct,
        "escalate_wrong": escalate_wrong,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_single_case(client: httpx.AsyncClient, api: str, case: dict) -> dict:
    """POST one eval case to /agent-investigate and return the result."""
    start = time.perf_counter()
    try:
        resp = await client.post(
            f"{api}/agent-investigate", json={"transaction": case["transaction"]}
        )
        resp.raise_for_status()
        report = resp.json()["report"]
        duration_ms = int((time.perf_counter() - start) * 1000)

        return {
            "id": case["id"],
            "description": case["description"],
            "expected": case["expected"],
            "predicted": report["recommendation"],
            "risk_score": report.get("risk_score"),
            "confidence": report["confidence_score"],
            "risk_level": report["risk_level"],
            "risk_signals": report["risk_signals"],
            "reasoning": report["reasoning"],
            "duration_ms": duration_ms,
            "correct": report["recommendation"] == case["expected"],
            "error": None,
        }

    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "id": case["id"],
            "description": case["description"],
            "expected": case["expected"],
            "predicted": "ERROR",
            "risk_score": None,
            "confidence": 0.0,
            "risk_level": "UNKNOWN",
            "risk_signals": [],
            "reasoning": "",
            "duration_ms": duration_ms,
            "correct": False,
            "error": str(exc),
        }


async def run_evals(cases_path: str, api: str, pause: float) -> None:
    """Run all eval cases and print a full report."""
    cases_file = Path(cases_path)
    if not cases_file.exists():
        print(f"ERROR: cases file not found: {cases_path}")
        sys.exit(1)

    with open(cases_file) as f:
        cases = json.load(f)

    print(f"\n{'=' * 60}")
    print("  ARGUS EVALUATION HARNESS")
    print(f"  Running {len(cases)} cases against {api}")
    print(f"{'=' * 60}\n")

    results = []
    async with httpx.AsyncClient(timeout=180) as client:
        for i, case in enumerate(cases, 1):
            if i > 1:
                await asyncio.sleep(pause)
            print(f"[{i:2d}/{len(cases)}] {case['id']} — {case['description'][:50]}...")
            result = await run_single_case(client, api, case)
            results.append(result)

            status = "✓" if result["correct"] else "✗"
            error_str = f" ERROR: {result['error']}" if result["error"] else ""
            print(
                f"        {status} expected={result['expected']:8s} "
                f"predicted={result['predicted']:8s} "
                f"score={result['risk_score']} "
                f"({result['duration_ms']}ms){error_str}"
            )

    # Summary
    metrics = compute_metrics(results)
    wrong = [r for r in results if not r["correct"]]

    print(f"\n{'=' * 60}")
    print("  RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total cases    : {metrics['total']}")
    print(f"  Correct        : {metrics['total'] - len(wrong)}")
    print(f"  Wrong          : {len(wrong)}")
    print("")
    print(f"  Precision      : {metrics['precision']:.4f}")
    print(f"  Recall         : {metrics['recall']:.4f}")
    print(f"  F1 Score       : {metrics['f1_score']:.4f}")
    print(f"  Accuracy       : {metrics['accuracy']:.4f}")
    print("")
    print(f"  True Positives : {metrics['true_positives']}")
    print(f"  False Positives: {metrics['false_positives']}")
    print(f"  True Negatives : {metrics['true_negatives']}")
    print(f"  False Negatives: {metrics['false_negatives']}")

    if wrong:
        print(f"\n{'=' * 60}")
        print("  MISCLASSIFIED CASES")
        print(f"{'=' * 60}")
        for r in wrong:
            print(f"\n  [{r['id']}] {r['description']}")
            print(f"  Expected: {r['expected']} | Predicted: {r['predicted']}")
            if r["risk_signals"]:
                print(f"  Signals: {', '.join(r['risk_signals'][:3])}")
            if r["error"]:
                print(f"  Error: {r['error']}")

    print(f"\n{'=' * 60}\n")

    # Exit with error code if precision or recall below threshold
    if metrics["precision"] < 0.7 or metrics["recall"] < 0.7:
        print("EVAL FAILED: precision or recall below 0.70 threshold")
        sys.exit(1)

    print("EVAL PASSED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Argus evaluation harness")
    parser.add_argument(
        "--cases", default="tests/evals/cases.json", help="Path to eval cases JSON file"
    )
    parser.add_argument(
        "--api", default="http://localhost:8000", help="Base URL of a running Argus API"
    )
    parser.add_argument(
        "--pause", type=float, default=2.0, help="Seconds between cases (Groq rate limits)"
    )
    args = parser.parse_args()
    asyncio.run(run_evals(args.cases, args.api.rstrip("/"), args.pause))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    main()
