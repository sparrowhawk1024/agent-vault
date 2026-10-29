"""Store for Simulated AI Usage and Auto-Refill State.

Tracks:
- Simulated token allowance, consumed units, remaining units
- Chat message history with deterministic token counting
- Configurable top-up threshold (default 15%)
- Auto-Refill policy rules
- Processed settlement transaction hashes & nonces for idempotency
"""

import time
from typing import Dict, Any, List, Optional
from backend.app.x402.models import AutoRefillPolicy, RefillPackage


class SimulatedUsageStore:
    def __init__(self, initial_allowance: int = 5_000, threshold_pct: float = 15.0):
        self.initial_allowance = initial_allowance
        self.total_allowance = initial_allowance
        self.consumed_units = 0
        self.threshold_pct = threshold_pct
        self.chat_history: List[Dict[str, Any]] = []
        self.policy = AutoRefillPolicy(refillThresholdPct=threshold_pct)
        self.processed_nonces: set = set()
        self.settlement_history: List[Dict[str, Any]] = []

    def get_remaining_units(self) -> int:
        return max(0, self.total_allowance - self.consumed_units)

    def get_percentage_remaining(self) -> float:
        if self.total_allowance <= 0:
            return 0.0
        return round((self.get_remaining_units() / self.total_allowance) * 100.0, 1)

    def is_low_balance(self) -> bool:
        return self.get_percentage_remaining() <= self.threshold_pct

    def consume_units(self, units: int, reason: str = "Simulated interaction") -> Dict[str, Any]:
        """Deduct simulated token units deterministically."""
        self.consumed_units += units
        remaining = self.get_remaining_units()
        pct = self.get_percentage_remaining()
        low = self.is_low_balance()

        return {
            "consumed": units,
            "totalConsumed": self.consumed_units,
            "remainingUnits": remaining,
            "percentageRemaining": pct,
            "isLowBalance": low,
            "reason": reason,
        }

    def credit_units(self, units: int, tx_hash: str, package_id: str) -> Dict[str, Any]:
        """Credit simulated token units upon verified x402 payment settlement."""
        self.total_allowance += units
        record = {
            "refillId": f"refill-{int(time.time())}-{len(self.settlement_history)+1}",
            "unitsGranted": units,
            "newTotalAllowance": self.total_allowance,
            "remainingUnits": self.get_remaining_units(),
            "txHash": tx_hash,
            "packageId": package_id,
            "timestamp": time.time(),
        }
        self.settlement_history.append(record)
        return record

    def reset(self, initial_allowance: Optional[int] = None):
        """Reset simulated allowance and chat history for a clean demo run."""
        if initial_allowance is not None:
            self.initial_allowance = initial_allowance
        self.total_allowance = self.initial_allowance
        self.consumed_units = 0
        self.chat_history = []
        self.processed_nonces = set()
        self.settlement_history = []
        self.policy.spentToday = 0


# Global singleton instance for application runtime
global_refill_store = SimulatedUsageStore()

