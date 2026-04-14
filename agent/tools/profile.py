"""
Cardholder profile tool.

Compares the current transaction against the cardholder's established
behavioural profile to detect anomalies.
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import asyncpg

from api.schemas import CardholderProfileResult


async def get_cardholder_profile(
    card_id: str,
    current_transaction_id: str,
    current_amount: float,
    current_category: str,
    current_country: str,
) -> CardholderProfileResult:
    """
    Build a behavioural profile from transaction history and compare
    the current transaction against it.

    A transaction that deviates significantly from established patterns
    is a strong fraud signal even if no single other check fires.
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
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        rows = await conn.fetch(
            """
            SELECT amount, merchant_category, merchant_country,
                   is_fraud, timestamp
            FROM transactions
            WHERE card_id = $1
              AND transaction_id != $2
              AND timestamp >= $3
            ORDER BY timestamp DESC
            """,
            card_id,
            current_transaction_id,
            cutoff,
        )

        fraud_rows = await conn.fetch(
            """
            SELECT COUNT(*) as fraud_count
            FROM transactions
            WHERE card_id = $1
              AND is_fraud = TRUE
            """,
            card_id,
        )

        account_row = await conn.fetchrow(
            """
            SELECT MIN(timestamp) as first_seen
            FROM transactions
            WHERE card_id = $1
            """,
            card_id,
        )

        previous_fraud_count = int(fraud_rows[0]["fraud_count"]) if fraud_rows else 0
        has_previous_fraud = previous_fraud_count > 0

        if account_row and account_row["first_seen"]:
            first_seen = account_row["first_seen"]
            if first_seen.tzinfo is None:
                first_seen = first_seen.replace(tzinfo=timezone.utc)
            account_age_days = (datetime.now(timezone.utc) - first_seen).days
        else:
            account_age_days = 0

        if not rows:
            risk_signals.append("No historical profile available — cannot assess behaviour")
            return CardholderProfileResult(
                card_id=card_id,
                account_age_days=account_age_days,
                typical_spend_range=(0.0, 0.0),
                typical_categories=[],
                typical_countries=[],
                has_previous_fraud=has_previous_fraud,
                previous_fraud_count=previous_fraud_count,
                current_transaction_fits_profile=False,
                risk_signals=risk_signals,
            )

        amounts = [float(r["amount"]) for r in rows]
        categories = [r["merchant_category"] for r in rows]
        countries = [r["merchant_country"] for r in rows]

        spend_min = min(amounts)
        spend_max = max(amounts)
        spend_avg = sum(amounts) / len(amounts)

        category_counts = Counter(categories)
        country_counts = Counter(countries)

        # Top 3 categories and countries = "typical" profile
        typical_categories = [c for c, _ in category_counts.most_common(3)]
        typical_countries = [c for c, _ in country_counts.most_common(3)]

        fits_profile = True

        # Amount anomaly — more than 3x the average
        if current_amount > spend_avg * 3:
            fits_profile = False
            risk_signals.append(
                f"Amount anomaly: ${current_amount:.2f} is {current_amount/spend_avg:.1f}x "
                f"above average spend (${spend_avg:.2f})"
            )

        # Category anomaly
        if current_category not in typical_categories:
            fits_profile = False
            risk_signals.append(
                f"Unusual category: '{current_category}' not in typical "
                f"categories {typical_categories}"
            )

        # Country anomaly
        if current_country not in typical_countries:
            fits_profile = False
            risk_signals.append(
                f"Unusual country: '{current_country}' not in typical "
                f"countries {typical_countries}"
            )

        if has_previous_fraud:
            risk_signals.append(
                f"Card has {previous_fraud_count} prior fraud incident(s) on record"
            )

        if account_age_days < 30:
            risk_signals.append(f"New account: only {account_age_days} days old")

        return CardholderProfileResult(
            card_id=card_id,
            account_age_days=account_age_days,
            typical_spend_range=(round(spend_min, 2), round(spend_max, 2)),
            typical_categories=typical_categories,
            typical_countries=typical_countries,
            has_previous_fraud=has_previous_fraud,
            previous_fraud_count=previous_fraud_count,
            current_transaction_fits_profile=fits_profile,
            risk_signals=risk_signals,
        )

    finally:
        await conn.close()