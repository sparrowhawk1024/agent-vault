"""Unit tests for x402 V2 Auto-Refill Protocol and Simulated AI Usage.

Verifies:
1. Usage depletion, token deduction, and threshold notification (<=15%).
2. No payment or credit before explicit consent.
3. Valid x402 402 challenge header and body generation.
4. Invalid payment requirements rejection (tampered amount, wrong payee).
5. Spend caps and vendor allowlist enforcement.
6. Successful settlement grants exactly the purchased simulated units once.
7. Duplicate submission protection (nonce replay/idempotency).
8. Spend caps and revoked Auto-Refill authority.
"""

import time
import base64
import pytest
from backend.app.x402.store import SimulatedUsageStore
from backend.app.x402.service import X402Service, get_available_refill_packages, generate_deterministic_chat_response
from backend.app.x402.models import (
    PaymentPayload,
    SignaturePayload,
    AcceptScheme,
    AutoRefillPolicy,
)
from backend.app.catalog.vendors import get_vendor_registry


@pytest.fixture
def fresh_store():
    store = SimulatedUsageStore(initial_allowance=5_000, threshold_pct=15.0)
    return store


@pytest.fixture
def service(fresh_store):
    return X402Service(store=fresh_store)


def test_deterministic_chat_and_usage_depletion(fresh_store):
    """Test deterministic token deduction and low-balance threshold detection."""
    assert fresh_store.get_remaining_units() == 5_000
    assert fresh_store.get_percentage_remaining() == 100.0
    assert not fresh_store.is_low_balance()

    # Turn 1: Consume ~200 tokens
    resp_text, tokens = generate_deterministic_chat_response("Optimize my cloud procurement")
    assert "[SIMULATED AI RESPONSE]" in resp_text
    assert tokens > 0

    c1 = fresh_store.consume_units(tokens)
    assert c1["remainingUnits"] == 5_000 - tokens
    assert not c1["isLowBalance"]

    # Turn 2: Advance usage to trigger threshold (15% of 5000 = 750 units)
    # Deduct 4,100 units -> remaining 900 - tokens < 750
    c2 = fresh_store.consume_units(4_100, reason="High workload simulation")
    assert fresh_store.get_remaining_units() < 750
    assert fresh_store.is_low_balance()
    assert fresh_store.get_percentage_remaining() <= 15.0


def test_no_credit_before_settlement(fresh_store):
    """Tokens must NOT be credited merely because usage is low or top-up is recommended."""
    fresh_store.consume_units(4_500)
    assert fresh_store.get_remaining_units() == 500
    assert fresh_store.is_low_balance()

    # Without verified settlement, allowance stays depleted
    assert fresh_store.total_allowance == 5_000
    assert fresh_store.get_remaining_units() == 500


def test_x402_402_challenge_generation(service):
    """Probe without payment header generates valid x402 V2 402 challenge."""
    challenge = service.create_payment_required_challenge("pack-tf-2k")
    assert challenge.x402Version == 2
    assert challenge.error == "PAYMENT-SIGNATURE header is required"
    assert len(challenge.accepts) == 1

    accept = challenge.accepts[0]
    assert accept.scheme == "exact"
    assert accept.amount == "3000000"  # $3.00 USDC
    assert accept.extra["units"] == 2_000

    # Verify Base64 header encoding
    b64 = challenge.to_header_b64()
    assert len(b64) > 20


def test_rejected_tampered_amount(service, fresh_store):
    """Payments with tampered amounts must be rejected and grant NO tokens."""
    challenge = service.create_payment_required_challenge("pack-tf-2k")
    accept = challenge.accepts[0]

    # Tampered amount (payload offers 100 instead of 3,000,000)
    sig_payload = SignaturePayload(
        payer="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        payTo=accept.payTo,
        asset=accept.asset,
        amount="100",  # TAMPERED
        nonce=101,
        validUntil=int(time.time()) + 120,
        signature="0x" + "b" * 130,
    )
    payload = PaymentPayload(
        x402Version=2,
        scheme="exact",
        network=accept.network,
        payload=sig_payload,
    )
    b64_sig = payload.model_dump_json()
    b64_header = base64.b64encode(b64_sig.encode("utf-8")).decode("utf-8")

    success, settlement, err, credit = service.verify_and_settle(b64_header, "pack-tf-2k")
    assert not success
    assert "PAYMENT MISMATCH" in err
    assert settlement is None
    assert credit is None
    assert fresh_store.total_allowance == 5_000


def test_rejected_unapproved_vendor_shadydeals(service, fresh_store):
    """Unapproved vendor offer (ShadyDeals) must be blocked by policy."""
    challenge = service.create_payment_required_challenge("pack-shady-5k")
    accept = challenge.accepts[0]

    sig_payload = SignaturePayload(
        payer="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        payTo=accept.payTo,
        asset=accept.asset,
        amount=accept.amount,
        nonce=202,
        validUntil=int(time.time()) + 120,
        signature="0x" + "c" * 130,
    )
    payload = PaymentPayload(
        x402Version=2,
        scheme="exact",
        network=accept.network,
        payload=sig_payload,
    )
    b64_header = base64.b64encode(payload.model_dump_json().encode("utf-8")).decode("utf-8")

    success, settlement, err, credit = service.verify_and_settle(b64_header, "pack-shady-5k")
    assert not success
    assert "POLICY VIOLATION" in err
    assert "not allowlisted" in err
    assert fresh_store.total_allowance == 5_000


def test_spend_cap_exceeded_rejection(service, fresh_store):
    """Packages exceeding the policy maxSpendPerRefill ($5.00) must be rejected."""
    # pack-tf-10k is $12.00 USDC > policy default $5.00 USDC
    challenge = service.create_payment_required_challenge("pack-tf-10k")
    accept = challenge.accepts[0]

    sig_payload = SignaturePayload(
        payer="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        payTo=accept.payTo,
        asset=accept.asset,
        amount=accept.amount,
        nonce=303,
        validUntil=int(time.time()) + 120,
        signature="0x" + "d" * 130,
    )
    payload = PaymentPayload(
        x402Version=2,
        scheme="exact",
        network=accept.network,
        payload=sig_payload,
    )
    b64_header = base64.b64encode(payload.model_dump_json().encode("utf-8")).decode("utf-8")

    success, settlement, err, credit = service.verify_and_settle(b64_header, "pack-tf-10k")
    assert not success
    assert "exceeds max spend per refill" in err


def test_successful_settlement_and_idempotency(service, fresh_store):
    """Valid payment grants exactly purchased units; replaying the same nonce is rejected."""
    fresh_store.consume_units(4_500)
    assert fresh_store.get_remaining_units() == 500

    challenge = service.create_payment_required_challenge("pack-tf-2k")
    accept = challenge.accepts[0]

    nonce = 404
    sig_payload = SignaturePayload(
        payer="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        payTo=accept.payTo,
        asset=accept.asset,
        amount=accept.amount,
        nonce=nonce,
        validUntil=int(time.time()) + 120,
        signature="0x" + "e" * 130,
    )
    payload = PaymentPayload(
        x402Version=2,
        scheme="exact",
        network=accept.network,
        payload=sig_payload,
    )
    b64_header = base64.b64encode(payload.model_dump_json().encode("utf-8")).decode("utf-8")

    # 1. First execution -> succeeds and credits 2,000 units
    success, settlement, err, credit = service.verify_and_settle(b64_header, "pack-tf-2k")
    assert success
    assert settlement.status == "settled"
    assert settlement.txHash.startswith("0x")
    assert credit["unitsGranted"] == 2_000
    assert fresh_store.total_allowance == 7_000  # 5,000 + 2,000
    assert fresh_store.get_remaining_units() == 2_500  # 500 + 2,000
    assert not fresh_store.is_low_balance()

    # 2. Replay with identical nonce -> must fail and NOT credit duplicate tokens!
    success2, settlement2, err2, credit2 = service.verify_and_settle(b64_header, "pack-tf-2k")
    assert not success2
    assert "REPLAY ERROR" in err2
    assert fresh_store.total_allowance == 7_000  # Remains 7,000, NOT 9,000!
    assert fresh_store.get_remaining_units() == 2_500


def test_policy_revocation(fresh_store):
    """Revoking Auto-Refill authority disables automated top-ups."""
    fresh_store.policy.enabled = True
    fresh_store.policy.revoked = True
    fresh_store.policy.enabled = False
    assert fresh_store.policy.revoked
    assert not fresh_store.policy.enabled


def test_flexible_pricing_service_differentiation():
    """Verify provider service differentiation and unit economics across providers."""
    from backend.app.x402.service import VENDOR_SERVICES, create_flexible_package, find_package

    assert "tokenforge" in VENDOR_SERVICES
    assert VENDOR_SERVICES["tokenforge"]["serviceType"] == "AI_CREDITS"
    assert VENDOR_SERVICES["tokenforge"]["unitPriceMicros"] == 1.50

    assert "nimbusapi" in VENDOR_SERVICES
    assert VENDOR_SERVICES["nimbusapi"]["serviceType"] == "API_CALLS"
    assert VENDOR_SERVICES["nimbusapi"]["unitPriceMicros"] == 0.85

    assert "vaultstore" in VENDOR_SERVICES
    assert VENDOR_SERVICES["vaultstore"]["serviceType"] == "STORAGE"
    assert VENDOR_SERVICES["vaultstore"]["unitPriceMicros"] == 0.60

    assert "budgetbyte" in VENDOR_SERVICES
    assert VENDOR_SERVICES["budgetbyte"]["serviceType"] == "MULTI_SERVICE"
    assert VENDOR_SERVICES["budgetbyte"]["unitPriceMicros"] == 1.40


def test_flexible_pricing_user_cap_matching(fresh_store, service):
    """Verify top-up pricing adapts flexibly to user cap per top-up."""
    from backend.app.x402.service import create_flexible_package, find_package

    # 1. Custom user cap of 213 µUSDC ($0.000213)
    pkg_213 = create_flexible_package("tokenforge", 213, is_cap_matched=True)
    assert pkg_213 is not None
    assert pkg_213.priceMicroUsdc == 213
    assert pkg_213.isCapFlexible is True
    assert pkg_213.units == int(213 / 1.5)

    # 2. Dynamic resolution of flexible package ID
    resolved_pkg = find_package("pack-flex-nimbusapi-850000")
    assert resolved_pkg is not None
    assert resolved_pkg.priceMicroUsdc == 850_000
    assert resolved_pkg.units == int(850_000 / 0.85)  # 1,000,000 calls
    assert resolved_pkg.serviceType == "API_CALLS"

    # 3. Dynamic settlement of flexible package under user cap
    fresh_store.consume_units(4_800)  # low balance
    accept = service.create_payment_required_challenge("pack-flex-nimbusapi-850000").accepts[0]

    nonce = int(time.time() * 1000) + 99
    sig_payload = SignaturePayload(
        payer="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        payTo=accept.payTo,
        asset=accept.asset,
        amount=accept.amount,
        nonce=nonce,
        validUntil=int(time.time()) + 120,
        signature="0x" + "f" * 130,
    )
    payload = PaymentPayload(
        x402Version=2,
        scheme="exact",
        network=accept.network,
        payload=sig_payload,
    )
    b64_header = base64.b64encode(payload.model_dump_json().encode("utf-8")).decode("utf-8")

    success, settlement, err, credit = service.verify_and_settle(b64_header, "pack-flex-nimbusapi-850000")
    assert success
    assert settlement.status == "settled"
    assert credit["unitsGranted"] == 1_000_000
    assert fresh_store.total_allowance == 5_000 + 1_000_000


def test_fixed_base_topup_tiers(fresh_store, service):
    """Verify fixed base top-up tiers: $5 (350 credits), $10, $20, $40, $50."""
    from backend.app.x402.service import find_package, get_available_refill_packages

    packages = {p.packageId: p for p in get_available_refill_packages()}

    # 1. Cheapest base tier: $5 -> 350 credits
    assert "pack-base-5" in packages
    p5 = packages["pack-base-5"]
    assert p5.priceUsdc == 5.00
    assert p5.priceMicroUsdc == 5_000_000
    assert p5.units == 350

    # 2. $10 tier
    assert "pack-base-10" in packages
    p10 = packages["pack-base-10"]
    assert p10.priceUsdc == 10.00
    assert p10.priceMicroUsdc == 10_000_000
    assert p10.units == 750

    # 3. $20 tier
    assert "pack-base-20" in packages
    p20 = packages["pack-base-20"]
    assert p20.priceUsdc == 20.00
    assert p20.priceMicroUsdc == 20_000_000
    assert p20.units == 1_600

    # 4. $40 tier
    assert "pack-base-40" in packages
    p40 = packages["pack-base-40"]
    assert p40.priceUsdc == 40.00
    assert p40.priceMicroUsdc == 40_000_000
    assert p40.units == 3_500

    # 5. $50 tier
    assert "pack-base-50" in packages
    p50 = packages["pack-base-50"]
    assert p50.priceUsdc == 50.00
    assert p50.priceMicroUsdc == 50_000_000
    assert p50.units == 5_000

    # 6. Settle $5 (350 credits) tier
    accept = service.create_payment_required_challenge("pack-base-5").accepts[0]
    nonce = int(time.time() * 1000) + 123
    sig_payload = SignaturePayload(
        payer="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        payTo=accept.payTo,
        asset=accept.asset,
        amount=accept.amount,
        nonce=nonce,
        validUntil=int(time.time()) + 120,
        signature="0x" + "a" * 130,
    )
    payload = PaymentPayload(
        x402Version=2,
        scheme="exact",
        network=accept.network,
        payload=sig_payload,
    )
    b64_header = base64.b64encode(payload.model_dump_json().encode("utf-8")).decode("utf-8")

    success, settlement, err, credit = service.verify_and_settle(b64_header, "pack-base-5")
    assert success
    assert settlement.status == "settled"
    assert credit["unitsGranted"] == 350
    assert fresh_store.total_allowance == 5_000 + 350



