"""
Node registry for the Argus investigation graph.

Re-exports all node functions so they can be imported and tested
independently without instantiating the full graph.
"""

from __future__ import annotations

from agent.graph import (
    node_geolocation_check,
    node_merchant_risk,
    node_profile_check,
    node_synthesise,
    node_transaction_history,
    node_velocity_check,
)

__all__ = [
    "node_transaction_history",
    "node_merchant_risk",
    "node_velocity_check",
    "node_geolocation_check",
    "node_profile_check",
    "node_synthesise",
]