"""
Transaction history tool.

Queries PostgreSQL for the card's recent transaction history and
derives risk signals from spending patterns.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from api.schemas import TransactionHistoryResult


async def get_db_connection() -> asyncpg.Connection:
    """Create a single database connection."""
    return await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "argus"),
        password=os.getenv("POSTGRES_PASSWORD", "argus_secret"),
        database=os.getenv("POSTGRES_DB", "argus_db"),
    )


async def get_transaction_history(
    card_id: str,
    current_transaction_id: str,
) -> TransactionHistoryResult:
    """
    Fetch transaction history for a card and derive risk signals.

    Args:
        card_id: The hashed card identifier.
        current_transaction_id: Excluded from history to avoid self-reference.

    Returns:
        TransactionHistoryResult with stats and risk signals.
    """
    conn = await get_db_connection()
    risk_signals: list[str] = []

    try:
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)

        # Fetch all transactions for this card in the last 30 days
        rows = await conn.fetch(
            """
            SELECT amount, merchant_category, merchant_country, timestamp
            FROM transactions
            WHERE card_id = $1
              AND transaction_id != $2
              AND timestamp >= $3
            ORDER BY timestamp DESC
            """,
            card_id,
            current_transaction_id,
            cutoff_30d,
        )

        if not rows:
            risk_signals.append("No transaction history found — new or inactive card")
            return TransactionHistoryResult(
                card_id=card_id,
                total_transactions_30d=0,
                total_spend_30d=0.0,
                average_transaction_amount=0.0,
                max_transaction_amount=0.0,
                transactions_in_last_1h=0,
                transactions_in_last_24h=0,
                most_common_merchant_category="unknown",
                most_common_country="unknown",
                risk_signals=risk_signals,
            )

        amounts = [float(r["amount"]) for r in rows]
        timestamps = [r["timestamp"] for r in rows]
        categories = [r["merchant_category"] for r in rows]
        countries = [r["merchant_country"] for r in rows]

        total_spend = sum(amounts)
        avg_amount = total_spend / len(amounts)
        max_amount = max(amounts)

        txns_1h = sum(1 for t in timestamps if t >= cutoff_1h)
        txns_24h = sum(1 for t in timestamps if t >= cutoff_24h)

        most_common_category = max(set(categories), key=categories.count)
        most_common_country = max(set(countries), key=countries.count)

        # Risk signal detection
        if txns_1h >= 3:
            risk_signals.append(f"High velocity: {txns_1h} transactions in last hour")
        if txns_24h >= 10:
            risk_signals.append(f"High daily volume: {txns_24h} transactions in 24h")
        if max_amount > avg_amount * 5:
            risk_signals.append(
                f"Unusually large transaction: max ${max_amount:.2f} vs avg ${avg_amount:.2f}"
            )

        return TransactionHistoryResult(
            card_id=card_id,
            total_transactions_30d=len(rows),
            total_spend_30d=round(total_spend, 2),
            average_transaction_amount=round(avg_amount, 2),
            max_transaction_amount=round(max_amount, 2),
            transactions_in_last_1h=txns_1h,
            transactions_in_last_24h=txns_24h,
            most_common_merchant_category=most_common_category,
            most_common_country=most_common_country,
            risk_signals=risk_signals,
        )

    finally:
        await conn.close()