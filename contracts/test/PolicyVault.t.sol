// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {PolicyVault} from "../src/PolicyVault.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {FailingToken} from "./mocks/FailingToken.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

contract PolicyVaultTest is Test {
    PolicyVault public vault;
    MockUSDC public usdc;

    uint256 internal ownerPk = 0xA11CE;
    uint256 internal agentPk = 0xB0B;
    uint256 internal verifierPk = 0xCAFE;
    uint256 internal roguePk = 0xDEAD;

    address internal owner;
    address internal agent;
    address internal verifier;
    address internal rogue;

    bytes32 internal vendor1Id = keccak256("nimbusapi");
    bytes32 internal vendor2Id = keccak256("tokenforge");
    bytes32 internal vendorUnregId = keccak256("shadydeals");

    address internal vendor1Payee = address(0x101);
    address internal vendor1Signer = address(0x102);

    address internal vendor2Payee = address(0x201);
    address internal vendor2Signer = address(0x202);

    bytes32 internal catAi = keccak256("AI_CREDITS");
    bytes32 internal catApi = keccak256("API_CALLS");
    bytes32 internal catStorage = keccak256("STORAGE");

    function setUp() public {
        owner = vm.addr(ownerPk);
        agent = vm.addr(agentPk);
        verifier = vm.addr(verifierPk);
        rogue = vm.addr(roguePk);

        usdc = new MockUSDC();
        vault = new PolicyVault(owner, address(usdc), verifier);

        // Register vendors
        vm.startPrank(owner);
        vault.registerVendor(vendor1Id, vendor1Payee, vendor1Signer);
        vault.registerVendor(vendor2Id, vendor2Payee, vendor2Signer);
        vm.stopPrank();

        // Mint and approve tokens for owner
        usdc.mint(owner, 100_000_000); // 100 USDC (6 decimals)
        vm.prank(owner);
        usdc.approve(address(vault), 100_000_000);
    }

    // --- HELPER FUNCTIONS ---

    function _buildStandardMandate(uint256 nonce) internal view returns (PolicyVault.Mandate memory) {
        bytes32[] memory vendorsList = new bytes32[](2);
        vendorsList[0] = vendor1Id;
        vendorsList[1] = vendor2Id;

        bytes32[] memory categoriesList = new bytes32[](2);
        categoriesList[0] = catAi;
        categoriesList[1] = catApi;

        return PolicyVault.Mandate({
            owner: owner,
            agent: agent,
            token: address(usdc),
            totalBudget: 100_000_000,    // 100 USDC
            perPurchaseCap: 40_000_000,   // 40 USDC
            dailyCap: 60_000_000,         // 60 USDC
            allowedVendorIds: vendorsList,
            allowedCategoryIds: categoriesList,
            validFrom: uint64(block.timestamp),
            expiry: uint64(block.timestamp + 30 days),
            nonce: nonce
        });
    }

    function _signMandate(PolicyVault.Mandate memory m, uint256 signerPk) internal view returns (bytes memory) {
        bytes32 structHash = vault.hashMandateStruct(m);
        bytes32 digest = keccak256(
            abi.encodePacked("\x19\x01", vault.eip712DomainHash(), structHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPk, digest);
        return abi.encodePacked(r, s, v);
    }

    function _signApproval(PolicyVault.Approval memory a, uint256 signerPk) internal view returns (bytes memory) {
        bytes32 structHash = vault.hashApprovalStruct(a);
        bytes32 digest = keccak256(
            abi.encodePacked("\x19\x01", vault.eip712DomainHash(), structHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPk, digest);
        return abi.encodePacked(r, s, v);
    }

    // --- HAPPY PATH ---

    function test_HappyPath_ExecuteMultiVendorBasket() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes memory ownerSig = _signMandate(m, ownerPk);
        bytes32 mandateId = vault.createMandate(m, ownerSig);

        // Basket with 2 lines: Vendor 1 ($15) + Vendor 2 ($12) = $27 total
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](2);
        lines[0] = PolicyVault.BasketLine({
            quoteId: keccak256("quote-1"),
            vendorId: vendor1Id,
            categoryId: catAi,
            skuId: keccak256("sku-ai-1"),
            units: 100,
            amount: 15_000_000
        });
        lines[1] = PolicyVault.BasketLine({
            quoteId: keccak256("quote-2"),
            vendorId: vendor2Id,
            categoryId: catApi,
            skuId: keccak256("sku-api-1"),
            units: 50,
            amount: 12_000_000
        });

        bytes32 basketHash = vault.computeBasketHash(lines);
        bytes32 approvalId = keccak256("approval-1");

        PolicyVault.Approval memory approval = PolicyVault.Approval({
            mandateId: mandateId,
            approvalId: approvalId,
            basketHash: basketHash,
            totalAmount: 27_000_000,
            deadline: uint64(block.timestamp + 120),
            verifierEpoch: vault.verifierEpoch()
        });

        bytes memory verifierSig = _signApproval(approval, verifierPk);

        uint256 balOwnerBefore = usdc.balanceOf(owner);
        uint256 balV1Before = usdc.balanceOf(vendor1Payee);
        uint256 balV2Before = usdc.balanceOf(vendor2Payee);

        vm.prank(agent);
        vault.executeBasket(mandateId, approval, lines, verifierSig);

        // Verification of state and balance movements
        assertEq(usdc.balanceOf(owner), balOwnerBefore - 27_000_000);
        assertEq(usdc.balanceOf(vendor1Payee), balV1Before + 15_000_000);
        assertEq(usdc.balanceOf(vendor2Payee), balV2Before + 12_000_000);

        assertEq(vault.spentTotal(mandateId), 27_000_000);
        assertEq(vault.spentToday(mandateId), 27_000_000);
        assertEq(vault.remainingBudget(mandateId), 73_000_000);
        assertTrue(vault.approvalUsed(approvalId));
        assertTrue(vault.quoteUsed(lines[0].quoteId));
        assertTrue(vault.quoteUsed(lines[1].quoteId));
    }

    // --- AUTHORITY REJECTIONS ---

    function test_RevertWhen_UnauthorizedAgentCallsExecute() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(rogue);
        vm.expectRevert(PolicyVault.NotMandateAgent.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_VendorNotRegistered() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendorUnregId, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.VendorNotRegistered.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_CategoryNotAllowed() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catStorage, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.CategoryNotAllowed.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_OwnerSignatureInvalid() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes memory rogueSig = _signMandate(m, roguePk);

        vm.expectRevert(PolicyVault.InvalidOwnerSignature.selector);
        vault.createMandate(m, rogueSig);
    }

    function test_RevertWhen_ApprovalCrossMandateReplay() public {
        PolicyVault.Mandate memory m1 = _buildStandardMandate(0);
        PolicyVault.Mandate memory m2 = _buildStandardMandate(1);

        bytes32 mandate1 = vault.createMandate(m1, _signMandate(m1, ownerPk));
        bytes32 mandate2 = vault.createMandate(m2, _signMandate(m2, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);

        PolicyVault.Approval memory a = PolicyVault.Approval(mandate1, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        // Attempt using approval intended for mandate1 on mandate2
        vm.prank(agent);
        vm.expectRevert(PolicyVault.ApprovalMandateMismatch.selector);
        vault.executeBasket(mandate2, a, lines, sig);
    }

    // --- VERIFIER SIGNATURE REJECTIONS ---

    function test_RevertWhen_BadVerifierSignature() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());

        // Signed with rogue key
        bytes memory badSig = _signApproval(a, roguePk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.BadVerifierSignature.selector);
        vault.executeBasket(mandateId, a, lines, badSig);
    }

    // --- TIME AND STATE REJECTIONS ---

    function test_RevertWhen_ApprovalExpired() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        // Warp past deadline
        vm.warp(block.timestamp + 121);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.ApprovalExpired.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_Revocation_RevokeThenExecuteFails() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        // Owner revokes before agent executes
        vm.prank(owner);
        vault.revokeMandate(mandateId);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.MandateIsRevoked.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_Revocation_ExecuteThenRevokeLeavesPaymentIntact() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        // Payment executes first
        vm.prank(agent);
        vault.executeBasket(mandateId, a, lines, sig);
        assertEq(usdc.balanceOf(vendor1Payee), 1_000_000);

        // Owner revokes after execution
        vm.prank(owner);
        vault.revokeMandate(mandateId);

        // Completed payment remains completed
        assertEq(usdc.balanceOf(vendor1Payee), 1_000_000);
        assertTrue(vault.isRevoked(mandateId));
    }

    function test_RevertWhen_EpochBumpedInvalidatesOutstandingApproval() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        // Owner bumps epoch
        vm.prank(owner);
        vault.bumpVerifierEpoch();

        vm.prank(agent);
        vm.expectRevert(PolicyVault.StaleVerifierEpoch.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_ContractPaused() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(owner);
        vault.pause();

        vm.prank(agent);
        vm.expectRevert(Pausable.EnforcedPause.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    // --- LIMITS AND CAP REJECTIONS ---

    function test_RevertWhen_PerPurchaseCapExceeded() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        // perPurchaseCap is 40 USDC (40_000_000). Try 41 USDC
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 41_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 41_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.PerPurchaseCapExceeded.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_DailyCapExceededAndNextDayRollover() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        // dailyCap is 60 USDC. First purchase: $35 USDC (OK)
        PolicyVault.BasketLine[] memory lines1 = new PolicyVault.BasketLine[](1);
        lines1[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 35_000_000);
        bytes32 bHash1 = vault.computeBasketHash(lines1);
        PolicyVault.Approval memory a1 = PolicyVault.Approval(mandateId, keccak256("app1"), bHash1, 35_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig1 = _signApproval(a1, verifierPk);

        vm.prank(agent);
        vault.executeBasket(mandateId, a1, lines1, sig1);

        // Second purchase on same day: $30 USDC (35 + 30 = 65 > 60 -> DailyCapExceeded)
        PolicyVault.BasketLine[] memory lines2 = new PolicyVault.BasketLine[](1);
        lines2[0] = PolicyVault.BasketLine(keccak256("q2"), vendor1Id, catAi, keccak256("sku2"), 10, 30_000_000);
        bytes32 bHash2 = vault.computeBasketHash(lines2);
        PolicyVault.Approval memory a2 = PolicyVault.Approval(mandateId, keccak256("app2"), bHash2, 30_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig2 = _signApproval(a2, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.DailyCapExceeded.selector);
        vault.executeBasket(mandateId, a2, lines2, sig2);

        // Warp to next UTC day (current timestamp + 1 days)
        uint256 newTime = block.timestamp + 1 days;
        vm.warp(newTime);

        // Sign new approval with fresh deadline
        uint64 nextDeadline = uint64(newTime + 120);
        PolicyVault.Approval memory a2NextDay = PolicyVault.Approval(
            mandateId, keccak256("app2-nextday"), bHash2, 30_000_000, nextDeadline, vault.verifierEpoch()
        );
        bytes memory sig2NextDay = _signApproval(a2NextDay, verifierPk);

        // Now succeeds on next day rollover!
        vm.prank(agent);
        vault.executeBasket(mandateId, a2NextDay, lines2, sig2NextDay);
        assertEq(vault.spentTotal(mandateId), 65_000_000);
    }

    // --- BASKET INTEGRITY & REPLAY REJECTIONS ---

    function test_RevertWhen_ApprovalReplayed() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vault.executeBasket(mandateId, a, lines, sig);

        // Attempt second execution with same approvalId
        vm.prank(agent);
        vm.expectRevert(PolicyVault.ApprovalReplayed.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_DuplicateQuoteIdInBasket() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        // Two lines with same quoteId
        bytes32 sameQuote = keccak256("same-quote");
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](2);
        lines[0] = PolicyVault.BasketLine(sameQuote, vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);
        lines[1] = PolicyVault.BasketLine(sameQuote, vendor1Id, catAi, keccak256("sku2"), 10, 1_000_000);

        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app1"), bHash, 2_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.QuoteAlreadyUsed.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_BasketHashMismatch() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("sku1"), 10, 1_000_000);

        // Approval is signed with a forged/tampered basketHash
        PolicyVault.Approval memory a = PolicyVault.Approval(
            mandateId, keccak256("app1"), keccak256("fakeHash"), 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch()
        );
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.BasketHashMismatch.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    // --- ATOMICITY: FAILING TOKEN TEST ---

    function test_RevertWhen_TransferFailsRollsBackWholeBasket() public {
        FailingToken failToken = new FailingToken();
        PolicyVault failVault = new PolicyVault(owner, address(failToken), verifier);

        vm.startPrank(owner);
        failVault.registerVendor(vendor1Id, vendor1Payee, vendor1Signer);
        failVault.registerVendor(vendor2Id, vendor2Payee, vendor2Signer);
        vm.stopPrank();

        failToken.mint(owner, 100_000_000);
        vm.prank(owner);
        failToken.approve(address(failVault), 100_000_000);

        // Set transfer failure on vendor2Payee
        failToken.setFailingPayee(vendor2Payee);

        // Create mandate for failVault
        bytes32[] memory vList = new bytes32[](2);
        vList[0] = vendor1Id;
        vList[1] = vendor2Id;
        bytes32[] memory cList = new bytes32[](2);
        cList[0] = catAi;
        cList[1] = catApi;

        PolicyVault.Mandate memory m = PolicyVault.Mandate({
            owner: owner,
            agent: agent,
            token: address(failToken),
            totalBudget: 100_000_000,
            perPurchaseCap: 40_000_000,
            dailyCap: 60_000_000,
            allowedVendorIds: vList,
            allowedCategoryIds: cList,
            validFrom: uint64(block.timestamp),
            expiry: uint64(block.timestamp + 30 days),
            nonce: 0
        });

        bytes32 sHash = failVault.hashMandateStruct(m);
        bytes32 mDigest = keccak256(abi.encodePacked("\x19\x01", failVault.eip712DomainHash(), sHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(ownerPk, mDigest);
        bytes32 mandateId = failVault.createMandate(m, abi.encodePacked(r, s, v));

        // Basket where second line goes to vendor2Payee (which reverts)
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](2);
        lines[0] = PolicyVault.BasketLine(keccak256("q1"), vendor1Id, catAi, keccak256("s1"), 10, 10_000_000);
        lines[1] = PolicyVault.BasketLine(keccak256("q2"), vendor2Id, catApi, keccak256("s2"), 10, 10_000_000);

        bytes32 bHash = failVault.computeBasketHash(lines);
        bytes32 appId = keccak256("app-fail");
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, appId, bHash, 20_000_000, uint64(block.timestamp + 120), failVault.verifierEpoch());

        bytes32 aDigest = keccak256(abi.encodePacked("\x19\x01", failVault.eip712DomainHash(), failVault.hashApprovalStruct(a)));
        (uint8 av, bytes32 ar, bytes32 asig) = vm.sign(verifierPk, aDigest);
        bytes memory vSig = abi.encodePacked(ar, asig, av);

        // Entire basket must revert with no partial payment
        vm.prank(agent);
        vm.expectRevert("FailingToken: transfer rejected by simulation");
        failVault.executeBasket(mandateId, a, lines, vSig);

        // Assert atomicity: 0 tokens transferred, 0 spend recorded, approval not used
        assertEq(failToken.balanceOf(vendor1Payee), 0);
        assertEq(failToken.balanceOf(vendor2Payee), 0);
        assertEq(failVault.spentTotal(mandateId), 0);
        assertFalse(failVault.approvalUsed(appId));
        assertFalse(failVault.quoteUsed(lines[0].quoteId));
    }

    // --- ADMINISTRATION ---

    function test_RevertWhen_NonOwnerCallsAdminFunctions() public {
        vm.startPrank(rogue);

        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, rogue));
        vault.registerVendor(keccak256("v"), address(0x99), address(0x99));

        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, rogue));
        vault.setVerifier(rogue);

        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, rogue));
        vault.bumpVerifierEpoch();

        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, rogue));
        vault.pause();

        vm.stopPrank();
    }

    // --- ADDITIONAL SECTION 7.7 / 7.8 SECURITY & EDGE CASE TESTS ---

    function test_RevertWhen_CompromisedVerifierSignsPolicyViolatingBasket() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        // perPurchaseCap is 40 USDC (40_000_000). Rogue/compromised verifier signs for 50 USDC.
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-violate"), vendor1Id, catAi, keccak256("sku-ai"), 10, 50_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-violate"), bHash, 50_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        // Valid signature from real verifier key
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.PerPurchaseCapExceeded.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_TotalMismatch() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-mismatch"), vendor1Id, catAi, keccak256("sku-ai"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        // Approval total states 2_000_000 but line total is 1_000_000
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-mismatch"), bHash, 2_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.TotalMismatch.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_EmptyBasket() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](0);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-empty"), bHash, 0, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.EmptyBasket.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_TooManyLines() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        // Max is 16 lines; create 17 lines
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](17);
        for (uint256 i = 0; i < 17; i++) {
            lines[i] = PolicyVault.BasketLine(
                keccak256(abi.encodePacked("line-quote", i)),
                vendor1Id,
                catAi,
                keccak256("sku-ai"),
                1,
                100_000
            );
        }
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-too-many"), bHash, 1_700_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.TooManyLines.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_MandateExpired() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-exp"), vendor1Id, catAi, keccak256("sku-ai"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-exp"), bHash, 1_000_000, uint64(block.timestamp + 31 days + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        // Warp past mandate expiry (m.expiry is block.timestamp + 30 days)
        vm.warp(block.timestamp + 31 days);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.MandateExpired.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_MandateNotYetValid() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        m.validFrom = uint64(block.timestamp + 5 days);
        m.expiry = uint64(block.timestamp + 35 days);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-early"), vendor1Id, catAi, keccak256("sku-ai"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-early"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.MandateNotYetValid.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_SignatureForDifferentChainIdOrContract() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-crosschain"), vendor1Id, catAi, keccak256("sku-ai"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-crosschain"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());

        // Construct fake domain with different chainId (999999)
        bytes32 fakeDomain = keccak256(
            abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256(bytes("AgentVault")),
                keccak256(bytes("1")),
                uint256(999999),
                address(vault)
            )
        );
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", fakeDomain, vault.hashApprovalStruct(a)));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(verifierPk, digest);
        bytes memory sig = abi.encodePacked(r, s, v);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.BadVerifierSignature.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_VendorInactive() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        // Owner marks vendor1 inactive
        vm.prank(owner);
        vault.setVendorActive(vendor1Id, false);

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-inactive"), vendor1Id, catAi, keccak256("sku-ai"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-inactive"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.VendorNotRegistered.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_SetVerifierInvalidatesOutstandingApproval() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-setver"), vendor1Id, catAi, keccak256("sku-ai"), 10, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-setver"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        // Owner sets new verifier, which automatically bumps verifierEpoch
        address newVerifier = address(0xCAFEBABE);
        vm.prank(owner);
        vault.setVerifier(newVerifier);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.StaleVerifierEpoch.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_AggregateBudgetExceeded() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        // First purchase: $35 USDC on Day 1
        PolicyVault.BasketLine[] memory lines1 = new PolicyVault.BasketLine[](1);
        lines1[0] = PolicyVault.BasketLine(keccak256("q-b1"), vendor1Id, catAi, keccak256("sku1"), 10, 35_000_000);
        bytes32 bHash1 = vault.computeBasketHash(lines1);
        PolicyVault.Approval memory a1 = PolicyVault.Approval(mandateId, keccak256("app-b1"), bHash1, 35_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig1 = _signApproval(a1, verifierPk);
        vm.prank(agent);
        vault.executeBasket(mandateId, a1, lines1, sig1);

        // Warp to Day 2, purchase $35 USDC (cumulative $70 USDC)
        uint256 timeDay2 = block.timestamp + 1 days;
        vm.warp(timeDay2);
        PolicyVault.BasketLine[] memory lines2 = new PolicyVault.BasketLine[](1);
        lines2[0] = PolicyVault.BasketLine(keccak256("q-b2"), vendor1Id, catAi, keccak256("sku2"), 10, 35_000_000);
        bytes32 bHash2 = vault.computeBasketHash(lines2);
        PolicyVault.Approval memory a2 = PolicyVault.Approval(mandateId, keccak256("app-b2"), bHash2, 35_000_000, uint64(timeDay2 + 120), vault.verifierEpoch());
        bytes memory sig2 = _signApproval(a2, verifierPk);
        vm.prank(agent);
        vault.executeBasket(mandateId, a2, lines2, sig2);

        // Warp to Day 3, attempt $35 USDC (70 + 35 = 105 > 100 totalBudget -> BudgetExceeded)
        uint256 timeDay3 = timeDay2 + 1 days;
        vm.warp(timeDay3);
        PolicyVault.BasketLine[] memory lines3 = new PolicyVault.BasketLine[](1);
        lines3[0] = PolicyVault.BasketLine(keccak256("q-b3"), vendor1Id, catAi, keccak256("sku3"), 10, 35_000_000);
        bytes32 bHash3 = vault.computeBasketHash(lines3);
        PolicyVault.Approval memory a3 = PolicyVault.Approval(mandateId, keccak256("app-b3"), bHash3, 35_000_000, uint64(timeDay3 + 120), vault.verifierEpoch());
        bytes memory sig3 = _signApproval(a3, verifierPk);
        vm.prank(agent);
        vm.expectRevert(PolicyVault.BudgetExceeded.selector);
        vault.executeBasket(mandateId, a3, lines3, sig3);
    }

    function test_RevertWhen_VendorRegisteredButNotAllowlisted() public {
        bytes32 vendor3Id = keccak256("vendor3");
        vm.prank(owner);
        vault.registerVendor(vendor3Id, address(0x301), address(0x302));

        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-v3"), vendor3Id, catAi, keccak256("sku"), 1, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-v3"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        vm.expectRevert(PolicyVault.VendorNotAllowed.selector);
        vault.executeBasket(mandateId, a, lines, sig);
    }

    function test_RevertWhen_QuoteAlreadyUsedAcrossBaskets() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        bytes32 quoteId = keccak256("shared-quote-id");

        // Basket 1 uses quoteId
        PolicyVault.BasketLine[] memory lines1 = new PolicyVault.BasketLine[](1);
        lines1[0] = PolicyVault.BasketLine(quoteId, vendor1Id, catAi, keccak256("sku1"), 1, 1_000_000);
        bytes32 bHash1 = vault.computeBasketHash(lines1);
        PolicyVault.Approval memory a1 = PolicyVault.Approval(mandateId, keccak256("app-q1"), bHash1, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig1 = _signApproval(a1, verifierPk);
        vm.prank(agent);
        vault.executeBasket(mandateId, a1, lines1, sig1);

        // Basket 2 reuses the same quoteId
        PolicyVault.BasketLine[] memory lines2 = new PolicyVault.BasketLine[](1);
        lines2[0] = PolicyVault.BasketLine(quoteId, vendor1Id, catAi, keccak256("sku2"), 1, 1_000_000);
        bytes32 bHash2 = vault.computeBasketHash(lines2);
        PolicyVault.Approval memory a2 = PolicyVault.Approval(mandateId, keccak256("app-q2"), bHash2, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig2 = _signApproval(a2, verifierPk);
        vm.prank(agent);
        vm.expectRevert(PolicyVault.QuoteAlreadyUsed.selector);
        vault.executeBasket(mandateId, a2, lines2, sig2);
    }

    function test_RevertWhen_EmptyVerifierSignature() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-empty-sig"), vendor1Id, catAi, keccak256("sku"), 1, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-empty-sig"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());

        vm.prank(agent);
        vm.expectRevert(PolicyVault.BadVerifierSignature.selector);
        vault.executeBasket(mandateId, a, lines, "");
    }

    function test_RevertWhen_ShortVerifierSignature() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        bytes32 mandateId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256("q-short-sig"), vendor1Id, catAi, keccak256("sku"), 1, 1_000_000);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mandateId, keccak256("app-short-sig"), bHash, 1_000_000, uint64(block.timestamp + 120), vault.verifierEpoch());

        vm.prank(agent);
        vm.expectRevert(PolicyVault.BadVerifierSignature.selector);
        vault.executeBasket(mandateId, a, lines, hex"12345678");
    }

    function test_RevertWhen_TokenMismatch() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        m.token = address(0xDEADBEEF);
        bytes memory sig = _signMandate(m, ownerPk);
        vm.expectRevert(PolicyVault.TokenMismatch.selector);
        vault.createMandate(m, sig);
    }

    function test_RevertWhen_NonceReused() public {
        PolicyVault.Mandate memory m1 = _buildStandardMandate(42);
        vault.createMandate(m1, _signMandate(m1, ownerPk));

        PolicyVault.Mandate memory m2 = _buildStandardMandate(42);
        m2.totalBudget = 50_000_000;
        bytes memory sig2 = _signMandate(m2, ownerPk);
        vm.expectRevert(PolicyVault.NonceUsed.selector);
        vault.createMandate(m2, sig2);
    }

    function test_RevertWhen_ZeroBudget() public {
        PolicyVault.Mandate memory m = _buildStandardMandate(0);
        m.totalBudget = 0;
        bytes memory sig = _signMandate(m, ownerPk);
        vm.expectRevert(PolicyVault.InvalidMandate.selector);
        vault.createMandate(m, sig);
    }

    function test_RevertWhen_EmptyAllowlist() public {
        PolicyVault.Mandate memory m1 = _buildStandardMandate(0);
        m1.allowedVendorIds = new bytes32[](0);
        bytes memory sig1 = _signMandate(m1, ownerPk);
        vm.expectRevert(PolicyVault.InvalidMandate.selector);
        vault.createMandate(m1, sig1);

        PolicyVault.Mandate memory m2 = _buildStandardMandate(1);
        m2.allowedCategoryIds = new bytes32[](0);
        bytes memory sig2 = _signMandate(m2, ownerPk);
        vm.expectRevert(PolicyVault.InvalidMandate.selector);
        vault.createMandate(m2, sig2);
    }

    function testFuzz_RandomCapsAndBaskets(
        uint256 rawBudget,
        uint256 rawPerCap,
        uint256 rawDailyCap,
        uint256 rawAmount
    ) public {
        uint256 budget = bound(rawBudget, 1_000_000, 100_000_000);
        uint256 perCap = bound(rawPerCap, 1, budget);
        uint256 dailyCap = bound(rawDailyCap, 1, budget);
        uint256 amount = bound(rawAmount, 1, budget * 2);

        usdc.mint(owner, budget);
        vm.prank(owner);
        usdc.approve(address(vault), type(uint256).max);

        bytes32[] memory vList = new bytes32[](1);
        vList[0] = vendor1Id;
        bytes32[] memory cList = new bytes32[](1);
        cList[0] = catAi;

        PolicyVault.Mandate memory m = PolicyVault.Mandate({
            owner: owner,
            agent: agent,
            token: address(usdc),
            totalBudget: budget,
            perPurchaseCap: perCap,
            dailyCap: dailyCap,
            allowedVendorIds: vList,
            allowedCategoryIds: cList,
            validFrom: uint64(block.timestamp),
            expiry: uint64(block.timestamp + 30 days),
            nonce: 99999 + (budget % 100000)
        });

        bytes32 mId = vault.createMandate(m, _signMandate(m, ownerPk));

        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](1);
        lines[0] = PolicyVault.BasketLine(keccak256(abi.encodePacked("fuzz-q", budget, amount)), vendor1Id, catAi, keccak256("sku"), 1, amount);
        bytes32 bHash = vault.computeBasketHash(lines);
        PolicyVault.Approval memory a = PolicyVault.Approval(mId, keccak256(abi.encodePacked("fuzz-app", budget, amount)), bHash, amount, uint64(block.timestamp + 120), vault.verifierEpoch());
        bytes memory sig = _signApproval(a, verifierPk);

        vm.prank(agent);
        if (amount > perCap) {
            vm.expectRevert(PolicyVault.PerPurchaseCapExceeded.selector);
            vault.executeBasket(mId, a, lines, sig);
        } else if (amount > budget) {
            vm.expectRevert(PolicyVault.BudgetExceeded.selector);
            vault.executeBasket(mId, a, lines, sig);
        } else if (amount > dailyCap) {
            vm.expectRevert(PolicyVault.DailyCapExceeded.selector);
            vault.executeBasket(mId, a, lines, sig);
        } else {
            vault.executeBasket(mId, a, lines, sig);
            assertEq(vault.spentTotal(mId), amount);
            assertEq(vault.spentToday(mId), amount);
        }
    }
}
