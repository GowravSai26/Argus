"""
Synthetic fraud data generator for Argus.

Generates realistic transaction data with a configurable fraud rate.
Run this script directly to populate the database with test data.

Usage:
    python data/generate.py --transactions 1000 --fraud-rate 0.08
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker

fake = Faker()
rng = random.Random(42)  # seeded for reproducibility

# ---------------------------------------------------------------------------
# Constants — realistic fraud patterns
# ---------------------------------------------------------------------------

HIGH_RISK_CATEGORIES = [
    "Electronics", "Jewelry", "Gift Cards", "Crypto Exchange",
    "Wire Transfer", "Gambling", "Adult Entertainment",
]

LOW_RISK_CATEGORIES = [
    "Grocery", "Gas Station", "Pharmacy", "Coffee Shop",
    "Restaurant", "Clothing", "Utilities", "Healthcare",
]

HIGH_RISK_COUNTRIES = ["NG", "RO", "UA", "VN", "PK", "ID"]
LOW_RISK_COUNTRIES  = ["US", "GB", "CA", "AU", "DE", "JP", "FR"]

ALL_COUNTRIES = HIGH_RISK_COUNTRIES + LOW_RISK_COUNTRIES


# ---------------------------------------------------------------------------
# Card and merchant pools
# ---------------------------------------------------------------------------

def make_card_pool(n: int = 200) -> list[dict]:
    """Generate a pool of synthetic cardholders with stable profiles."""
    cards = []
    for _ in range(n):
        home_country = rng.choice(LOW_RISK_COUNTRIES)
        cards.append({
            "card_id": f"card_{uuid.uuid4().hex[:8]}",
            "home_country": home_country,
            "typical_categories": rng.sample(LOW_RISK_CATEGORIES, k=3),
            "typical_spend_min": rng.uniform(10, 50),
            "typical_spend_max": rng.uniform(100, 500),
            "account_age_days": rng.randint(30, 3650),
            "has_previous_fraud": rng.random() < 0.05,
        })
    return cards


def make_merchant_pool(n: int = 100) -> list[dict]:
    """Generate a pool of synthetic merchants with risk profiles."""
    merchants = []
    for _ in range(n):
        is_high_risk = rng.random() < 0.2
        category = rng.choice(
            HIGH_RISK_CATEGORIES if is_high_risk else LOW_RISK_CATEGORIES
        )
        country = rng.choice(
            HIGH_RISK_COUNTRIES if is_high_risk else LOW_RISK_COUNTRIES
        )
        merchants.append({
            "merchant_id": f"merch_{uuid.uuid4().hex[:6]}",
            "merchant_name": fake.company(),
            "category": category,
            "country": country,
            "city": fake.city(),
            "fraud_rate": rng.uniform(0.15, 0.40) if is_high_risk else rng.uniform(0.001, 0.02),
            "chargeback_rate": rng.uniform(0.05, 0.15) if is_high_risk else rng.uniform(0.001, 0.01),
            "days_since_first_seen": rng.randint(1, 2000),
            "is_high_risk": is_high_risk,
        })
    return merchants


# ---------------------------------------------------------------------------
# Transaction generator
# ---------------------------------------------------------------------------

def generate_transaction(
    card: dict,
    merchant: dict,
    is_fraud: bool,
    base_time: datetime,
) -> dict:
    """Generate a single synthetic transaction."""

    if is_fraud:
        # Fraud patterns: high amount, wrong country, high-risk merchant
        amount = rng.uniform(500, 5000)
        merchant_country = rng.choice(HIGH_RISK_COUNTRIES)
        is_online = rng.random() < 0.8
        time_offset = timedelta(
            days=rng.randint(0, 30),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
    else:
        # Legitimate patterns: normal amount, home country, typical category
        amount = rng.uniform(
            card["typical_spend_min"],
            card["typical_spend_max"],
        )
        merchant_country = card["home_country"]
        is_online = rng.random() < 0.3
        time_offset = timedelta(
            days=rng.randint(0, 30),
            hours=rng.randint(6, 22),  # daytime hours
            minutes=rng.randint(0, 59),
        )

    return {
        "transaction_id": f"txn_{uuid.uuid4().hex[:8]}",
        "card_id": card["card_id"],
        "merchant_id": merchant["merchant_id"],
        "amount": round(amount, 2),
        "merchant_category": merchant["category"],
        "merchant_country": merchant_country,
        "merchant_city": merchant["city"],
        "cardholder_country": card["home_country"],
        "timestamp": (base_time + time_offset).isoformat(),
        "is_online": is_online,
        "is_fraud": is_fraud,
        "device_fingerprint": uuid.uuid4().hex if is_online else None,
    }


# ---------------------------------------------------------------------------
# SQL generation
# ---------------------------------------------------------------------------

def transactions_to_sql(transactions: list[dict]) -> str:
    """Convert transaction dicts to INSERT SQL statements."""
    lines = [
        "-- Auto-generated by data/generate.py",
        "-- Do not edit manually\n",
        "INSERT INTO transactions (",
        "    transaction_id, card_id, merchant_id, amount,",
        "    merchant_category, merchant_country, merchant_city,",
        "    cardholder_country, timestamp, is_online, is_fraud, device_fingerprint",
        ") VALUES",
    ]

    values = []
    for t in transactions:
        device = f"'{t['device_fingerprint']}'" if t["device_fingerprint"] else "NULL"
        values.append(
            f"    ('{t['transaction_id']}', '{t['card_id']}', '{t['merchant_id']}', "
            f"{t['amount']}, '{t['merchant_category']}', '{t['merchant_country']}', "
            f"'{t['merchant_city']}', '{t['cardholder_country']}', "
            f"'{t['timestamp']}', {str(t['is_online']).upper()}, "
            f"{str(t['is_fraud']).upper()}, {device})"
        )

    lines.append(",\n".join(values) + ";")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(n_transactions: int = 1000, fraud_rate: float = 0.08) -> list[dict]:
    """Generate n_transactions with the given fraud rate."""
    cards = make_card_pool(200)
    merchants = make_merchant_pool(100)
    base_time = datetime.now(timezone.utc) - timedelta(days=30)

    transactions = []
    for _ in range(n_transactions):
        card = rng.choice(cards)
        merchant = rng.choice(merchants)
        is_fraud = rng.random() < fraud_rate
        transactions.append(
            generate_transaction(card, merchant, is_fraud, base_time)
        )

    return transactions


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic fraud data")
    parser.add_argument("--transactions", type=int, default=1000)
    parser.add_argument("--fraud-rate", type=float, default=0.08)
    parser.add_argument("--output", type=str, default="data/seed.sql")
    args = parser.parse_args()

    print(f"Generating {args.transactions} transactions ({args.fraud_rate*100:.0f}% fraud rate)...")
    txns = generate(args.transactions, args.fraud_rate)

    fraud_count = sum(1 for t in txns if t["is_fraud"])
    print(f"Generated: {len(txns)} total | {fraud_count} fraud | {len(txns)-fraud_count} legitimate")

    sql = transactions_to_sql(txns)
    with open(args.output, "w") as f:
        f.write(sql)

    print(f"Written to {args.output}")