"""Custom error decoder for PolicyVault."""

from eth_utils import keccak

CUSTOM_ERRORS = [
    "MandateNotFound",
    "MandateExists",
    "NonceUsed",
    "InvalidMandate",
    "TokenMismatch",
    "InvalidOwnerSignature",
    "NotMandateAgent",
    "NotMandateOwner",
    "MandateIsRevoked",
    "MandateNotYetValid",
    "MandateExpired",
    "ApprovalMandateMismatch",
    "StaleVerifierEpoch",
    "ApprovalExpired",
    "ApprovalReplayed",
    "BadVerifierSignature",
    "BasketHashMismatch",
    "EmptyBasket",
    "TooManyLines",
    "VendorNotRegistered",
    "VendorNotAllowed",
    "CategoryNotAllowed",
    "QuoteAlreadyUsed",
    "ZeroAmount",
    "TotalMismatch",
    "PerPurchaseCapExceeded",
    "BudgetExceeded",
    "DailyCapExceeded",
]

# Map 4-byte selector (e.g. 0x12345678) -> Error Name
ERROR_SELECTORS = {
    keccak(text=f"{name}()")[:4].hex(): name for name in CUSTOM_ERRORS
}

# Add standard OpenZeppelin errors
ERROR_SELECTORS[keccak(text="EnforcedPause()")[:4].hex()] = "EnforcedPause"
ERROR_SELECTORS[keccak(text="ExpectedPause()")[:4].hex()] = "ExpectedPause"
ERROR_SELECTORS[keccak(text="ReentrancyGuardReentrantCall()")[:4].hex()] = "ReentrancyGuardReentrantCall"
ERROR_SELECTORS[keccak(text="OwnableUnauthorizedAccount(address)")[:4].hex()] = "OwnableUnauthorizedAccount"
ERROR_SELECTORS[keccak(text="SafeERC20FailedOperation(address)")[:4].hex()] = "SafeERC20FailedOperation"


def decode_custom_error(revert_data_hex: str) -> str:
    """Decode revert data hex into custom error name."""
    if not revert_data_hex or revert_data_hex == "0x":
        return "UnknownRevert(empty)"
    clean = revert_data_hex[2:] if revert_data_hex.startswith("0x") else revert_data_hex
    if len(clean) >= 8:
        selector = clean[:8].lower()
        if selector in ERROR_SELECTORS:
            return ERROR_SELECTORS[selector]
    return f"UnknownRevert({revert_data_hex[:10]})"
