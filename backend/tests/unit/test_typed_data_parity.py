"""Unit test for byte-for-byte parity between Foundry PolicyVault.sol and Python typed_data.py."""

import json
import os
import pytest
from eth_utils import keccak, to_hex
from backend.app.chain.typed_data import (
    build_domain_separator,
    hash_mandate_struct,
    hash_basket_line_struct,
    compute_basket_hash,
    hash_approval_struct,
    compute_eip712_digest,
)


def test_eip712_golden_vectors_parity():
    vector_path = os.path.join(
        os.path.dirname(__file__), "..", "vectors", "eip712_vectors.json"
    )
    assert os.path.exists(vector_path), f"Golden vectors file missing at {vector_path}"

    with open(vector_path, "r") as f:
        vectors = json.load(f)

    # Replicate exact inputs from GoldenVectors.s.sol:
    dummy_owner = "0x1111111111111111111111111111111111111111"
    dummy_agent = "0x2222222222222222222222222222222222222222"
    dummy_verifier = "0x3333333333333333333333333333333333333333"
    dummy_token = "0x4444444444444444444444444444444444444444"

    # Vendors & Categories
    v0 = to_hex(keccak(text="nimbusapi"))
    v1 = to_hex(keccak(text="tokenforge"))
    c0 = to_hex(keccak(text="AI_CREDITS"))
    c1 = to_hex(keccak(text="API_CALLS"))

    # Mandate
    mandate = {
        "owner": dummy_owner,
        "agent": dummy_agent,
        "token": dummy_token,
        "totalBudget": 100_000_000,
        "perPurchaseCap": 40_000_000,
        "dailyCap": 60_000_000,
        "allowedVendorIds": [v0, v1],
        "allowedCategoryIds": [c0, c1],
        "validFrom": 1700000000,
        "expiry": 1702592000,
        "nonce": 42,
    }

    mandate_struct_hash = to_hex(hash_mandate_struct(mandate))
    assert mandate_struct_hash.lower() == vectors["mandateStructHash"].lower(), (
        f"Mandate struct hash mismatch: {mandate_struct_hash} != {vectors['mandateStructHash']}"
    )

    # BasketLines
    line0 = {
        "quoteId": to_hex(keccak(text="quote-gold-1")),
        "vendorId": v0,
        "categoryId": c0,
        "skuId": to_hex(keccak(text="sku-gold-1")),
        "units": 100,
        "amount": 15_000_000,
    }
    line1 = {
        "quoteId": to_hex(keccak(text="quote-gold-2")),
        "vendorId": v1,
        "categoryId": c1,
        "skuId": to_hex(keccak(text="sku-gold-2")),
        "units": 50,
        "amount": 12_000_000,
    }

    line0_struct_hash = to_hex(hash_basket_line_struct(line0))
    assert line0_struct_hash.lower() == vectors["line0StructHash"].lower()

    line1_struct_hash = to_hex(hash_basket_line_struct(line1))
    assert line1_struct_hash.lower() == vectors["line1StructHash"].lower()

    basket_hash = to_hex(compute_basket_hash([line0, line1]))
    assert basket_hash.lower() == vectors["basketHash"].lower()

    # Approval
    domain_sep = bytes.fromhex(vectors["domainSeparator"][2:])
    mandate_digest = to_hex(compute_eip712_digest(domain_sep, hash_mandate_struct(mandate)))
    assert mandate_digest.lower() == vectors["mandateDigest"].lower()

    approval = {
        "mandateId": vectors["mandateDigest"],
        "approvalId": to_hex(keccak(text="approval-gold-1")),
        "basketHash": basket_hash,
        "totalAmount": 27_000_000,
        "deadline": 1700000120,
        "verifierEpoch": 1,
    }

    approval_struct_hash = to_hex(hash_approval_struct(approval))
    assert approval_struct_hash.lower() == vectors["approvalStructHash"].lower()

    approval_digest = to_hex(compute_eip712_digest(domain_sep, hash_approval_struct(approval)))
    assert approval_digest.lower() == vectors["approvalDigest"].lower()

    print("\n[ALL 7 EIP-712 GOLDEN VECTORS MATCH BYTE-FOR-BYTE WITH FOUNDRY SOLIDITY]")
