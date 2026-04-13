"""
Unit tests for all five Argus investigation tools.

These tests use mocked database connections so they run without
a live PostgreSQL instance — making them fast and CI-friendly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api.schemas import (
    CardholderProfileResult,
    GeolocationResult,
    MerchantRiskResult,
    TransactionHistoryResult,
    VelocityResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_transaction() -> dict:
    return {
        "transaction_id": "txn_test001",
        "card_id": "card_test001",
        "merchant_id": "merch_test001",
        "amount": 299.99,
        "merchant_category": "Electronics",
        "merchant_country": "NG",
        "merchant_city": "Lagos",
        "cardholder_country": "US",
        "timestamp": datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
        "is_online": True,
        "is_fraud": False,
        "device_fingerprint": "abc123",
    }


# ---------------------------------------------------------------------------
# Transaction history tests
# ---------------------------------------------------------------------------


class TestTransactionHistory:
    @pytest.mark.asyncio
    async def test_no_history_returns_empty_result(self):
        """A card with no history should return zeroed stats and a risk signal."""
        with patch("agent.tools.transaction.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            mock_connect.return_value = mock_conn

            from agent.tools.transaction import get_transaction_history
            result = await get_transaction_history("card_new", "txn_001")

        assert isinstance(result, TransactionHistoryResult)
        assert result.total_transactions_30d == 0
        assert result.total_spend_30d == 0.0
        assert len(result.risk_signals) > 0
        assert any("No transaction history" in s for s in result.risk_signals)

    @pytest.mark.asyncio
    async def test_high_velocity_detected(self):
        """Three or more transactions in the last hour should trigger a risk signal."""
        now = datetime.now(timezone.utc)

        mock_rows = [
            {"amount": 50.0, "merchant_category": "Electronics",
             "merchant_country": "US", "timestamp": now},
            {"amount": 75.0, "merchant_category": "Electronics",
             "merchant_country": "US", "timestamp": now},
            {"amount": 60.0, "merchant_category": "Electronics",
             "merchant_country": "US", "timestamp": now},
        ]

        with patch("agent.tools.transaction.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            mock_connect.return_value = mock_conn

            from agent.tools.transaction import get_transaction_history
            result = await get_transaction_history("card_001", "txn_001")

        assert result.transactions_in_last_1h == 3
        assert any("velocity" in s.lower() for s in result.risk_signals)

    @pytest.mark.asyncio
    async def test_normal_history_no_signals(self):
        """Normal spending pattern should produce no risk signals."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        mock_rows = [
            {"amount": 45.0, "merchant_category": "Grocery",
             "merchant_country": "US", "timestamp": now - timedelta(days=i)}
            for i in range(1, 6)
        ]

        with patch("agent.tools.transaction.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            mock_connect.return_value = mock_conn

            from agent.tools.transaction import get_transaction_history
            result = await get_transaction_history("card_001", "txn_001")

        assert result.total_transactions_30d == 5
        assert result.risk_signals == []


# ---------------------------------------------------------------------------
# Merchant risk tests
# ---------------------------------------------------------------------------


class TestMerchantRisk:
    @pytest.mark.asyncio
    async def test_unknown_merchant_returns_heuristic(self):
        """Unknown merchant should fall back to category-based heuristics."""
        with patch("agent.tools.merchant.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = None
            mock_connect.return_value = mock_conn

            from agent.tools.merchant import get_merchant_risk
            result = await get_merchant_risk("merch_unknown", "Electronics", "US")

        assert isinstance(result, MerchantRiskResult)
        assert result.merchant_name == "Unknown"
        assert result.is_high_risk_category is True
        assert any("not found" in s.lower() for s in result.risk_signals)

    @pytest.mark.asyncio
    async def test_high_risk_merchant_signals(self):
        """A known high-risk merchant should produce appropriate signals."""
        mock_row = {
            "merchant_name": "ShadyElectronics",
            "category": "Electronics",
            "country": "NG",
            "fraud_rate": 0.25,
            "chargeback_rate": 0.10,
            "is_high_risk": True,
            "days_since_first_seen": 10,
        }

        with patch("agent.tools.merchant.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_row
            mock_connect.return_value = mock_conn

            from agent.tools.merchant import get_merchant_risk
            result = await get_merchant_risk("merch_001", "Electronics", "NG")

        assert result.fraud_rate_percent == 25.0
        assert len(result.risk_signals) >= 2
        assert any("high risk" in s.lower() for s in result.risk_signals)

    @pytest.mark.asyncio
    async def test_low_risk_merchant_no_signals(self):
        """A clean merchant should produce no risk signals."""
        mock_row = {
            "merchant_name": "SafeGrocery",
            "category": "Grocery",
            "country": "US",
            "fraud_rate": 0.001,
            "chargeback_rate": 0.002,
            "is_high_risk": False,
            "days_since_first_seen": 500,
        }

        with patch("agent.tools.merchant.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_row
            mock_connect.return_value = mock_conn

            from agent.tools.merchant import get_merchant_risk
            result = await get_merchant_risk("merch_002", "Grocery", "US")

        assert result.risk_signals == []


# ---------------------------------------------------------------------------
# Velocity tests
# ---------------------------------------------------------------------------


class TestVelocity:
    @pytest.mark.asyncio
    async def test_velocity_exceeded_signals(self):
        """Exceeding velocity thresholds should set velocity_exceeded=True."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        mock_rows = [
            {"amount": 200.0, "merchant_id": f"m{i}",
             "merchant_country": "US", "timestamp": now - timedelta(minutes=i*5)}
            for i in range(5)
        ]

        with patch("agent.tools.velocity.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            mock_connect.return_value = mock_conn

            from agent.tools.velocity import check_velocity
            result = await check_velocity("card_001", "txn_001")

        assert isinstance(result, VelocityResult)
        assert result.velocity_exceeded is True

    @pytest.mark.asyncio
    async def test_no_recent_transactions_clean(self):
        """No recent transactions means no velocity risk."""
        with patch("agent.tools.velocity.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            mock_connect.return_value = mock_conn

            from agent.tools.velocity import check_velocity
            result = await check_velocity("card_001", "txn_001")

        assert result.velocity_exceeded is False
        assert result.transactions_last_1h == 0
        assert result.risk_signals == []


# ---------------------------------------------------------------------------
# Geolocation tests
# ---------------------------------------------------------------------------


class TestGeolocation:
    @pytest.mark.asyncio
    async def test_impossible_travel_detected(self):
        """US → NG in 30 minutes should be flagged as impossible travel."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        last_txn_time = now - timedelta(minutes=30)

        mock_row = {"merchant_country": "US", "timestamp": last_txn_time}

        with patch("agent.tools.geolocation.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_row
            mock_connect.return_value = mock_conn

            from agent.tools.geolocation import check_geolocation
            result = await check_geolocation(
                card_id="card_001",
                current_transaction_id="txn_001",
                transaction_country="NG",
                cardholder_country="US",
                transaction_timestamp=now,
            )

        assert isinstance(result, GeolocationResult)
        assert result.is_impossible_travel is True
        assert any("impossible travel" in s.lower() for s in result.risk_signals)

    @pytest.mark.asyncio
    async def test_same_country_no_travel_signal(self):
        """Transaction in same country as last transaction should not flag travel."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        last_txn_time = now - timedelta(hours=2)

        mock_row = {"merchant_country": "US", "timestamp": last_txn_time}

        with patch("agent.tools.geolocation.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_row
            mock_connect.return_value = mock_conn

            from agent.tools.geolocation import check_geolocation
            result = await check_geolocation(
                card_id="card_001",
                current_transaction_id="txn_001",
                transaction_country="US",
                cardholder_country="US",
                transaction_timestamp=now,
            )

        assert result.is_impossible_travel is False
        assert result.is_cross_border is False


# ---------------------------------------------------------------------------
# Cardholder profile tests
# ---------------------------------------------------------------------------


class TestCardholderProfile:
    @pytest.mark.asyncio
    async def test_amount_anomaly_detected(self):
        """Amount 3x above average should be flagged."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        mock_rows = [
            {"amount": 50.0, "merchant_category": "Grocery",
             "merchant_country": "US", "is_fraud": False,
             "created_at": now - timedelta(days=i)}
            for i in range(1, 11)
        ]
        mock_fraud_rows = [{"fraud_count": 0}]
        mock_account_row = {"first_seen": now - timedelta(days=365)}

        with patch("agent.tools.profile.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch.side_effect = [mock_rows, mock_fraud_rows]
            mock_conn.fetchrow.return_value = mock_account_row
            mock_connect.return_value = mock_conn

            from agent.tools.profile import get_cardholder_profile
            result = await get_cardholder_profile(
                card_id="card_001",
                current_transaction_id="txn_001",
                current_amount=500.0,  # 10x the average of $50
                current_category="Grocery",
                current_country="US",
            )

        assert isinstance(result, CardholderProfileResult)
        assert result.current_transaction_fits_profile is False
        assert any("anomaly" in s.lower() for s in result.risk_signals)

    @pytest.mark.asyncio
    async def test_normal_transaction_fits_profile(self):
        """Transaction matching profile should be marked as fitting."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        mock_rows = [
            {"amount": 50.0, "merchant_category": "Grocery",
             "merchant_country": "US", "is_fraud": False,
             "created_at": now - timedelta(days=i)}
            for i in range(1, 11)
        ]
        mock_fraud_rows = [{"fraud_count": 0}]
        mock_account_row = {"first_seen": now - timedelta(days=365)}

        with patch("agent.tools.profile.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch.side_effect = [mock_rows, mock_fraud_rows]
            mock_conn.fetchrow.return_value = mock_account_row
            mock_connect.return_value = mock_conn

            from agent.tools.profile import get_cardholder_profile
            result = await get_cardholder_profile(
                card_id="card_001",
                current_transaction_id="txn_001",
                current_amount=55.0,
                current_category="Grocery",
                current_country="US",
            )

        assert result.current_transaction_fits_profile is True
        assert result.has_previous_fraud is False


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_transaction_input_validates_country_code(self):
        """Invalid country codes should raise ValidationError."""
        from pydantic import ValidationError
        from api.schemas import TransactionInput

        with pytest.raises(ValidationError):
            TransactionInput(
                transaction_id="txn_001",
                card_id="card_001",
                merchant_id="merch_001",
                amount=100.0,
                merchant_category="Grocery",
                merchant_country="USA",  # invalid — must be 2 chars
                merchant_city="NYC",
                cardholder_country="US",
                timestamp=datetime.now(timezone.utc),
                is_online=False,
            )

    def test_transaction_input_rejects_negative_amount(self):
        """Negative amounts should raise ValidationError."""
        from pydantic import ValidationError
        from api.schemas import TransactionInput

        with pytest.raises(ValidationError):
            TransactionInput(
                transaction_id="txn_001",
                card_id="card_001",
                merchant_id="merch_001",
                amount=-50.0,
                merchant_category="Grocery",
                merchant_country="US",
                merchant_city="NYC",
                cardholder_country="US",
                timestamp=datetime.now(timezone.utc),
                is_online=False,
            )