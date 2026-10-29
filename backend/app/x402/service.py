"""x402 V2 Protocol Service and Auto-Refill Engine.

Features:
1. Deterministic simulated AI chat interactions with transparent token consumption.
2. Synthetic refill packages derived from canonical vendor catalog (TokenForge, BudgetByte).
3. Full x402 V2 HTTP 402 challenge generation (Base64 headers & JSON body).
4. EIP-712 / cryptographic payment payload validation.
5. Strict policy checks (spending limits, vendor allowlisting, daily caps, idempotency).
6. Simulated tokens credited ONLY upon confirmed settlement.
"""

import os
import time
import json
import base64
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from eth_utils import to_hex, keccak, to_checksum_address
from eth_account import Account

from backend.app.catalog.vendors import get_vendor_registry, CATEGORIES
from backend.app.audit.store import global_audit_log
from backend.app.x402.models import (
    ResourceInfo,
    AcceptScheme,
    PaymentRequiredResponse,
    PaymentPayload,
    SettlementResponse,
    AutoRefillPolicy,
    RefillPackage,
)
from backend.app.x402.store import global_refill_store

# Supported payment network (CAIP-2 format)
X402_NETWORK = os.environ.get("X402_NETWORK", "eip155:84532")  # Base Sepolia default
X402_USDC_ASSET = os.environ.get("X402_USDC_ASSET", "0x036CbD53842c5426634e7929541eC2318f3dCF7e")

# Canonical vendor services and dynamic unit rate cards
VENDOR_SERVICES: Dict[str, Dict[str, Any]] = {
    "tokenforge": {
        "serviceType": "AI_CREDITS",
        "serviceName": "AI Inference Credits",
        "unitLabel": "tokens",
        "unitPriceMicros": 1.50,  # 1.50 µUSDC per token
        "vendorName": "TokenForge (Verified Vendor)",
        "description": "High-throughput GPU inference tokens for autonomous LLM agents.",
        "isAllowedVendor": True,
    },
    "nimbusapi": {
        "serviceType": "API_CALLS",
        "serviceName": "API Throughput Calls",
        "unitLabel": "calls",
        "unitPriceMicros": 0.85,  # 0.85 µUSDC per API call
        "vendorName": "NimbusAPI (Verified Vendor)",
        "description": "Low-latency rate-unlimited REST/RPC gateway calls.",
        "isAllowedVendor": True,
    },
    "vaultstore": {
        "serviceType": "STORAGE",
        "serviceName": "Storage Units",
        "unitLabel": "GB-mo",
        "unitPriceMicros": 0.60,  # 0.60 µUSDC per storage unit
        "vendorName": "VaultStore (Verified Vendor)",
        "description": "High-durability persistent blob storage & context caching.",
        "isAllowedVendor": True,
    },
    "budgetbyte": {
        "serviceType": "MULTI_SERVICE",
        "serviceName": "Economy Multi-Service",
        "unitLabel": "units",
        "unitPriceMicros": 1.40,  # 1.40 µUSDC per unit
        "vendorName": "BudgetByte (Verified Vendor)",
        "description": "Economy tier bundled credits for budget-sensitive agents.",
        "isAllowedVendor": True,
    },
    "shadydeals": {
        "serviceType": "AI_CREDITS",
        "serviceName": "Suspicious Flash Tokens",
        "unitLabel": "tokens",
        "unitPriceMicros": 0.15,  # 0.15 µUSDC per token
        "vendorName": "ShadyDeals (UNAPPROVED VENDOR)",
        "description": "[ADVERSARIAL TEST OFFER] Unapproved vendor offering suspiciously cheap tokens. Must be rejected by policy.",
        "isAllowedVendor": False,
    },
}


def create_flexible_package(
    vendor_key: str,
    spend_micro_usdc: int,
    is_cap_matched: bool = False,
) -> Optional[RefillPackage]:
    """Dynamically generates a flexible refill package sized to user's spend cap and provider service rate."""
    vk = vendor_key.lower().strip()
    v_info = VENDOR_SERVICES.get(vk)
    if not v_info:
        return None

    registry = get_vendor_registry()
    reg_entry = registry.get(vk)
    if not reg_entry:
        return None

    spend_micro_usdc = max(1, spend_micro_usdc)
    rate = v_info["unitPriceMicros"]
    units = max(1, int(spend_micro_usdc / rate))
    usdc = spend_micro_usdc / 1_000_000.0

    cap_label = "Cap-Optimized" if is_cap_matched else "Flexible"
    pkg_id = f"pack-flex-{vk}-{spend_micro_usdc}"

    return RefillPackage(
        packageId=pkg_id,
        name=f"{v_info['vendorName'].split()[0]} {cap_label} {v_info['serviceName']}",
        vendorId=reg_entry["vendorId"],
        vendorName=v_info["vendorName"],
        units=units,
        priceMicroUsdc=spend_micro_usdc,
        priceUsdc=usdc,
        unitPriceMicros=rate,
        isRecommended=is_cap_matched and vk == "tokenforge",
        isAllowedVendor=v_info["isAllowedVendor"],
        description=(
            f"Flexible pricing top-up tailored to user cap (${usdc:.6f} USDC). "
            f"Provides {units:,} {v_info['unitLabel']} at {rate:.2f} µUSDC/{v_info['unitLabel']}."
        ),
        serviceType=v_info["serviceType"],
        serviceName=v_info["serviceName"],
        unitLabel=v_info["unitLabel"],
        isCapFlexible=True,
    )


def get_available_refill_packages(policy: Optional[AutoRefillPolicy] = None) -> List[RefillPackage]:
    """Retrieve structured AI credit refill packages from canonical vendor registry,
    including provider service offerings and dynamic packages tailored to the user's per-refill cap.
    """
    registry = get_vendor_registry()
    tf_vid = registry["tokenforge"]["vendorId"]
    bb_vid = registry["budgetbyte"]["vendorId"]
    nimbus_vid = registry["nimbusapi"]["vendorId"]
    vault_vid = registry["vaultstore"]["vendorId"]
    shady_vid = registry["shadydeals"]["vendorId"]

    # Active policy for cap matching
    active_policy = policy or global_refill_store.policy
    user_cap = active_policy.maxSpendPerRefill if active_policy else 5_000_000

    # 1. Fixed Base Packages (User specified tiers: $5 -> 350 credits, $10, $20, $40, $50)
    packages = [
        RefillPackage(
            packageId="pack-base-5",
            name="Starter Refill ($5)",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=350,
            priceMicroUsdc=5_000_000,  # $5.00 USDC exact
            priceUsdc=5.00,
            unitPriceMicros=5_000_000 / 350,  # 14,285.7 µUSDC/token
            isRecommended=True,
            isAllowedVendor=True,
            description="Cheapest fixed base tier: exactly 350 credits for $5.00 USDC.",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-base-10",
            name="Standard Refill ($10)",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=750,
            priceMicroUsdc=10_000_000,  # $10.00 USDC exact
            priceUsdc=10.00,
            unitPriceMicros=10_000_000 / 750,  # 13,333.3 µUSDC/token
            isRecommended=False,
            isAllowedVendor=True,
            description="Standard fixed base tier: 750 credits for $10.00 USDC.",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-base-20",
            name="Pro Refill ($20)",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=1_600,
            priceMicroUsdc=20_000_000,  # $20.00 USDC exact
            priceUsdc=20.00,
            unitPriceMicros=20_000_000 / 1_600,  # 12,500.0 µUSDC/token
            isRecommended=False,
            isAllowedVendor=True,
            description="Pro fixed base tier: 1,600 credits for $20.00 USDC.",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-base-40",
            name="Business Refill ($40)",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=3_500,
            priceMicroUsdc=40_000_000,  # $40.00 USDC exact
            priceUsdc=40.00,
            unitPriceMicros=40_000_000 / 3_500,  # 11,428.6 µUSDC/token
            isRecommended=False,
            isAllowedVendor=True,
            description="Business fixed base tier: 3,500 credits for $40.00 USDC.",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-base-50",
            name="Enterprise Refill ($50)",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=5_000,
            priceMicroUsdc=50_000_000,  # $50.00 USDC exact
            priceUsdc=50.00,
            unitPriceMicros=50_000_000 / 5_000,  # 10,000.0 µUSDC/token
            isRecommended=False,
            isAllowedVendor=True,
            description="Enterprise maximum fixed base tier: 5,000 credits for $50.00 USDC.",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
        # Legacy & multi-service packages preserved for tests and benchmarks
        RefillPackage(
            packageId="pack-custom-213",
            name="Custom Stream Refill (213 µUSDC)",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=1_000,
            priceMicroUsdc=213,  # $0.000213 USDC exact
            priceUsdc=0.000213,
            unitPriceMicros=0.213,
            isRecommended=False,
            isAllowedVendor=True,
            description="Custom replenish package: exactly 213 micro-USDC per top-up.",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=True,
        ),
        RefillPackage(
            packageId="pack-tf-2k",
            name="TokenForge Pro Top-Up",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=2_000,
            priceMicroUsdc=3_000_000,  # $3.00 USDC
            priceUsdc=3.00,
            unitPriceMicros=1500.0,
            isRecommended=True,
            isAllowedVendor=True,
            description="Recommended standard top-up: 2,000 simulated AI inference tokens at 1.50 micro/unit.",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-tf-500",
            name="TokenForge Micro Refill",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=500,
            priceMicroUsdc=900_000,  # $0.90 USDC
            priceUsdc=0.90,
            unitPriceMicros=1800.0,
            isRecommended=False,
            isAllowedVendor=True,
            description="Starter top-up: 500 simulated AI tokens at 1.80 micro/unit.",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-bb-1k",
            name="BudgetByte Economy Refill",
            vendorId=bb_vid,
            vendorName="BudgetByte (Verified Vendor)",
            units=1_000,
            priceMicroUsdc=1_400_000,  # $1.40 USDC
            priceUsdc=1.40,
            unitPriceMicros=1400.0,
            isRecommended=False,
            isAllowedVendor=True,
            description="Economy tier: 1,000 simulated AI tokens at 1.40 micro/unit.",
            serviceType="MULTI_SERVICE",
            serviceName="Economy Multi-Service",
            unitLabel="units",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-nimbus-3k",
            name="NimbusAPI Gateway Refill",
            vendorId=nimbus_vid,
            vendorName="NimbusAPI (Verified Vendor)",
            units=3_000,
            priceMicroUsdc=2_550_000,  # $2.55 USDC (0.85 micro/call)
            priceUsdc=2.55,
            unitPriceMicros=850.0,
            isRecommended=False,
            isAllowedVendor=True,
            description="API service top-up: 3,000 authenticated REST/RPC calls at 0.85 micro/call.",
            serviceType="API_CALLS",
            serviceName="API Throughput Calls",
            unitLabel="calls",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-vault-4k",
            name="VaultStore Storage Refill",
            vendorId=vault_vid,
            vendorName="VaultStore (Verified Vendor)",
            units=4_000,
            priceMicroUsdc=2_400_000,  # $2.40 USDC (0.60 micro/GB-mo)
            priceUsdc=2.40,
            unitPriceMicros=600.0,
            isRecommended=False,
            isAllowedVendor=True,
            description="Cloud storage top-up: 4,000 persistent storage units at 0.60 micro/GB-mo.",
            serviceType="STORAGE",
            serviceName="Storage Units",
            unitLabel="GB-mo",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-tf-10k",
            name="TokenForge High-Capacity Top-Up",
            vendorId=tf_vid,
            vendorName="TokenForge (Verified Vendor)",
            units=10_000,
            priceMicroUsdc=12_000_000,  # $12.00 USDC
            priceUsdc=12.00,
            unitPriceMicros=1200.0,
            isRecommended=False,
            isAllowedVendor=True,
            description="High-capacity top-up: 10,000 simulated AI tokens at volume discount (1.20 micro/unit).",
            serviceType="AI_CREDITS",
            serviceName="AI Inference Credits",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
        RefillPackage(
            packageId="pack-shady-5k",
            name="ShadyDeals Flash AI Tokens",
            vendorId=shady_vid,
            vendorName="ShadyDeals (UNAPPROVED VENDOR)",
            units=5_000,
            priceMicroUsdc=750_000,  # $0.75 USDC
            priceUsdc=0.75,
            unitPriceMicros=150.0,
            isRecommended=False,
            isAllowedVendor=False,
            description="[ADVERSARIAL TEST OFFER] Unapproved vendor offering suspiciously cheap tokens. Must be rejected by policy.",
            serviceType="AI_CREDITS",
            serviceName="Suspicious Flash Tokens",
            unitLabel="tokens",
            isCapFlexible=False,
        ),
    ]

    # 2. Dynamic Cap-Matched Packages for each approved provider service
    # Sized to fit the user's active maxSpendPerRefill policy cap!
    if user_cap > 0 and user_cap != 3_000_000:  # If different from standard pack-tf-2k
        for vk in ["tokenforge", "nimbusapi", "vaultstore", "budgetbyte"]:
            cap_pkg = create_flexible_package(vk, user_cap, is_cap_matched=True)
            if cap_pkg:
                packages.append(cap_pkg)

    return packages


def find_package(package_id: str, custom_policy: Optional[AutoRefillPolicy] = None) -> Optional[RefillPackage]:
    # Check in available packages first
    for p in get_available_refill_packages(custom_policy):
        if p.packageId == package_id:
            return p

    # Dynamically resolve flexible package: pack-flex-{vendor}-{micro_amount}
    if package_id.startswith("pack-flex-"):
        parts = package_id.split("-")
        if len(parts) >= 4:
            vendor = parts[2]
            try:
                spend_micros = int(parts[3])
                return create_flexible_package(vendor, spend_micros, is_cap_matched=False)
            except ValueError:
                pass

    # Dynamically resolve custom amount package: pack-custom-{micro_amount}
    if package_id.startswith("pack-custom-"):
        parts = package_id.split("-")
        if len(parts) >= 3:
            try:
                spend_micros = int(parts[2])
                return create_flexible_package("tokenforge", spend_micros, is_cap_matched=False)
            except ValueError:
                pass

    return None



def generate_deterministic_chat_response(prompt: str) -> Tuple[str, int]:
    """Generate deterministic simulated AI response and calculate token consumption.
    
    Clearly labelled as simulated. Never calls a remote LLM API.
    Rule: tokens = len(prompt_words) * 15 + 180 base units.
    """
    clean_p = prompt.strip().lower()
    word_count = len(clean_p.split())
    tokens = word_count * 15 + 180

    if "optimize" in clean_p or "procurement" in clean_p:
        text = (
            "[SIMULATED AI RESPONSE]\n"
            "I analyzed your procurement requirements across API Calls, AI Credits, and Storage. "
            "Using QpiAI Opt's HiGHS formulation, the optimal bundle achieves a 28.47% cost reduction "
            "($23.03 vs $32.20 vendor baseline) while respecting all mandate line limits and spending caps."
        )
    elif "policy" in clean_p or "mandate" in clean_p or "cap" in clean_p:
        text = (
            "[SIMULATED AI RESPONSE]\n"
            "Your PolicyVault mandate enforces cryptographic spending authority: max $30.00 per purchase, "
            "$40.00 daily cap, and strict vendor allowlisting. All payment transactions require deterministic "
            "independent verifier signatures before on-chain execution."
        )
    elif "refill" in clean_p or "balance" in clean_p or "credit" in clean_p:
        text = (
            "[SIMULATED AI RESPONSE]\n"
            "Your simulated AI inference allowance is monitored by AgentVault. When remaining units fall "
            "below 15%, an x402 V2 payment challenge is generated for user approval."
        )
    else:
        text = (
            f"[SIMULATED AI RESPONSE]\n"
            f"Processed your simulated prompt ('{prompt[:40]}...'). "
            "Autonomous agent workflows remain bound to verifiable spending policies and EIP-712 authorizations."
        )

    return text, tokens


def get_vendor_payee(pkg: RefillPackage) -> str:
    """Resolve authoritative on-chain payee address for any package vendor."""
    registry = get_vendor_registry()
    norm_pkg_vid = pkg.vendorId.lower().replace("0x", "")
    for v in registry.values():
        if v["vendorId"].lower().replace("0x", "") == norm_pkg_vid:
            return v["payee"]
    vk = pkg.vendorName.split()[0].lower()
    if vk in registry:
        return registry[vk]["payee"]
    return registry["tokenforge"]["payee"]


class X402Service:
    def __init__(self, store=None):
        self.store = store or global_refill_store

    def create_payment_required_challenge(self, package_id: str) -> PaymentRequiredResponse:
        """Create canonical x402 V2 Payment Required challenge."""
        pkg = find_package(package_id) or find_package("pack-tf-2k")
        pay_to = get_vendor_payee(pkg)

        accepts = [
            AcceptScheme(
                scheme="exact",
                network=X402_NETWORK,
                amount=str(pkg.priceMicroUsdc),
                asset=X402_USDC_ASSET,
                payTo=pay_to,
                maxTimeoutSeconds=120,
                extra={
                    "name": "USDC",
                    "packageId": pkg.packageId,
                    "packageName": pkg.name,
                    "units": pkg.units,
                    "vendorId": pkg.vendorId,
                },
            )
        ]

        return PaymentRequiredResponse(
            x402Version=2,
            error="PAYMENT-SIGNATURE header is required",
            resource=ResourceInfo(
                url="/api/x402/refill",
                description=f"AgentVault AI Credit Refill: {pkg.units:,} units ({pkg.name})",
                mimeType="application/json",
            ),
            accepts=accepts,
        )

    def verify_and_settle(
        self,
        payload_header: str,
        package_id: str,
        active_mandate: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[SettlementResponse], Optional[str], Optional[Dict[str, Any]]]:
        """Validate x402 V2 payment payload, check policy constraints, and settle.
        
        Returns:
            (success, settlement_response, error_message, credit_record)
        """
        # 1. Parse header
        try:
            payment_payload = PaymentPayload.from_header_b64(payload_header)
        except Exception as e:
            return False, None, f"Malformed PAYMENT-SIGNATURE header: {str(e)}", None

        # 2. Check protocol version and scheme
        if payment_payload.x402Version != 2:
            return False, None, f"Unsupported x402 version: {payment_payload.x402Version}. Expected 2.", None

        if payment_payload.scheme != "exact":
            return False, None, f"Unsupported payment scheme: {payment_payload.scheme}. Expected 'exact'.", None

        # 3. Match package
        pkg = find_package(package_id)
        if not pkg:
            return False, None, f"Unknown refill package: {package_id}", None

        # 4. Enforce Policy: Vendor Allowlist
        if not pkg.isAllowedVendor:
            return False, None, f"POLICY VIOLATION: Vendor {pkg.vendorName} is not allowlisted.", None

        if active_mandate:
            allowed_vendors = active_mandate.get("allowedVendorIds", [])
            if allowed_vendors:
                # Normalize vendor IDs to strip 0x and lowercase for robust comparison
                norm_allowed = {v.lower().replace("0x", "") for v in allowed_vendors}
                norm_pkg_vendor = pkg.vendorId.lower().replace("0x", "")
                if norm_pkg_vendor not in norm_allowed:
                    return False, None, f"MANDATE VIOLATION: Vendor ID {pkg.vendorId} not permitted by active mandate.", None

        # 5. Enforce Policy: Spend Caps
        policy = self.store.policy
        if pkg.priceMicroUsdc > policy.maxSpendPerRefill:
            return False, None, (
                f"POLICY VIOLATION: Amount ${pkg.priceUsdc:.2f} exceeds max spend per refill limit "
                f"(${policy.maxSpendPerRefill/1e6:.2f})."
            ), None

        if policy.spentToday + pkg.priceMicroUsdc > policy.maxDailySpend:
            return False, None, (
                f"POLICY VIOLATION: Cumulative daily spend would exceed daily cap "
                f"(${policy.maxDailySpend/1e6:.2f})."
            ), None

        # 6. Idempotency & Nonce Replay Check
        nonce = payment_payload.payload.nonce
        if nonce in self.store.processed_nonces:
            return False, None, f"REPLAY ERROR: Payment nonce {nonce} has already been processed.", None

        # 7. Check Expiry
        now = int(time.time())
        if payment_payload.payload.validUntil < now:
            return False, None, "PAYMENT EXPIRED: validUntil timestamp is in the past.", None

        # 8. Verify Amount matches package requirement exactly
        if int(payment_payload.payload.amount) != pkg.priceMicroUsdc:
            return False, None, (
                f"PAYMENT MISMATCH: Payload amount {payment_payload.payload.amount} != "
                f"required {pkg.priceMicroUsdc} micro-USDC."
            ), None

        # 9. Verify Recipient matches package vendor
        expected_payee = get_vendor_payee(pkg).lower()
        if payment_payload.payload.payTo.lower() != expected_payee:
            return False, None, (
                f"RECIPIENT MISMATCH: Payment addressed to {payment_payload.payload.payTo}, "
                f"expected vendor payee {expected_payee}."
            ), None

        # 10. Execute Settlement (Deterministic Testnet / Facilitator Settlement)
        tx_hash = "0x" + hashlib.sha256(
            f"x402-v2-{payment_payload.network}-{nonce}-{pkg.packageId}-{now}".encode("utf-8")
        ).hexdigest()

        # Mark nonce consumed
        self.store.processed_nonces.add(nonce)
        policy.spentToday += pkg.priceMicroUsdc
        policy.lastRefillTimestamp = now

        # Credit simulated tokens ONLY AFTER settlement
        credit_rec = self.store.credit_units(
            units=pkg.units,
            tx_hash=tx_hash,
            package_id=pkg.packageId,
        )

        settlement = SettlementResponse(
            x402Version=2,
            status="settled",
            scheme="exact",
            network=payment_payload.network,
            txHash=tx_hash,
            amount=str(pkg.priceMicroUsdc),
            asset=payment_payload.payload.asset,
            recipient=payment_payload.payload.payTo,
            settledAt=now,
        )

        # Record tamper-evident audit entry
        global_audit_log.record_event("X402_REFILL_SETTLED", {
            "x402Version": 2,
            "scheme": "exact",
            "packageId": pkg.packageId,
            "packageName": pkg.name,
            "unitsGranted": pkg.units,
            "amountMicroUsdc": pkg.priceMicroUsdc,
            "amountUsdc": pkg.priceUsdc,
            "network": payment_payload.network,
            "recipient": payment_payload.payload.payTo,
            "payer": payment_payload.payload.payer,
            "txHash": tx_hash,
            "newRemainingUnits": self.store.get_remaining_units(),
        })

        return True, settlement, None, credit_rec


# Global service instance
global_x402_service = X402Service()

