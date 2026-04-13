"""
Geolocation plausibility tool.

Detects impossible travel — if a card was used in New York 1 hour ago
and is now being used in London, that is physically impossible.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

import asyncpg

from api.schemas import GeolocationResult

# Approximate country centroids (lat, lon) for distance calculation
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "US": (37.09, -95.71), "GB": (55.37, -3.43), "CA": (56.13, -106.34),
    "AU": (-25.27, 133.77), "DE": (51.16, 10.45), "JP": (36.20, 138.25),
    "FR": (46.22, 2.21),   "NG": (9.08, 8.67),   "RO": (45.94, 24.96),
    "UA": (48.37, 31.16),  "VN": (14.05, 108.27), "PK": (30.37, 69.34),
    "ID": (-0.78, 113.92), "CN": (35.86, 104.19), "IN": (20.59, 78.96),
    "BR": (-14.23, -51.92), "MX": (23.63, -102.55), "ZA": (-30.55, 22.93),
}

# Average commercial flight speed km/h — used for impossibility check
AVG_TRAVEL_SPEED_KMH = 900.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometres."""
    r = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * r * asin(sqrt(a))


async def check_geolocation(
    card_id: str,
    current_transaction_id: str,
    transaction_country: str,
    cardholder_country: str,
    transaction_timestamp: datetime,
) -> GeolocationResult:
    """
    Check if the transaction location is geographically plausible.

    Impossible travel is detected by comparing the distance between the
    current transaction country and the last known transaction country
    against the time elapsed and maximum possible travel speed.
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
        # Find the most recent prior transaction for this card
        row = await conn.fetchrow(
            """
            SELECT merchant_country, timestamp
            FROM transactions
            WHERE card_id = $1
              AND transaction_id != $2
              AND timestamp < $3
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            card_id,
            current_transaction_id,
            transaction_timestamp,
        )

        is_cross_border = transaction_country != cardholder_country
        if is_cross_border:
            risk_signals.append(
                f"Cross-border transaction: card from {cardholder_country}, "
                f"used in {transaction_country}"
            )

        if row is None:
            return GeolocationResult(
                card_id=card_id,
                transaction_country=transaction_country,
                cardholder_home_country=cardholder_country,
                last_known_country=cardholder_country,
                hours_since_last_transaction=999.0,
                is_cross_border=is_cross_border,
                is_impossible_travel=False,
                distance_km=None,
                risk_signals=risk_signals,
            )

        last_country = row["merchant_country"]
        last_timestamp = row["timestamp"]

        if last_timestamp.tzinfo is None:
            last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)

        hours_elapsed = (
            transaction_timestamp - last_timestamp
        ).total_seconds() / 3600

        # Calculate distance if we have coordinates for both countries
        distance_km: float | None = None
        is_impossible_travel = False

        coords_current = COUNTRY_COORDS.get(transaction_country)
        coords_last = COUNTRY_COORDS.get(last_country)

        if coords_current and coords_last and last_country != transaction_country:
            distance_km = haversine_km(*coords_last, *coords_current)
            min_hours_required = distance_km / AVG_TRAVEL_SPEED_KMH

            if hours_elapsed < min_hours_required and hours_elapsed > 0:
                is_impossible_travel = True
                risk_signals.append(
                    f"Impossible travel detected: {distance_km:.0f}km between "
                    f"{last_country} and {transaction_country} "
                    f"in {hours_elapsed:.1f}h (minimum {min_hours_required:.1f}h required)"
                )

        if hours_elapsed < 0.5 and last_country != transaction_country:
            risk_signals.append(
                f"Rapid country change: {last_country} → {transaction_country} "
                f"in {hours_elapsed * 60:.0f} minutes"
            )

        return GeolocationResult(
            card_id=card_id,
            transaction_country=transaction_country,
            cardholder_home_country=cardholder_country,
            last_known_country=last_country,
            hours_since_last_transaction=round(hours_elapsed, 2),
            is_cross_border=is_cross_border,
            is_impossible_travel=is_impossible_travel,
            distance_km=round(distance_km, 1) if distance_km else None,
            risk_signals=risk_signals,
        )

    finally:
        await conn.close()