"""
Velocity check tool.

Detects rapid repeated transactions — a primary signal of card testing fraud
where attackers make many small purchases to verify a stolen card works.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import asyncpg

from api.schemas import VelocityResult

# Thresholds — tunable without code changes in production
VELOCITY_LIMITS = {
    "max_transactions_1h": 3,
    "max_transactions_24h": 10,
    "max_amount_1h": 1000.0,
    "max_amount_24h": 3000.0,
    "max_unique_merchants_24h": 5,
    "max_unique_countries_24h": 2,
}


async def check_velocity(
    card_id: str,
    current_transaction_id: str,
) -> VelocityResult:
    """
    Check transaction velocity for a card.

    Velocity fraud = many transactions in a short window.
    This catches card testing, account takeover, and smurfing patterns.
    """
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "argus"),
        password=os.getenv("POSTGRES_PASSWORD", "argus_secret"),
        database=os.getenv("POSTGRES_DB", "argus_db"),
    )
    risk_signals: list[str] = []

    try:
        now = datetime.now(timezone.utc)
        cutoff_1h = now - timedelta(hours=1)
        cutoff_24h = now - timedelta(hours=24)

        rows_24h = await conn.fetch(
            """
            SELECT amount, merchant_id, merchant_country, timestamp
            FROM transactions
            WHERE card_id = $1
              AND transaction_id != $2
              AND timestamp >= $3
            ORDER BY timestamp DESC
            """,
            card_id,
            current_transaction_id,
            cutoff_24h,
        )

        rows_1h = [r for r in rows_24h if r["timestamp"] >= cutoff_1h]

        txns_1h = len(rows_1h)
        txns_24h = len(rows_24h)
        amount_1h = sum(float(r["amount"]) for r in rows_1h)
        amount_24h = sum(float(r["amount"]) for r in rows_24h)
        unique_merchants = len({r["merchant_id"] for r in rows_24h})
        unique_countries = len({r["merchant_country"] for r in rows_24h})

        velocity_exceeded = False

        if txns_1h >= VELOCITY_LIMITS["max_transactions_1h"]:
            velocity_exceeded = True
            risk_signals.append(
                f"Velocity exceeded: {txns_1h} transactions in last hour "
                f"(limit: {VELOCITY_LIMITS['max_transactions_1h']})"
            )
        if txns_24h >= VELOCITY_LIMITS["max_transactions_24h"]:
            velocity_exceeded = True
            risk_signals.append(
                f"Velocity exceeded: {txns_24h} transactions in 24h "
                f"(limit: {VELOCITY_LIMITS['max_transactions_24h']})"
            )
        if amount_1h >= VELOCITY_LIMITS["max_amount_1h"]:
            velocity_exceeded = True
            risk_signals.append(
                f"High spend velocity: ${amount_1h:.2f} in last hour"
            )
        if unique_countries >= VELOCITY_LIMITS["max_unique_countries_24h"]:
            velocity_exceeded = True
            risk_signals.append(
                f"Multiple countries in 24h: {unique_countries} countries"
            )
        if unique_merchants >= VELOCITY_LIMITS["max_unique_merchants_24h"]:
            risk_signals.append(
                f"Many unique merchants in 24h: {unique_merchants}"
            )

        return VelocityResult(
            card_id=card_id,
            transactions_last_1h=txns_1h,
            transactions_last_24h=txns_24h,
            unique_merchants_last_24h=unique_merchants,
            unique_countries_last_24h=unique_countries,
            amount_last_1h=round(amount_1h, 2),
            amount_last_24h=round(amount_24h, 2),
            velocity_exceeded=velocity_exceeded,
            risk_signals=risk_signals,
        )

    finally:
        await conn.close()