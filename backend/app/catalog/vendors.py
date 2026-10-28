"""Vendor registry and deterministic key derivation for AgentVault.

Five synthetic vendors (labelled TEST DATA):
1. NimbusAPI: API capacity (API_CALLS)
2. TokenForge: AI credits (AI_CREDITS)
3. VaultStore: Cloud storage (STORAGE)
4. BudgetByte: All three categories, cheap, short quote expiry
5. ShadyDeals: Cheapest per unit, NOT allowlisted, contains prompt injection lures
"""

import os
from typing import Dict, Any, List
from eth_utils import keccak, to_hex, to_checksum_address
from eth_account import Account

# Categories
CATEGORIES: Dict[str, Dict[str, Any]] = {
    "AI_CREDITS": {
        "id": to_hex(keccak(text="AI_CREDITS")),
        "name": "AI Credits",
        "description": "Model token inference capacity",
    },
    "API_CALLS": {
        "id": to_hex(keccak(text="API_CALLS")),
        "name": "API Calls",
        "description": "Authenticated REST and RPC throughput",
    },
    "STORAGE": {
        "id": to_hex(keccak(text="STORAGE")),
        "name": "Storage Units",
        "description": "High-durability blob storage capacity (GB-months)",
    },
}

VENDOR_NAMES = [
    "nimbusapi",
    "tokenforge",
    "vaultstore",
    "budgetbyte",
    "shadydeals",
]


def derive_vendor_key(seed: str, vendor_name: str, key_type: str) -> str:
    """Derive deterministic private key for a vendor's payee or signer.
    Matches Deploy.s.sol derivation:
    keccak256(abi.encodePacked(seed, vName, key_type))
    """
    raw = (seed + vendor_name + key_type).encode("utf-8")
    pk_bytes = keccak(raw)
    return to_hex(pk_bytes)


def get_vendor_registry(seed: str = "agentvault-test-seed") -> Dict[str, Dict[str, Any]]:
    """Return dictionary of 5 vendors with their deterministic keys, payees, and signers."""
    registry = {}
    for vname in VENDOR_NAMES:
        vid = to_hex(keccak(text=vname))
        payee_pk = derive_vendor_key(seed, vname, "payee")
        signer_pk = derive_vendor_key(seed, vname, "signer")
        payee_addr = to_checksum_address(Account.from_key(payee_pk).address)
        signer_addr = to_checksum_address(Account.from_key(signer_pk).address)

        # Allowlist status: shadydeals is intentionally untrusted/not allowlisted
        is_default_allowed = (vname != "shadydeals")

        registry[vname] = {
            "name": vname,
            "vendorId": vid,
            "payee": payee_addr,
            "payeePrivateKey": payee_pk,
            "quoteSigner": signer_addr,
            "quoteSignerPrivateKey": signer_pk,
            "active": True,
            "defaultAllowed": is_default_allowed,
        }
    return registry
