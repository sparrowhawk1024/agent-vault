"""Trusted Metering Service for AgentVault.

Stores independently authenticated resource requirements needed by the autonomous system:
- API call units
- AI inference credits
- Storage capacity (GB-months)
"""

import time
from typing import Dict, Any, List, Optional


from backend.app.catalog.vendors import CATEGORIES


class RequirementStore:
    def __init__(self):
        self._requirements: Dict[str, Dict[str, Any]] = {}
        # Pre-seed with default requirement for demo readiness
        self.record_requirement(
            req_id="req-seed-01",
            category_requirements={
                CATEGORIES["API_CALLS"]["id"]: 15_000,
                CATEGORIES["AI_CREDITS"]["id"]: 8_000,
                CATEGORIES["STORAGE"]["id"]: 1_200,
            },
            description="Production autonomous agent pipeline monthly capacity baseline."
        )

    def record_requirement(
        self,
        req_id: str,
        category_requirements: Dict[str, int],
        description: str = "",
    ) -> Dict[str, Any]:
        """Record a validated requirement."""
        req = {
            "requirementId": req_id,
            "categoryRequirements": {k: int(v) for k, v in category_requirements.items()},
            "description": description,
            "timestamp": time.time(),
        }
        self._requirements[req_id] = req
        return req

    def get_requirement(self, req_id: str) -> Optional[Dict[str, Any]]:
        return self._requirements.get(req_id)

    def list_requirements(self) -> List[Dict[str, Any]]:
        return list(self._requirements.values())


global_requirement_store = RequirementStore()
