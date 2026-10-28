"""Unit tests for AgentVault catalog generator and vendor registry."""

import pytest
from eth_utils import to_checksum_address
from eth_account import Account

from backend.app.catalog.vendors import get_vendor_registry, CATEGORIES, derive_vendor_key
from backend.app.catalog.generator import generate_catalog
from backend.app.chain.typed_data import (
    build_domain_separator,
    hash_quote_struct,
    compute_eip712_digest,
    recover_eip712_signer,
)


def test_vendor_registry_derivation():
    registry = get_vendor_registry(seed="agentvault-test-seed")
    assert len(registry) == 5
    assert "nimbusapi" in registry
    assert "tokenforge" in registry
    assert "vaultstore" in registry
    assert "budgetbyte" in registry
    assert "shadydeals" in registry

    # Verify shadydeals is not default allowed
    assert registry["shadydeals"]["defaultAllowed"] is False
    assert registry["nimbusapi"]["defaultAllowed"] is True

    # Verify payee and quoteSigner are distinct addresses
    for vname, vdata in registry.items():
        assert vdata["payee"] != vdata["quoteSigner"]
        assert len(vdata["vendorId"]) == 66  # 0x + 64 hex


def test_catalog_generation_and_signatures():
    dummy_vault = "0x1111111111111111111111111111111111111111"
    chain_id = 31337
    domain_sep = build_domain_separator(chain_id, dummy_vault)

    quotes = generate_catalog(
        seed=1,
        now_timestamp=1700000000,
        vault_address=dummy_vault,
        chain_id=chain_id,
    )

    # Expected ~50 quotes
    assert 45 <= len(quotes) <= 60

    registry = get_vendor_registry()

    categories_seen = set()
    near_expiry_count = 0
    hostile_count = 0

    for q in quotes:
        # Check required fields
        assert "quoteId" in q
        assert "vendorId" in q
        assert "skuId" in q
        assert "categoryId" in q
        assert "units" in q and q["units"] > 0
        assert "price" in q and q["price"] > 0
        assert "validUntil" in q
        assert "signature" in q
        assert "description" in q

        categories_seen.add(q["categoryName"])

        # Cryptographic verification of vendor EIP-712 quote signature
        struct_hash = hash_quote_struct(q)
        digest = compute_eip712_digest(domain_sep, struct_hash)
        recovered_signer = recover_eip712_signer(digest, q["signature"])

        vname = q["vendorName"]
        expected_signer = registry[vname]["quoteSigner"]
        assert recovered_signer.lower() == expected_signer.lower(), (
            f"Signature mismatch for vendor {vname}"
        )

        # Count near expiry quotes
        if q["validUntil"] <= 1700000000 + 60:
            near_expiry_count += 1

        # Count hostile prompt injection quotes
        if vname == "shadydeals":
            hostile_count += 1
            assert any(term in q["description"] for term in ["OVERRIDE", "address", "budget", "discount", "SECURITY"])

    assert len(categories_seen) == 3
    assert near_expiry_count >= 1
    assert hostile_count >= 5
