// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {StdInvariant} from "forge-std/StdInvariant.sol";
import {PolicyVault} from "../src/PolicyVault.sol";
import {MockUSDC} from "../src/MockUSDC.sol";

contract VaultHandler is Test {
    PolicyVault public vault;
    MockUSDC public usdc;
    bytes32 public mandateId;

    address internal owner;
    address internal agent;
    address internal verifier;

    uint256 internal ownerPk = 0xA11CE;
    uint256 internal agentPk = 0xB0B;
    uint256 internal verifierPk = 0xCAFE;

    bytes32 internal vendor1Id = keccak256("nimbusapi");
    bytes32 internal catAi = keccak256("AI_CREDITS");

    uint256 public totalPaidCumulative;
    uint256 public quoteNonce;
    uint256 public approvalNonce;

    mapping(bytes32 => bool) public usedQuotes;
    mapping(bytes32 => bool) public usedApprovals;

    constructor(PolicyVault _vault, MockUSDC _usdc, bytes32 _mandateId, address _owner, address _agent, address _verifier) {
        vault = _vault;
        usdc = _usdc;
        mandateId = _mandateId;
        owner = _owner;
        agent = _agent;
        verifier = _verifier;
    }

    function executeRandomBasket(uint256 rawAmount, uint256 warpSeconds) external {
        // Bound warp seconds up to 2 days
        uint256 warpTime = bound(warpSeconds, 0, 2 days);
        if (warpTime > 0) {
            vm.warp(block.timestamp + warpTime);
        }

        // Amount bounded between 1 micro-USDC and 40 USDC (per purchase cap)
        uint256 amount = bound(rawAmount, 1, 40_000_000);

        quoteNonce++;
        bytes32 quoteId = keccak256(abi.encodePacked("invariant-quote", quoteNonce));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine({
            quoteId: quoteId,
            vendorId: vendor1Id,
            categoryId: catAi,
            skuId: keccak256("sku-ai"),
            units: 10,
            amount: amount
        });

        bytes32 bHash = vault.computeBasketHash(lines);

        approvalNonce++;
        bytes32 approvalId = keccak256(abi.encodePacked("invariant-approval", approvalNonce));

        PolicyVault.Approval memory approval = PolicyVault.Approval({
            mandateId: mandateId,
            approvalId: approvalId,
            basketHash: bHash,
            totalAmount: amount,
            deadline: uint64(block.timestamp + 120),
            verifierEpoch: vault.verifierEpoch()
        });

        bytes32 structHash = vault.hashApprovalStruct(approval);
        bytes32 digest = keccak256(
            abi.encodePacked("\x19\x01", vault.eip712DomainHash(), structHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(verifierPk, digest);
        bytes memory sig = abi.encodePacked(r, s, v);

        // Record check before execution
        uint256 spentTot = vault.spentTotal(mandateId);
        uint256 spentDay = vault.spentToday(mandateId);

        // Pre-checks against mandate limits (totalBudget=100M, perPurchaseCap=40M, dailyCap=60M)
        bool willExceedBudget = (spentTot + amount > 100_000_000);
        bool willExceedDaily = (spentDay + amount > 60_000_000);

        vm.prank(agent);
        try vault.executeBasket(mandateId, approval, lines, sig) {
            // Execution succeeded
            assertTrue(!willExceedBudget, "Invariant violated: executed over budget");
            assertTrue(!willExceedDaily, "Invariant violated: executed over daily cap");

            totalPaidCumulative += amount;
            usedQuotes[quoteId] = true;
            usedApprovals[approvalId] = true;
        } catch {
            // Expected rejection when caps reached or conditions not met
        }
    }
}

contract PolicyVaultInvariantTest is StdInvariant, Test {
    PolicyVault public vault;
    MockUSDC public usdc;
    VaultHandler public handler;
    bytes32 public mandateId;

    uint256 internal ownerPk = 0xA11CE;
    uint256 internal agentPk = 0xB0B;
    uint256 internal verifierPk = 0xCAFE;

    address internal owner;
    address internal agent;
    address internal verifier;

    bytes32 internal vendor1Id = keccak256("nimbusapi");
    bytes32 internal catAi = keccak256("AI_CREDITS");

    function setUp() public {
        owner = vm.addr(ownerPk);
        agent = vm.addr(agentPk);
        verifier = vm.addr(verifierPk);

        usdc = new MockUSDC();
        vault = new PolicyVault(owner, address(usdc), verifier);

        vm.prank(owner);
        vault.registerVendor(vendor1Id, address(0x101), address(0x102));

        usdc.mint(owner, 100_000_000); // 100 USDC
        vm.prank(owner);
        usdc.approve(address(vault), 100_000_000);

        // Create standard mandate
        bytes32[] memory vList = new bytes32[](1);
        vList[0] = vendor1Id;
        bytes32[] memory cList = new bytes32[](1);
        cList[0] = catAi;

        PolicyVault.Mandate memory m = PolicyVault.Mandate({
            owner: owner,
            agent: agent,
            token: address(usdc),
            totalBudget: 100_000_000,
            perPurchaseCap: 40_000_000,
            dailyCap: 60_000_000,
            allowedVendorIds: vList,
            allowedCategoryIds: cList,
            validFrom: uint64(block.timestamp),
            expiry: uint64(block.timestamp + 30 days),
            nonce: 0
        });

        bytes32 structHash = vault.hashMandateStruct(m);
        bytes32 digest = keccak256(
            abi.encodePacked("\x19\x01", vault.eip712DomainHash(), structHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(ownerPk, digest);
        mandateId = vault.createMandate(m, abi.encodePacked(r, s, v));

        handler = new VaultHandler(vault, usdc, mandateId, owner, agent, verifier);
        targetContract(address(handler));
    }

    /// @notice Invariant 1: spentTotal never exceeds totalBudget (100 USDC)
    function invariant_spentTotalNeverExceedsTotalBudget() public view {
        assertLe(vault.spentTotal(mandateId), 100_000_000);
    }

    /// @notice Invariant 2: spentToday never exceeds dailyCap (60 USDC)
    function invariant_spentTodayNeverExceedsDailyCap() public view {
        assertLe(vault.spentToday(mandateId), 60_000_000);
    }

    /// @notice Invariant 3: spentTotal equals the cumulative sum of paid lines
    function invariant_spentTotalEqualsCumulativePaid() public view {
        assertEq(vault.spentTotal(mandateId), handler.totalPaidCumulative());
    }
}
