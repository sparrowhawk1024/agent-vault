// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {StdInvariant} from "forge-std/StdInvariant.sol";
import {console2} from "forge-std/console2.sol";
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
    uint256 internal roguePk = 0xDEAD;

    bytes32 internal vendor1Id = keccak256("nimbusapi");
    bytes32 internal vendor2Id = keccak256("tokenforge");
    bytes32 internal vendorUnregId = keccak256("unregistered_vendor");
    bytes32 internal catAi = keccak256("AI_CREDITS");
    bytes32 internal catApi = keccak256("API_CALLS");

    // --- GHOST COUNTERS (Tracked independently from contract state) ---
    uint256 public ghost_totalPaidCumulative;
    uint256 public ghost_successfulBasketCount;
    uint256 public ghost_successfulLineCount;
    uint256 public ghost_quoteConsumedCount;
    uint256 public ghost_approvalConsumedCount;

    mapping(uint256 => uint256) public ghost_dailyPaid;
    mapping(bytes32 => uint256) public ghost_vendorPayouts;

    bytes32[] public consumedApprovalIds;
    bytes32[] public consumedQuoteIds;

    uint256 public quoteNonce;
    uint256 public approvalNonce;
    uint256 public disposableNonce = 5000;

    // --- PER-ACTION GHOST COUNTERS ---
    uint256 public ghost_success_executeBasket;
    uint256 public ghost_failure_executeBasket;

    uint256 public ghost_success_revoke;
    uint256 public ghost_failure_revoke;

    uint256 public ghost_success_epochBump;
    uint256 public ghost_failure_epochBump;

    uint256 public ghost_success_setVerifier;
    uint256 public ghost_failure_setVerifier;

    uint256 public ghost_success_timeWarp;
    uint256 public ghost_failure_timeWarp;

    uint256 public ghost_success_overCap;
    uint256 public ghost_failure_overCap;

    uint256 public ghost_success_unregisteredVendor;
    uint256 public ghost_failure_unregisteredVendor;

    uint256 public ghost_success_badSignature;
    uint256 public ghost_failure_badSignature;

    uint256 public ghost_success_duplicateQuote;
    uint256 public ghost_failure_duplicateQuote;

    uint256 public ghost_totalSuccesses;
    uint256 public ghost_totalFailures;

    constructor(
        PolicyVault _vault,
        MockUSDC _usdc,
        bytes32 _mandateId,
        address _owner,
        address _agent,
        address _verifier
    ) {
        vault = _vault;
        usdc = _usdc;
        mandateId = _mandateId;
        owner = _owner;
        agent = _agent;
        verifier = _verifier;
    }

    // --- ACTION 1: EXECUTE RANDOM BASKET ---
    function executeRandomBasket(uint256 rawAmount, uint256 warpSeconds, bool multiLine) external {
        uint256 warpTime = bound(warpSeconds, 0, 1 days);
        if (warpTime > 0) {
            vm.warp(block.timestamp + warpTime);
        }

        uint256 lineCount = multiLine ? 2 : 1;
        uint256 perLineAmount = bound(rawAmount, 1, 20_000_000); // 1 uUSDC to 20 USDC
        uint256 totalBasketAmount = perLineAmount * lineCount;

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](lineCount);

        quoteNonce++;
        bytes32 qId1 = keccak256(abi.encodePacked("inv-quote-1", quoteNonce));
        lines[0] = PolicyVault.BasketLine({
            quoteId: qId1,
            vendorId: vendor1Id,
            categoryId: catAi,
            skuId: keccak256("sku-ai"),
            units: 10,
            amount: perLineAmount
        });

        bytes32 qId2;
        if (lineCount > 1) {
            quoteNonce++;
            qId2 = keccak256(abi.encodePacked("inv-quote-2", quoteNonce));
            lines[1] = PolicyVault.BasketLine({
                quoteId: qId2,
                vendorId: vendor2Id,
                categoryId: catApi,
                skuId: keccak256("sku-api"),
                units: 10,
                amount: perLineAmount
            });
        }

        bytes32 bHash = vault.computeBasketHash(lines);

        approvalNonce++;
        bytes32 approvalId = keccak256(abi.encodePacked("inv-approval", approvalNonce));

        PolicyVault.Approval memory approval = PolicyVault.Approval({
            mandateId: mandateId,
            approvalId: approvalId,
            basketHash: bHash,
            totalAmount: totalBasketAmount,
            deadline: uint64(block.timestamp + 120),
            verifierEpoch: vault.verifierEpoch()
        });

        bytes32 structHash = vault.hashApprovalStruct(approval);
        bytes32 digest = keccak256(
            abi.encodePacked("\x19\x01", vault.eip712DomainHash(), structHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(verifierPk, digest);
        bytes memory sig = abi.encodePacked(r, s, v);

        uint256 currentDay = block.timestamp / 1 days;

        vm.prank(agent);
        try vault.executeBasket(mandateId, approval, lines, sig) {
            ghost_totalPaidCumulative += totalBasketAmount;
            ghost_dailyPaid[currentDay] += totalBasketAmount;
            ghost_successfulBasketCount++;
            ghost_successfulLineCount += lineCount;

            ghost_vendorPayouts[vendor1Id] += perLineAmount;
            consumedQuoteIds.push(qId1);
            ghost_quoteConsumedCount++;

            if (lineCount > 1) {
                ghost_vendorPayouts[vendor2Id] += perLineAmount;
                consumedQuoteIds.push(qId2);
                ghost_quoteConsumedCount++;
            }

            consumedApprovalIds.push(approvalId);
            ghost_approvalConsumedCount++;

            ghost_success_executeBasket++;
            ghost_totalSuccesses++;
        } catch {
            ghost_failure_executeBasket++;
            ghost_totalFailures++;
        }
    }

    // --- ACTION 2: REPLAY USED APPROVAL ---
    function replayUsedApproval(uint256 seedIndex) external {
        if (consumedApprovalIds.length == 0) return;
        uint256 idx = seedIndex % consumedApprovalIds.length;
        bytes32 usedAppId = consumedApprovalIds[idx];

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine({
            quoteId: keccak256(abi.encodePacked("replay-q", quoteNonce++)),
            vendorId: vendor1Id,
            categoryId: catAi,
            skuId: keccak256("sku-ai"),
            units: 1,
            amount: 1_000_000
        });

        PolicyVault.Approval memory a = PolicyVault.Approval({
            mandateId: mandateId,
            approvalId: usedAppId,
            basketHash: vault.computeBasketHash(lines),
            totalAmount: 1_000_000,
            deadline: uint64(block.timestamp + 120),
            verifierEpoch: vault.verifierEpoch()
        });

        bytes32 sHash = vault.hashApprovalStruct(a);
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", vault.eip712DomainHash(), sHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(verifierPk, digest);

        vm.prank(agent);
        try vault.executeBasket(mandateId, a, lines, abi.encodePacked(r, s, v)) {
            revert("CRITICAL: Replayed approval succeeded!");
        } catch {
            ghost_totalFailures++;
        }
    }

    // --- ACTION 3: REVOKE MANDATE ---
    function action_revokeMandate(bool asOwner) external {
        if (asOwner) {
            // Owner creates a disposable mandate and revokes it
            disposableNonce++;
            bytes32[] memory vList = new bytes32[](1);
            vList[0] = vendor1Id;
            bytes32[] memory cList = new bytes32[](1);
            cList[0] = catAi;

            PolicyVault.Mandate memory dm = PolicyVault.Mandate({
                owner: owner,
                agent: agent,
                token: address(usdc),
                totalBudget: 1_000_000,
                perPurchaseCap: 500_000,
                dailyCap: 1_000_000,
                allowedVendorIds: vList,
                allowedCategoryIds: cList,
                validFrom: uint64(block.timestamp),
                expiry: uint64(block.timestamp + 1 days),
                nonce: disposableNonce
            });

            bytes32 sHash = vault.hashMandateStruct(dm);
            bytes32 digest = keccak256(abi.encodePacked("\x19\x01", vault.eip712DomainHash(), sHash));
            (uint8 v, bytes32 r, bytes32 s) = vm.sign(ownerPk, digest);
            bytes32 dmId = vault.createMandate(dm, abi.encodePacked(r, s, v));

            vm.prank(owner);
            try vault.revokeMandate(dmId) {
                ghost_success_revoke++;
                ghost_totalSuccesses++;
            } catch {
                ghost_failure_revoke++;
                ghost_totalFailures++;
            }
        } else {
            // Unauthorized caller attempts to revoke active mandate
            vm.prank(agent);
            try vault.revokeMandate(mandateId) {
                revert("CRITICAL: Non-owner revoked mandate!");
            } catch {
                ghost_failure_revoke++;
                ghost_totalFailures++;
            }
        }
    }

    // --- ACTION 4: EPOCH BUMP ---
    function action_bumpEpoch(bool asOwner) external {
        if (asOwner) {
            vm.prank(owner);
            try vault.bumpVerifierEpoch() {
                ghost_success_epochBump++;
                ghost_totalSuccesses++;
            } catch {
                ghost_failure_epochBump++;
                ghost_totalFailures++;
            }
        } else {
            vm.prank(agent);
            try vault.bumpVerifierEpoch() {
                revert("CRITICAL: Non-owner bumped epoch!");
            } catch {
                ghost_failure_epochBump++;
                ghost_totalFailures++;
            }
        }
    }

    // --- ACTION 5: SET VERIFIER ---
    function action_setVerifier(bool asOwner) external {
        if (asOwner) {
            vm.prank(owner);
            try vault.setVerifier(verifier) {
                ghost_success_setVerifier++;
                ghost_totalSuccesses++;
            } catch {
                ghost_failure_setVerifier++;
                ghost_totalFailures++;
            }
        } else {
            vm.prank(agent);
            try vault.setVerifier(address(0xDEAD)) {
                revert("CRITICAL: Non-owner set verifier!");
            } catch {
                ghost_failure_setVerifier++;
                ghost_totalFailures++;
            }
        }
    }

    // --- ACTION 6: TIME WARP ---
    function action_timeWarp(uint256 warpSeconds, bool testExpiredApproval) external {
        if (testExpiredApproval) {
            // Create an approval with a 60-second deadline, warp 120 seconds, and attempt execute
            PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
            lines[0] = PolicyVault.BasketLine({
                quoteId: keccak256(abi.encodePacked("warp-q", quoteNonce++)),
                vendorId: vendor1Id,
                categoryId: catAi,
                skuId: keccak256("sku-ai"),
                units: 1,
                amount: 100_000
            });
            bytes32 bHash = vault.computeBasketHash(lines);
            PolicyVault.Approval memory app = PolicyVault.Approval({
                mandateId: mandateId,
                approvalId: keccak256(abi.encodePacked("warp-app", approvalNonce++)),
                basketHash: bHash,
                totalAmount: 100_000,
                deadline: uint64(block.timestamp + 60),
                verifierEpoch: vault.verifierEpoch()
            });
            bytes32 sHash = vault.hashApprovalStruct(app);
            bytes32 digest = keccak256(abi.encodePacked("\x19\x01", vault.eip712DomainHash(), sHash));
            (uint8 v, bytes32 r, bytes32 s) = vm.sign(verifierPk, digest);

            vm.warp(block.timestamp + 120);

            vm.prank(agent);
            try vault.executeBasket(mandateId, app, lines, abi.encodePacked(r, s, v)) {
                revert("CRITICAL: Expired approval executed!");
            } catch {
                ghost_failure_timeWarp++;
                ghost_totalFailures++;
            }
        } else {
            uint256 warp = bound(warpSeconds, 1, 1 days);
            vm.warp(block.timestamp + warp);
            ghost_success_timeWarp++;
            ghost_totalSuccesses++;
        }
    }

    // --- ACTION 7: OVER-CAP BASKET ---
    function action_overCap(uint256 rawAmount) external {
        uint256 excessAmount = bound(rawAmount, 40_000_001, 80_000_000); // Exceeds perPurchaseCap of 40 USDC
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine({
            quoteId: keccak256(abi.encodePacked("overcap-q", quoteNonce++)),
            vendorId: vendor1Id,
            categoryId: catAi,
            skuId: keccak256("sku-ai"),
            units: 1,
            amount: excessAmount
        });
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory app = PolicyVault.Approval({
            mandateId: mandateId,
            approvalId: keccak256(abi.encodePacked("overcap-app", approvalNonce++)),
            basketHash: bHash,
            totalAmount: excessAmount,
            deadline: uint64(block.timestamp + 120),
            verifierEpoch: vault.verifierEpoch()
        });
        bytes32 sHash = vault.hashApprovalStruct(app);
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", vault.eip712DomainHash(), sHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(verifierPk, digest);

        vm.prank(agent);
        try vault.executeBasket(mandateId, app, lines, abi.encodePacked(r, s, v)) {
            revert("CRITICAL: Over-cap basket executed!");
        } catch {
            ghost_failure_overCap++;
            ghost_totalFailures++;
        }
    }

    // --- ACTION 8: UNREGISTERED VENDOR ---
    function action_unregisteredVendor() external {
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine({
            quoteId: keccak256(abi.encodePacked("unreg-q", quoteNonce++)),
            vendorId: vendorUnregId,
            categoryId: catAi,
            skuId: keccak256("sku-ai"),
            units: 1,
            amount: 100_000
        });
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory app = PolicyVault.Approval({
            mandateId: mandateId,
            approvalId: keccak256(abi.encodePacked("unreg-app", approvalNonce++)),
            basketHash: bHash,
            totalAmount: 100_000,
            deadline: uint64(block.timestamp + 120),
            verifierEpoch: vault.verifierEpoch()
        });
        bytes32 sHash = vault.hashApprovalStruct(app);
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", vault.eip712DomainHash(), sHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(verifierPk, digest);

        vm.prank(agent);
        try vault.executeBasket(mandateId, app, lines, abi.encodePacked(r, s, v)) {
            revert("CRITICAL: Unregistered vendor basket executed!");
        } catch {
            ghost_failure_unregisteredVendor++;
            ghost_totalFailures++;
        }
    }

    // --- ACTION 9: BAD VERIFIER SIGNATURE ---
    function action_badSignature() external {
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine({
            quoteId: keccak256(abi.encodePacked("badsig-q", quoteNonce++)),
            vendorId: vendor1Id,
            categoryId: catAi,
            skuId: keccak256("sku-ai"),
            units: 1,
            amount: 100_000
        });
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory app = PolicyVault.Approval({
            mandateId: mandateId,
            approvalId: keccak256(abi.encodePacked("badsig-app", approvalNonce++)),
            basketHash: bHash,
            totalAmount: 100_000,
            deadline: uint64(block.timestamp + 120),
            verifierEpoch: vault.verifierEpoch()
        });
        bytes32 sHash = vault.hashApprovalStruct(app);
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", vault.eip712DomainHash(), sHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(roguePk, digest); // Signed with rogue key

        vm.prank(agent);
        try vault.executeBasket(mandateId, app, lines, abi.encodePacked(r, s, v)) {
            revert("CRITICAL: Bad signature basket executed!");
        } catch {
            ghost_failure_badSignature++;
            ghost_totalFailures++;
        }
    }

    // --- ACTION 10: DUPLICATE QUOTE ACROSS BASKETS ---
    function action_duplicateQuoteAcrossBaskets() external {
        if (consumedQuoteIds.length == 0) return;
        bytes32 usedQuote = consumedQuoteIds[0];

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine({
            quoteId: usedQuote,
            vendorId: vendor1Id,
            categoryId: catAi,
            skuId: keccak256("sku-ai"),
            units: 1,
            amount: 100_000
        });
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory app = PolicyVault.Approval({
            mandateId: mandateId,
            approvalId: keccak256(abi.encodePacked("dupq-app", approvalNonce++)),
            basketHash: bHash,
            totalAmount: 100_000,
            deadline: uint64(block.timestamp + 120),
            verifierEpoch: vault.verifierEpoch()
        });
        bytes32 sHash = vault.hashApprovalStruct(app);
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", vault.eip712DomainHash(), sHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(verifierPk, digest);

        vm.prank(agent);
        try vault.executeBasket(mandateId, app, lines, abi.encodePacked(r, s, v)) {
            revert("CRITICAL: Duplicate quote executed!");
        } catch {
            ghost_failure_duplicateQuote++;
            ghost_totalFailures++;
        }
    }

    function consumedApprovalIdsLength() external view returns (uint256) {
        return consumedApprovalIds.length;
    }

    function consumedQuoteIdsLength() external view returns (uint256) {
        return consumedQuoteIds.length;
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
    bytes32 internal vendor2Id = keccak256("tokenforge");
    bytes32 internal catAi = keccak256("AI_CREDITS");
    bytes32 internal catApi = keccak256("API_CALLS");

    function setUp() public {
        owner = vm.addr(ownerPk);
        agent = vm.addr(agentPk);
        verifier = vm.addr(verifierPk);

        usdc = new MockUSDC();
        vault = new PolicyVault(owner, address(usdc), verifier);

        vm.startPrank(owner);
        vault.registerVendor(vendor1Id, address(0x101), address(0x102));
        vault.registerVendor(vendor2Id, address(0x201), address(0x202));
        vm.stopPrank();

        usdc.mint(owner, 100_000_000); // 100 USDC total budget
        vm.prank(owner);
        usdc.approve(address(vault), 100_000_000);

        bytes32[] memory vList = new bytes32[](2);
        vList[0] = vendor1Id;
        vList[1] = vendor2Id;
        bytes32[] memory cList = new bytes32[](2);
        cList[0] = catAi;
        cList[1] = catApi;

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

    /// @notice Invariant 3: on-chain spentTotal equals independent ghost cumulative paid amount
    function invariant_spentTotalEqualsGhostCumulativePaid() public view {
        assertEq(vault.spentTotal(mandateId), handler.ghost_totalPaidCumulative());
    }

    /// @notice Invariant 4: sum of independent vendor payouts reconciles with cumulative paid
    function invariant_vendorPayoutsReconcileWithCumulativeSettlement() public view {
        uint256 sumVendorPayouts = handler.ghost_vendorPayouts(vendor1Id) + handler.ghost_vendorPayouts(vendor2Id);
        assertEq(sumVendorPayouts, handler.ghost_totalPaidCumulative());
    }

    /// @notice Invariant 5: on-chain spentToday reconciles with ghost daily spending for current UTC day
    function invariant_spentTodayReconcilesWithGhostDaily() public view {
        uint256 currentDay = block.timestamp / 1 days;
        assertEq(vault.spentToday(mandateId), handler.ghost_dailyPaid(currentDay));
    }

    /// @notice Invariant 6: every consumed quote and approval is permanently marked on-chain
    function invariant_consumedApprovalsAndQuotesMarkedUsed() public view {
        uint256 quoteCount = handler.consumedQuoteIdsLength();
        if (quoteCount > 0) {
            bytes32 sampleQuote = handler.consumedQuoteIds(quoteCount - 1);
            assertTrue(vault.quoteUsed(sampleQuote), "Consumed quote not marked used on-chain");
        }
        uint256 appCount = handler.consumedApprovalIdsLength();
        if (appCount > 0) {
            bytes32 sampleApp = handler.consumedApprovalIds(appCount - 1);
            assertTrue(vault.approvalUsed(sampleApp), "Consumed approval not marked used on-chain");
        }
    }

    /// @notice Hook called after invariant campaign finishes; asserts ghost successes and failures > 0
    function afterInvariant() public view {
        assertGt(handler.ghost_totalSuccesses(), 0, "No handler actions succeeded");
        assertGt(handler.ghost_totalFailures(), 0, "No handler actions failed/reverted");

        console2.log("=== INVARIANT CAMPAIGN GHOST ACTION COUNTS ===");
        console2.log("Total Ghost Successes:", handler.ghost_totalSuccesses());
        console2.log("Total Ghost Failures: ", handler.ghost_totalFailures());
        console2.log("  - executeBasket:      success=%s, fail=%s", handler.ghost_success_executeBasket(), handler.ghost_failure_executeBasket());
        console2.log("  - revokeMandate:      success=%s, fail=%s", handler.ghost_success_revoke(), handler.ghost_failure_revoke());
        console2.log("  - bumpEpoch:          success=%s, fail=%s", handler.ghost_success_epochBump(), handler.ghost_failure_epochBump());
        console2.log("  - setVerifier:        success=%s, fail=%s", handler.ghost_success_setVerifier(), handler.ghost_failure_setVerifier());
        console2.log("  - timeWarp:           success=%s, fail=%s", handler.ghost_success_timeWarp(), handler.ghost_failure_timeWarp());
        console2.log("  - overCap:            success=%s, fail=%s", handler.ghost_success_overCap(), handler.ghost_failure_overCap());
        console2.log("  - unregisteredVendor: success=%s, fail=%s", handler.ghost_success_unregisteredVendor(), handler.ghost_failure_unregisteredVendor());
        console2.log("  - badSignature:       success=%s, fail=%s", handler.ghost_success_badSignature(), handler.ghost_failure_badSignature());
        console2.log("  - duplicateQuote:     success=%s, fail=%s", handler.ghost_success_duplicateQuote(), handler.ghost_failure_duplicateQuote());
    }
}
