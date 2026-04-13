"""
Merchant risk tool.

Looks up the merchant's fraud rate, chargeback rate, and category risk.
"""

from __future__ import annotations

import os

import asyncpg

from api.schemas import MerchantRiskResult

HIGH_RISK_CATEGORIES = {
    "Electronics", "Jewelry", "Gift Cards", "Crypto Exchange",
    "Wire Transfer", "Gambling", "Adult Entertainment",
}


async def get_merchant_risk(
    merchant_id: str,
    merchant_category: str,
    merchant_country: str,
) -> MerchantRiskResult:
    """
    Fetch merchant risk profile from the database.

    Falls back to category-level heuristics if merchant is unknown.
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
        row = await conn.fetchrow(
            """
            SELECT merchant_name, category, country, fraud_rate,
                   chargeback_rate, is_high_risk, days_since_first_seen
            FROM merchants
            WHERE merchant_id = $1
            """,
            merchant_id,
        )

        is_high_risk_category = merchant_category in HIGH_RISK_CATEGORIES

        if row is None:
            # Unknown merchant — use heuristics
            risk_signals.append("Merchant not found in database — unknown merchant")
            if is_high_risk_category:
                risk_signals.append(f"High-risk merchant category: {merchant_category}")

            return MerchantRiskResult(
                merchant_id=merchant_id,
                merchant_name="Unknown",
                category=merchant_category,
                fraud_rate_percent=5.0 if is_high_risk_category else 1.0,
                chargeback_rate_percent=2.0 if is_high_risk_category else 0.5,
                is_high_risk_category=is_high_risk_category,
                country=merchant_country,
                days_since_first_seen=0,
                risk_signals=risk_signals,
            )

        fraud_rate = float(row["fraud_rate"]) * 100
        chargeback_rate = float(row["chargeback_rate"]) * 100

        if row["is_high_risk"]:
            risk_signals.append(f"Merchant flagged as high risk (fraud rate: {fraud_rate:.2f}%)")
        if fraud_rate > 5.0:
            risk_signals.append(f"Elevated merchant fraud rate: {fraud_rate:.2f}%")
        if chargeback_rate > 3.0:
            risk_signals.append(f"High chargeback rate: {chargeback_rate:.2f}%")
        if row["days_since_first_seen"] < 30:
            risk_signals.append(f"New merchant: only {row['days_since_first_seen']} days old")
        if is_high_risk_category:
            risk_signals.append(f"High-risk category: {merchant_category}")

        return MerchantRiskResult(
            merchant_id=merchant_id,
            merchant_name=row["merchant_name"],
            category=row["category"],
            fraud_rate_percent=round(fraud_rate, 3),
            chargeback_rate_percent=round(chargeback_rate, 3),
            is_high_risk_category=is_high_risk_category,
            country=row["country"],
            days_since_first_seen=row["days_since_first_seen"],
            risk_signals=risk_signals,
        )

    finally:
        await conn.close()