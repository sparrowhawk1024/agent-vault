// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title PolicyVault
 * @notice On-chain enforcement boundary for AgentVault: verifies EIP-712 mandates and verifier approvals,
 *         strictly caps spend, enforces vendor allowlists, and pulls funds directly to registered payees.
 */
contract PolicyVault is EIP712, Ownable, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;
    using ECDSA for bytes32;

    // --- STRUCTS ---

    struct Mandate {
        address owner;
        address agent;
        address token;
        uint256 totalBudget;
        uint256 perPurchaseCap;
        uint256 dailyCap;
        bytes32[] allowedVendorIds;
        bytes32[] allowedCategoryIds;
        uint64 validFrom;
        uint64 expiry;
        uint256 nonce;
    }

    struct BasketLine {
        bytes32 quoteId;
        bytes32 vendorId;
        bytes32 categoryId;
        bytes32 skuId;
        uint256 units;
        uint256 amount;
    }

    struct Approval {
        bytes32 mandateId;
        bytes32 approvalId;
        bytes32 basketHash;
        uint256 totalAmount;
        uint64 deadline;
        uint256 verifierEpoch;
    }

    struct Vendor {
        address payee;
        address quoteSigner;
        bool active;
    }

    // --- TYPEHASH CONSTANTS ---

    bytes32 public constant MANDATE_TYPEHASH = keccak256(
        "Mandate(address owner,address agent,address token,uint256 totalBudget,uint256 perPurchaseCap,uint256 dailyCap,bytes32[] allowedVendorIds,bytes32[] allowedCategoryIds,uint64 validFrom,uint64 expiry,uint256 nonce)"
    );

    bytes32 public constant BASKET_LINE_TYPEHASH = keccak256(
        "BasketLine(bytes32 quoteId,bytes32 vendorId,bytes32 categoryId,bytes32 skuId,uint256 units,uint256 amount)"
    );

    bytes32 public constant APPROVAL_TYPEHASH = keccak256(
        "Approval(bytes32 mandateId,bytes32 approvalId,bytes32 basketHash,uint256 totalAmount,uint64 deadline,uint256 verifierEpoch)"
    );

    bytes32 public constant QUOTE_TYPEHASH = keccak256(
        "Quote(bytes32 quoteId,bytes32 vendorId,bytes32 skuId,bytes32 categoryId,uint256 units,uint256 price,uint64 validUntil)"
    );

    // --- CUSTOM ERRORS ---

    error MandateNotFound();
    error MandateExists();
    error NonceUsed();
    error InvalidMandate();
    error TokenMismatch();
    error InvalidOwnerSignature();
    error NotMandateAgent();
    error NotMandateOwner();
    error MandateIsRevoked();
    error MandateNotYetValid();
    error MandateExpired();
    error ApprovalMandateMismatch();
    error StaleVerifierEpoch();
    error ApprovalExpired();
    error ApprovalReplayed();
    error BadVerifierSignature();
    error BasketHashMismatch();
    error EmptyBasket();
    error TooManyLines();
    error VendorNotRegistered();
    error VendorNotAllowed();
    error CategoryNotAllowed();
    error QuoteAlreadyUsed();
    error ZeroAmount();
    error TotalMismatch();
    error PerPurchaseCapExceeded();
    error BudgetExceeded();
    error DailyCapExceeded();

    // --- EVENTS ---

    event MandateCreated(bytes32 indexed mandateId, address indexed owner, address indexed agent, uint256 totalBudget);
    event MandateRevoked(bytes32 indexed mandateId, address indexed owner);
    event VendorRegistered(bytes32 indexed vendorId, address payee, address quoteSigner);
    event VendorStatusChanged(bytes32 indexed vendorId, bool active);
    event VerifierChanged(address indexed oldVerifier, address indexed newVerifier, uint256 newEpoch);
    event EpochBumped(uint256 newEpoch);
    event BasketExecuted(
        bytes32 indexed mandateId,
        bytes32 indexed approvalId,
        bytes32 basketHash,
        uint256 totalAmount,
        uint256 lineCount
    );
    event LinePaid(
        bytes32 indexed mandateId,
        bytes32 indexed approvalId,
        bytes32 indexed vendorId,
        address payee,
        uint256 amount,
        bytes32 quoteId
    );

    // --- STATE VARIABLES ---

    address public immutable token;
    address public verifier;
    uint256 public verifierEpoch;

    mapping(bytes32 => Vendor) public vendors;
    mapping(bytes32 => Mandate) private _mandates;
    mapping(bytes32 => bool) public mandateExists;
    mapping(bytes32 => bool) public isRevoked;
    mapping(address => mapping(uint256 => bool)) public nonceUsed;

    // Allowlist nested mappings: mandateId => itemId => bool
    mapping(bytes32 => mapping(bytes32 => bool)) public isVendorAllowed;
    mapping(bytes32 => mapping(bytes32 => bool)) public isCategoryAllowed;

    // Spending trackers
    mapping(bytes32 => uint256) public spentTotal;
    mapping(bytes32 => mapping(uint256 => uint256)) public dailySpent; // day = timestamp / 1 days

    // Replay protection
    mapping(bytes32 => bool) public approvalUsed;
    mapping(bytes32 => bool) public quoteUsed;

    // --- CONSTRUCTOR ---

    constructor(
        address initialOwner,
        address vaultToken,
        address initialVerifier
    ) EIP712("AgentVault", "1") Ownable(initialOwner) {
        require(vaultToken != address(0), "Zero token address");
        require(initialVerifier != address(0), "Zero verifier address");
        token = vaultToken;
        verifier = initialVerifier;
        verifierEpoch = 1;
    }

    // --- MANDATE MANAGEMENT ---

    /**
     * @notice Create and register a spending mandate using an owner's EIP-712 signature.
     * @param m The Mandate struct parameters.
     * @param ownerSig EIP-712 signature over the Mandate struct signed by m.owner.
     * @return mandateId The canonical EIP-712 digest representing the mandate.
     */
    function createMandate(Mandate calldata m, bytes calldata ownerSig) external returns (bytes32 mandateId) {
        if (m.token != token) revert TokenMismatch();
        if (m.totalBudget == 0 || m.perPurchaseCap == 0 || m.dailyCap == 0) revert InvalidMandate();
        if (m.perPurchaseCap > m.totalBudget) revert InvalidMandate();
        if (m.validFrom >= m.expiry) revert InvalidMandate();
        if (m.expiry <= block.timestamp) revert MandateExpired();
        if (m.allowedVendorIds.length == 0 || m.allowedVendorIds.length > 32) revert InvalidMandate();
        if (m.allowedCategoryIds.length == 0 || m.allowedCategoryIds.length > 32) revert InvalidMandate();
        if (nonceUsed[m.owner][m.nonce]) revert NonceUsed();

        bytes32 structHash = hashMandateStruct(m);
        mandateId = _hashTypedDataV4(structHash);

        if (mandateExists[mandateId]) revert MandateExists();

        address recovered = ECDSA.recover(mandateId, ownerSig);
        if (recovered != m.owner) revert InvalidOwnerSignature();

        // Mark nonce and state
        nonceUsed[m.owner][m.nonce] = true;
        mandateExists[mandateId] = true;
        _mandates[mandateId] = m;

        // Populate allowlists O(1)
        for (uint256 i = 0; i < m.allowedVendorIds.length; i++) {
            isVendorAllowed[mandateId][m.allowedVendorIds[i]] = true;
        }
        for (uint256 i = 0; i < m.allowedCategoryIds.length; i++) {
            isCategoryAllowed[mandateId][m.allowedCategoryIds[i]] = true;
        }

        emit MandateCreated(mandateId, m.owner, m.agent, m.totalBudget);
    }

    /**
     * @notice Revoke an active mandate. Callable only by the mandate's owner.
     * @param mandateId The ID of the mandate to revoke.
     */
    function revokeMandate(bytes32 mandateId) external {
        if (!mandateExists[mandateId]) revert MandateNotFound();
        Mandate storage m = _mandates[mandateId];
        if (msg.sender != m.owner) revert NotMandateOwner();
        if (isRevoked[mandateId]) revert MandateIsRevoked();

        isRevoked[mandateId] = true;
        emit MandateRevoked(mandateId, m.owner);
    }

    // --- EXECUTION ---

    /**
     * @notice Execute an approved procurement basket atomically.
     * @param mandateId The mandate granting spending authority.
     * @param a The verifier Approval struct.
     * @param lines Array of BasketLine items (1 to 16 lines).
     * @param verifierSig EIP-712 signature over the Approval struct signed by the active verifier.
     */
    function executeBasket(
        bytes32 mandateId,
        Approval calldata a,
        BasketLine[] calldata lines,
        bytes calldata verifierSig
    ) external nonReentrant whenNotPaused {
        // 1. Mandate checks
        if (!mandateExists[mandateId]) revert MandateNotFound();
        Mandate storage m = _mandates[mandateId];
        if (msg.sender != m.agent) revert NotMandateAgent();
        if (isRevoked[mandateId]) revert MandateIsRevoked();
        if (block.timestamp < m.validFrom) revert MandateNotYetValid();
        if (block.timestamp > m.expiry) revert MandateExpired();

        // 2. Approval checks
        if (a.mandateId != mandateId) revert ApprovalMandateMismatch();
        if (a.verifierEpoch != verifierEpoch) revert StaleVerifierEpoch();
        if (block.timestamp > a.deadline) revert ApprovalExpired();
        if (approvalUsed[a.approvalId]) revert ApprovalReplayed();

        // 3. Verifier signature recovery
        bytes32 approvalDigest = _hashTypedDataV4(hashApprovalStruct(a));
        (address recoveredVerifier, ECDSA.RecoverError err, ) = ECDSA.tryRecover(approvalDigest, verifierSig);
        if (err != ECDSA.RecoverError.NoError || recoveredVerifier != verifier) {
            revert BadVerifierSignature();
        }

        // 4. Basket line count & hash validation
        uint256 lineCount = lines.length;
        if (lineCount == 0) revert EmptyBasket();
        if (lineCount > 16) revert TooManyLines();

        bytes32 computedBasketHash = computeBasketHash(lines);
        if (computedBasketHash != a.basketHash) revert BasketHashMismatch();

        // 5. Line items loop: policy, pricing, uniqueness, totals
        uint256 calculatedTotal = 0;
        for (uint256 i = 0; i < lineCount; i++) {
            BasketLine calldata line = lines[i];

            if (line.amount == 0) revert ZeroAmount();
            if (quoteUsed[line.quoteId]) revert QuoteAlreadyUsed();

            // Enforce quoteId uniqueness within the basket
            for (uint256 j = 0; j < i; j++) {
                if (lines[j].quoteId == line.quoteId) revert QuoteAlreadyUsed();
            }

            Vendor storage vendor = vendors[line.vendorId];
            if (vendor.payee == address(0) || !vendor.active) revert VendorNotRegistered();
            if (!isVendorAllowed[mandateId][line.vendorId]) revert VendorNotAllowed();
            if (!isCategoryAllowed[mandateId][line.categoryId]) revert CategoryNotAllowed();

            calculatedTotal += line.amount;
        }

        if (calculatedTotal != a.totalAmount) revert TotalMismatch();

        // 6. Limits verification
        if (calculatedTotal > m.perPurchaseCap) revert PerPurchaseCapExceeded();
        if (spentTotal[mandateId] + calculatedTotal > m.totalBudget) revert BudgetExceeded();

        uint256 currentDay = block.timestamp / 1 days;
        if (dailySpent[mandateId][currentDay] + calculatedTotal > m.dailyCap) revert DailyCapExceeded();

        // 7. Effects first
        approvalUsed[a.approvalId] = true;
        for (uint256 i = 0; i < lineCount; i++) {
            quoteUsed[lines[i].quoteId] = true;
        }
        spentTotal[mandateId] += calculatedTotal;
        dailySpent[mandateId][currentDay] += calculatedTotal;

        // 8. Interactions: Atomic pull from owner to registered vendor payees
        address mandateOwner = m.owner;
        for (uint256 i = 0; i < lineCount; i++) {
            BasketLine calldata line = lines[i];
            address payee = vendors[line.vendorId].payee;

            IERC20(token).safeTransferFrom(mandateOwner, payee, line.amount);
            emit LinePaid(mandateId, a.approvalId, line.vendorId, payee, line.amount, line.quoteId);
        }

        emit BasketExecuted(mandateId, a.approvalId, a.basketHash, calculatedTotal, lineCount);
    }

    // --- ADMIN CONTROLS ---

    function registerVendor(bytes32 vendorId, address payee, address quoteSigner) external onlyOwner {
        require(payee != address(0), "Zero payee");
        require(quoteSigner != address(0), "Zero quote signer");
        vendors[vendorId] = Vendor({payee: payee, quoteSigner: quoteSigner, active: true});
        emit VendorRegistered(vendorId, payee, quoteSigner);
    }

    function setVendorActive(bytes32 vendorId, bool active) external onlyOwner {
        if (vendors[vendorId].payee == address(0)) revert VendorNotRegistered();
        vendors[vendorId].active = active;
        emit VendorStatusChanged(vendorId, active);
    }

    function setVerifier(address newVerifier) external onlyOwner {
        require(newVerifier != address(0), "Zero verifier");
        address oldVerifier = verifier;
        verifier = newVerifier;
        verifierEpoch++;
        emit VerifierChanged(oldVerifier, newVerifier, verifierEpoch);
    }

    function bumpVerifierEpoch() external onlyOwner {
        verifierEpoch++;
        emit EpochBumped(verifierEpoch);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // --- HASHING UTILITIES ---

    function hashMandateStruct(Mandate calldata m) public pure returns (bytes32) {
        bytes32 vendorHash = keccak256(abi.encodePacked(m.allowedVendorIds));
        bytes32 categoryHash = keccak256(abi.encodePacked(m.allowedCategoryIds));

        return keccak256(
            abi.encode(
                MANDATE_TYPEHASH,
                m.owner,
                m.agent,
                m.token,
                m.totalBudget,
                m.perPurchaseCap,
                m.dailyCap,
                vendorHash,
                categoryHash,
                m.validFrom,
                m.expiry,
                m.nonce
            )
        );
    }

    function hashBasketLineStruct(BasketLine calldata line) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                BASKET_LINE_TYPEHASH,
                line.quoteId,
                line.vendorId,
                line.categoryId,
                line.skuId,
                line.units,
                line.amount
            )
        );
    }

    function hashApprovalStruct(Approval calldata a) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                APPROVAL_TYPEHASH,
                a.mandateId,
                a.approvalId,
                a.basketHash,
                a.totalAmount,
                a.deadline,
                a.verifierEpoch
            )
        );
    }

    function computeBasketHash(BasketLine[] calldata lines) public pure returns (bytes32) {
        bytes memory concatenated = new bytes(lines.length * 32);
        for (uint256 i = 0; i < lines.length; i++) {
            bytes32 lineHash = hashBasketLineStruct(lines[i]);
            assembly {
                mstore(add(add(concatenated, 32), mul(i, 32)), lineHash)
            }
        }
        return keccak256(concatenated);
    }

    // --- VIEW FUNCTIONS ---

    function getMandate(bytes32 mandateId) external view returns (Mandate memory) {
        if (!mandateExists[mandateId]) revert MandateNotFound();
        return _mandates[mandateId];
    }

    function spentToday(bytes32 mandateId) external view returns (uint256) {
        return dailySpent[mandateId][block.timestamp / 1 days];
    }

    function domainSeparator() public view returns (bytes32) {
        return _domainSeparatorV4();
    }

    function eip712DomainHash() public view returns (bytes32) {
        return _domainSeparatorV4();
    }

    function remainingBudget(bytes32 mandateId) external view returns (uint256) {
        if (!mandateExists[mandateId]) revert MandateNotFound();
        uint256 spent = spentTotal[mandateId];
        uint256 total = _mandates[mandateId].totalBudget;
        return total > spent ? total - spent : 0;
    }
}
