"""
Pydantic schemas for the Argus Fraud Investigation Agent API.

These models define the contract between the API, the agent, and the database.
Every field is typed. Every field has a description. No exceptions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Recommendation(str, Enum):
    """Final recommendation produced by the agent."""

    BLOCK = "BLOCK"
    ALLOW = "ALLOW"
    ESCALATE = "ESCALATE"


class RiskLevel(str, Enum):
    """Categorical risk level derived from confidence score."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class InvestigationStatus(str, Enum):
    """Lifecycle status of an investigation run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Transaction input
# ---------------------------------------------------------------------------


class TransactionInput(BaseModel):
    """
    Incoming transaction flagged for investigation.
    This is the payload the API receives and passes to the agent.
    """

    transaction_id: str = Field(
        ..., description="Unique identifier for the transaction", examples=["txn_8f3a2b1c"]
    )
    card_id: str = Field(
        ..., description="Hashed card identifier", examples=["card_9d4e5f6a"]
    )
    merchant_id: str = Field(
        ..., description="Merchant identifier", examples=["merch_2a3b4c"]
    )
    amount: float = Field(
        ..., gt=0, description="Transaction amount in USD", examples=[249.99]
    )
    merchant_category: str = Field(
        ..., description="Merchant category code description", examples=["Electronics"]
    )
    merchant_country: str = Field(
        ..., description="ISO 3166-1 alpha-2 country code", examples=["US"]
    )
    merchant_city: str = Field(
        ..., description="City where transaction occurred", examples=["San Francisco"]
    )
    cardholder_country: str = Field(
        ..., description="Country where card was issued", examples=["US"]
    )
    timestamp: datetime = Field(
        ..., description="UTC timestamp of the transaction"
    )
    is_online: bool = Field(
        ..., description="True if card-not-present / online transaction"
    )
    device_fingerprint: str | None = Field(
        default=None, description="Device fingerprint hash for online transactions"
    )

    @field_validator("merchant_country", "cardholder_country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        if len(v) != 2 or not v.isalpha():
            raise ValueError("Country code must be ISO 3166-1 alpha-2 (e.g. 'US')")
        return v.upper()

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v > 1_000_000:
            raise ValueError("Amount exceeds maximum allowed value")
        return round(v, 2)


# ---------------------------------------------------------------------------
# Tool outputs — one per agent tool
# ---------------------------------------------------------------------------


class TransactionHistoryResult(BaseModel):
    """Output of the transaction history tool."""

    card_id: str
    total_transactions_30d: int
    total_spend_30d: float
    average_transaction_amount: float
    max_transaction_amount: float
    transactions_in_last_1h: int
    transactions_in_last_24h: int
    most_common_merchant_category: str
    most_common_country: str
    risk_signals: list[str] = Field(default_factory=list)


class MerchantRiskResult(BaseModel):
    """Output of the merchant risk tool."""

    merchant_id: str
    merchant_name: str
    category: str
    fraud_rate_percent: float
    chargeback_rate_percent: float
    is_high_risk_category: bool
    country: str
    days_since_first_seen: int
    risk_signals: list[str] = Field(default_factory=list)


class VelocityResult(BaseModel):
    """Output of the velocity check tool."""

    card_id: str
    transactions_last_1h: int
    transactions_last_24h: int
    unique_merchants_last_24h: int
    unique_countries_last_24h: int
    amount_last_1h: float
    amount_last_24h: float
    velocity_exceeded: bool
    risk_signals: list[str] = Field(default_factory=list)


class GeolocationResult(BaseModel):
    """Output of the geolocation plausibility tool."""

    card_id: str
    transaction_country: str
    cardholder_home_country: str
    last_known_country: str
    hours_since_last_transaction: float
    is_cross_border: bool
    is_impossible_travel: bool
    distance_km: float | None = None
    risk_signals: list[str] = Field(default_factory=list)


class CardholderProfileResult(BaseModel):
    """Output of the cardholder profile tool."""

    card_id: str
    account_age_days: int
    typical_spend_range: tuple[float, float]
    typical_categories: list[str]
    typical_countries: list[str]
    has_previous_fraud: bool
    previous_fraud_count: int
    current_transaction_fits_profile: bool
    risk_signals: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Investigation report
# ---------------------------------------------------------------------------


class InvestigationReport(BaseModel):
    """
    Final structured output of a completed agent investigation.
    This is what gets stored in PostgreSQL and returned via the API.
    """

    investigation_id: UUID = Field(default_factory=uuid4)
    transaction_id: str
    recommendation: Recommendation
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Agent confidence in recommendation (0.0 = uncertain, 1.0 = certain)",
    )
    risk_level: RiskLevel
    reasoning: str = Field(
        ..., description="Human-readable explanation of the agent's decision"
    )
    risk_signals: list[str] = Field(
        default_factory=list,
        description="All risk signals detected across all tools",
    )
    decision_trace: list[str] = Field(
    default_factory=list,
    description="Step-by-step reasoning trace of agent decisions"
)
    tool_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw outputs from each tool, keyed by tool name",
    )
    investigated_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = Field(
        ..., description="Total agent wall-clock time in milliseconds"
    )
    langsmith_run_url: str | None = Field(
        default=None, description="LangSmith trace URL for this investigation"
    )


# ---------------------------------------------------------------------------
# API request / response wrappers
# ---------------------------------------------------------------------------


class InvestigateRequest(BaseModel):
    """POST /investigate request body."""

    transaction: TransactionInput


class InvestigateResponse(BaseModel):
    """POST /investigate response body."""

    status: InvestigationStatus
    report: InvestigationReport | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """GET /health response body."""

    status: str = "ok"
    version: str = "0.1.0"
    model: str = "claude-sonnet-4-20250514"