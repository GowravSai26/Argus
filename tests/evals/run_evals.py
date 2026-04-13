"""
Argus evaluation harness.

Runs the agent against 50 labelled fraud cases and reports
precision, recall, and F1 score — the same metrics used in
production fraud systems.

Usage:
    python tests/evals/run_evals.py
    python tests/evals/run_evals.py --cases tests/evals/cases.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


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
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    accuracy = (tp + tn) / len(results) if results else 0.0

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


async def run_single_case(case: dict) -> dict:
    """Run the agent on a single eval case and return the result."""
    from api.schemas import TransactionInput
    from agent.graph import run_investigation

    start = time.perf_counter()
    try:
        transaction = TransactionInput(**case["transaction"])
        report = await run_investigation(transaction)
        duration_ms = int((time.perf_counter() - start) * 1000)

        return {
            "id": case["id"],
            "description": case["description"],
            "expected": case["expected"],
            "predicted": report.recommendation.value,
            "confidence": report.confidence_score,
            "risk_level": report.risk_level.value,
            "risk_signals": report.risk_signals,
            "reasoning": report.reasoning,
            "duration_ms": duration_ms,
            "correct": report.recommendation.value == case["expected"],
            "error": None,
        }

    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "id": case["id"],
            "description": case["description"],
            "expected": case["expected"],
            "predicted": "ERROR",
            "confidence": 0.0,
            "risk_level": "UNKNOWN",
            "risk_signals": [],
            "reasoning": "",
            "duration_ms": duration_ms,
            "correct": False,
            "error": str(exc),
        }


async def run_evals(cases_path: str) -> None:
    """Run all eval cases and print a full report."""
    cases_file = Path(cases_path)
    if not cases_file.exists():
        print(f"ERROR: cases file not found: {cases_path}")
        sys.exit(1)

    with open(cases_file) as f:
        cases = json.load(f)

    print(f"\n{'='*60}")
    print(f"  ARGUS EVALUATION HARNESS")
    print(f"  Running {len(cases)} cases...")
    print(f"{'='*60}\n")

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i:2d}/{len(cases)}] {case['id']} — {case['description'][:50]}...")
        result = await run_single_case(case)
        results.append(result)

        status = "✓" if result["correct"] else "✗"
        error_str = f" ERROR: {result['error']}" if result["error"] else ""
        print(
            f"        {status} expected={result['expected']:8s} "
            f"predicted={result['predicted']:8s} "
            f"confidence={result['confidence']:.2f} "
            f"({result['duration_ms']}ms){error_str}"
        )

    # Summary
    metrics = compute_metrics(results)
    wrong = [r for r in results if not r["correct"]]

    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    print(f"  Total cases    : {metrics['total']}")
    print(f"  Correct        : {metrics['total'] - len(wrong)}")
    print(f"  Wrong          : {len(wrong)}")
    print(f"")
    print(f"  Precision      : {metrics['precision']:.4f}")
    print(f"  Recall         : {metrics['recall']:.4f}")
    print(f"  F1 Score       : {metrics['f1_score']:.4f}")
    print(f"  Accuracy       : {metrics['accuracy']:.4f}")
    print(f"")
    print(f"  True Positives : {metrics['true_positives']}")
    print(f"  False Positives: {metrics['false_positives']}")
    print(f"  True Negatives : {metrics['true_negatives']}")
    print(f"  False Negatives: {metrics['false_negatives']}")

    if wrong:
        print(f"\n{'='*60}")
        print(f"  MISCLASSIFIED CASES")
        print(f"{'='*60}")
        for r in wrong:
            print(f"\n  [{r['id']}] {r['description']}")
            print(f"  Expected: {r['expected']} | Predicted: {r['predicted']}")
            if r["risk_signals"]:
                print(f"  Signals: {', '.join(r['risk_signals'][:3])}")
            if r["error"]:
                print(f"  Error: {r['error']}")

    print(f"\n{'='*60}\n")

    # Exit with error code if precision or recall below threshold
    if metrics["precision"] < 0.7 or metrics["recall"] < 0.7:
        print("EVAL FAILED: precision or recall below 0.70 threshold")
        sys.exit(1)

    print("EVAL PASSED")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Argus evaluation harness")
    parser.add_argument(
        "--cases",
        type=str,
        default="tests/evals/cases.json",
        help="Path to eval cases JSON file",
    )
    args = parser.parse_args()

    asyncio.run(run_evals(args.cases))