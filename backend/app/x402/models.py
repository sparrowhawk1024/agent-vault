"""x402 Protocol V2 Data Models and Schemas.

Implements the official x402 V2 HTTP Payment Required specification:
- HTTP 402 PaymentRequired challenge object
- PAYMENT-REQUIRED header payload
- PAYMENT-SIGNATURE request payload
- PAYMENT-RESPONSE settlement payload
"""

import base64
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ResourceInfo(BaseModel):
    url: str
    description: str
    mimeType: str = "application/json"


class AcceptScheme(BaseModel):
    scheme: str = "exact"  # "exact" for fixed-price bundle
    network: str = "eip155:84532"  # CAIP-2 identifier (e.g. Base Sepolia or eip155:31337 local)
    amount: str  # in atomic token units (e.g. micro-USDC: "3000000" = 3.0 USDC)
    asset: str  # Contract address of payment token (e.g. USDC)
    payTo: str  # Recipient / vendor payee address
    maxTimeoutSeconds: int = 120
    extra: Dict[str, Any] = Field(default_factory=dict)


class PaymentRequiredResponse(BaseModel):
    x402Version: int = 2
    error: str = "PAYMENT-SIGNATURE header is required"
    resource: ResourceInfo
    accepts: List[AcceptScheme]

    def to_header_b64(self) -> str:
        """Encode to Base64 JSON for PAYMENT-REQUIRED header."""
        raw = self.model_dump_json()
        return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


class SignaturePayload(BaseModel):
    payer: str
    payTo: str
    asset: str
    amount: str
    nonce: int
    validUntil: int
    signature: str


class PaymentPayload(BaseModel):
    x402Version: int = 2
    scheme: str = "exact"
    network: str
    payload: SignaturePayload

    @classmethod
    def from_header_b64(cls, header_value: str) -> "PaymentPayload":
        """Decode from Base64 JSON from PAYMENT-SIGNATURE header."""
        decoded = base64.b64decode(header_value.strip()).decode("utf-8")
        data = json.loads(decoded)
        return cls.model_validate(data)


class SettlementResponse(BaseModel):
    x402Version: int = 2
    status: str  # "settled" | "failed"
    scheme: str = "exact"
    network: str
    txHash: Optional[str] = None
    amount: str
    asset: str
    recipient: str
    settledAt: int
    error: Optional[str] = None

    def to_header_b64(self) -> str:
        """Encode to Base64 JSON for PAYMENT-RESPONSE header."""
        raw = self.model_dump_json()
        return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


class AutoRefillPolicy(BaseModel):
    enabled: bool = False
    maxSpendPerRefill: int = 5_000_000   # 5 USDC
    maxDailySpend: int = 15_000_000      # 15 USDC
    approvedVendor: str = "tokenforge"   # Only allowlisted vendor
    refillThresholdPct: float = 15.0     # Trigger top-up at 15%
    spentToday: int = 0
    lastRefillTimestamp: Optional[int] = None
    revoked: bool = False


class RefillPackage(BaseModel):
    packageId: str
    name: str
    vendorId: str
    vendorName: str
    units: int                 # Simulated resource/token units
    priceMicroUsdc: int        # Exact atomic price (e.g. 3_000_000 = $3.00)
    priceUsdc: float
    unitPriceMicros: float     # Price per unit (for value comparison)
    isRecommended: bool = False
    isAllowedVendor: bool = True
    description: str
    serviceType: str = "AI_CREDITS"        # "AI_CREDITS" | "API_CALLS" | "STORAGE" | "MULTI_SERVICE"
    serviceName: str = "AI Inference Credits"
    unitLabel: str = "tokens"              # "tokens" | "calls" | "GB-mo" | "units"
    isCapFlexible: bool = False            # True if dynamically sized to user's per-top-up cap


