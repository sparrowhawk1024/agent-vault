"""EIP-712 typing, hashing, and signature recovery for AgentVault.

Implements byte-for-byte exact EIP-712 struct hashing and digest construction
matching PolicyVault.sol.
"""

from typing import List, Dict, Any, Tuple
from eth_abi import encode
from eth_utils import keccak, to_checksum_address, to_bytes, to_hex
from eth_account import Account
from eth_account.messages import encode_defunct


# --- EIP-712 TYPE STRINGS & HASHES ---

EIP712_DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
EIP712_DOMAIN_TYPEHASH = keccak(text=EIP712_DOMAIN_TYPE)

MANDATE_TYPE = "Mandate(address owner,address agent,address token,uint256 totalBudget,uint256 perPurchaseCap,uint256 dailyCap,bytes32[] allowedVendorIds,bytes32[] allowedCategoryIds,uint64 validFrom,uint64 expiry,uint256 nonce)"
MANDATE_TYPEHASH = keccak(text=MANDATE_TYPE)

BASKET_LINE_TYPE = "BasketLine(bytes32 quoteId,bytes32 vendorId,bytes32 categoryId,bytes32 skuId,uint256 units,uint256 amount)"
BASKET_LINE_TYPEHASH = keccak(text=BASKET_LINE_TYPE)

APPROVAL_TYPE = "Approval(bytes32 mandateId,bytes32 approvalId,bytes32 basketHash,uint256 totalAmount,uint64 deadline,uint256 verifierEpoch)"
APPROVAL_TYPEHASH = keccak(text=APPROVAL_TYPE)

QUOTE_TYPE = "Quote(bytes32 quoteId,bytes32 vendorId,bytes32 skuId,bytes32 categoryId,uint256 units,uint256 price,uint64 validUntil)"
QUOTE_TYPEHASH = keccak(text=QUOTE_TYPE)


def normalize_bytes32(val: Any) -> bytes:
    """Normalize hex string or bytes to exactly 32 bytes."""
    if isinstance(val, str):
        if val.startswith("0x"):
            val = val[2:]
        b = bytes.fromhex(val)
    elif isinstance(val, (bytes, bytearray)):
        b = bytes(val)
    else:
        raise ValueError(f"Cannot convert {type(val)} to bytes32")
    if len(b) != 32:
        raise ValueError(f"Expected 32 bytes, got {len(b)} bytes")
    return b


def build_domain_separator(chain_id: int, verifying_contract: str) -> bytes:
    """Compute EIP712Domain hash for AgentVault."""
    contract_addr = to_checksum_address(verifying_contract)
    name_hash = keccak(text="AgentVault")
    version_hash = keccak(text="1")

    encoded = encode(
        ["bytes32", "bytes32", "bytes32", "uint256", "address"],
        [EIP712_DOMAIN_TYPEHASH, name_hash, version_hash, chain_id, contract_addr]
    )
    return keccak(encoded)


def hash_mandate_struct(mandate: Dict[str, Any]) -> bytes:
    """Compute hashStruct for Mandate struct."""
    owner = to_checksum_address(mandate["owner"])
    agent = to_checksum_address(mandate["agent"])
    token = to_checksum_address(mandate["token"])
    total_budget = int(mandate["totalBudget"])
    per_purchase_cap = int(mandate["perPurchaseCap"])
    daily_cap = int(mandate["dailyCap"])
    valid_from = int(mandate["validFrom"])
    expiry = int(mandate["expiry"])
    nonce = int(mandate["nonce"])

    # abi.encodePacked for bytes32 arrays
    vendor_bytes = b"".join(normalize_bytes32(v) for v in mandate["allowedVendorIds"])
    vendor_hash = keccak(vendor_bytes)

    cat_bytes = b"".join(normalize_bytes32(c) for c in mandate["allowedCategoryIds"])
    cat_hash = keccak(cat_bytes)

    encoded = encode(
        [
            "bytes32", "address", "address", "address",
            "uint256", "uint256", "uint256",
            "bytes32", "bytes32",
            "uint64", "uint64", "uint256"
        ],
        [
            MANDATE_TYPEHASH, owner, agent, token,
            total_budget, per_purchase_cap, daily_cap,
            vendor_hash, cat_hash,
            valid_from, expiry, nonce
        ]
    )
    return keccak(encoded)


def hash_basket_line_struct(line: Dict[str, Any]) -> bytes:
    """Compute hashStruct for BasketLine struct."""
    quote_id = normalize_bytes32(line["quoteId"])
    vendor_id = normalize_bytes32(line["vendorId"])
    category_id = normalize_bytes32(line["categoryId"])
    sku_id = normalize_bytes32(line["skuId"])
    units = int(line["units"])
    amount = int(line["amount"])

    encoded = encode(
        ["bytes32", "bytes32", "bytes32", "bytes32", "bytes32", "uint256", "uint256"],
        [BASKET_LINE_TYPEHASH, quote_id, vendor_id, category_id, sku_id, units, amount]
    )
    return keccak(encoded)


def compute_basket_hash(lines: List[Dict[str, Any]]) -> bytes:
    """Compute canonical basketHash = keccak256(concat(hashStruct(l0), ..., hashStruct(ln)))."""
    concatenated = b"".join(hash_basket_line_struct(l) for l in lines)
    return keccak(concatenated)


def hash_approval_struct(approval: Dict[str, Any]) -> bytes:
    """Compute hashStruct for Approval struct."""
    mandate_id = normalize_bytes32(approval["mandateId"])
    approval_id = normalize_bytes32(approval["approvalId"])
    basket_hash = normalize_bytes32(approval["basketHash"])
    total_amount = int(approval["totalAmount"])
    deadline = int(approval["deadline"])
    verifier_epoch = int(approval["verifierEpoch"])

    encoded = encode(
        ["bytes32", "bytes32", "bytes32", "bytes32", "uint256", "uint64", "uint256"],
        [APPROVAL_TYPEHASH, mandate_id, approval_id, basket_hash, total_amount, deadline, verifier_epoch]
    )
    return keccak(encoded)


def hash_quote_struct(quote: Dict[str, Any]) -> bytes:
    """Compute hashStruct for Quote struct."""
    quote_id = normalize_bytes32(quote["quoteId"])
    vendor_id = normalize_bytes32(quote["vendorId"])
    sku_id = normalize_bytes32(quote["skuId"])
    category_id = normalize_bytes32(quote["categoryId"])
    units = int(quote["units"])
    price = int(quote["price"])
    valid_until = int(quote["validUntil"])

    encoded = encode(
        ["bytes32", "bytes32", "bytes32", "bytes32", "bytes32", "uint256", "uint256", "uint64"],
        [QUOTE_TYPEHASH, quote_id, vendor_id, sku_id, category_id, units, price, valid_until]
    )
    return keccak(encoded)


def compute_eip712_digest(domain_separator: bytes, struct_hash: bytes) -> bytes:
    """Compute final EIP-712 digest: keccak256("\\x19\\x01" || domainSeparator || structHash)."""
    return keccak(b"\x19\x01" + domain_separator + struct_hash)


def sign_eip712_digest(digest: bytes, private_key: str) -> str:
    """Sign an EIP-712 digest using a private key and return hex string signature (r,s,v)."""
    account = Account.from_key(private_key)
    sig = account.unsafe_sign_hash(digest)
    return sig.signature.hex()


def recover_eip712_signer(digest: bytes, signature_hex: str) -> str:
    """Recover the signer address from an EIP-712 digest and signature."""
    sig_bytes = bytes.fromhex(signature_hex[2:] if signature_hex.startswith("0x") else signature_hex)
    recovered = Account._recover_hash(digest, signature=sig_bytes)
    return to_checksum_address(recovered)
