// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {PolicyVault} from "../src/PolicyVault.sol";
import {MockUSDC} from "../src/MockUSDC.sol";

contract GoldenVectorsScript is Script {
    function run() external {
        address dummyOwner = address(0x1111111111111111111111111111111111111111);
        address dummyAgent = address(0x2222222222222222222222222222222222222222);
        address dummyVerifier = address(0x3333333333333333333333333333333333333333);
        address dummyToken = address(0x4444444444444444444444444444444444444444);

        // Deterministic contract address simulation
        PolicyVault vault = new PolicyVault(dummyOwner, dummyToken, dummyVerifier);

        // Fixed vector Mandate
        bytes32[] memory vendorsList = new bytes32[](2);
        vendorsList[0] = keccak256("nimbusapi");
        vendorsList[1] = keccak256("tokenforge");

        bytes32[] memory categoriesList = new bytes32[](2);
        categoriesList[0] = keccak256("AI_CREDITS");
        categoriesList[1] = keccak256("API_CALLS");

        PolicyVault.Mandate memory m = PolicyVault.Mandate({
            owner: dummyOwner,
            agent: dummyAgent,
            token: dummyToken,
            totalBudget: 100_000_000,
            perPurchaseCap: 40_000_000,
            dailyCap: 60_000_000,
            allowedVendorIds: vendorsList,
            allowedCategoryIds: categoriesList,
            validFrom: 1700000000,
            expiry: 1702592000,
            nonce: 42
        });

        bytes32 mandateStructHash = vault.hashMandateStruct(m);
        bytes32 domainSeparator = vault.domainSeparator();
        bytes32 mandateDigest = keccak256(abi.encodePacked("\x19\x01", domainSeparator, mandateStructHash));

        // Fixed vector BasketLines
        PolicyVault.BasketLine[] memory lines = new PolicyVault.BasketLine[](2);
        lines[0] = PolicyVault.BasketLine({
            quoteId: keccak256("quote-gold-1"),
            vendorId: vendorsList[0],
            categoryId: categoriesList[0],
            skuId: keccak256("sku-gold-1"),
            units: 100,
            amount: 15_000_000
        });
        lines[1] = PolicyVault.BasketLine({
            quoteId: keccak256("quote-gold-2"),
            vendorId: vendorsList[1],
            categoryId: categoriesList[1],
            skuId: keccak256("sku-gold-2"),
            units: 50,
            amount: 12_000_000
        });

        bytes32 line0StructHash = vault.hashBasketLineStruct(lines[0]);
        bytes32 line1StructHash = vault.hashBasketLineStruct(lines[1]);
        bytes32 basketHash = vault.computeBasketHash(lines);

        // Fixed vector Approval
        bytes32 approvalId = keccak256("approval-gold-1");
        PolicyVault.Approval memory a = PolicyVault.Approval({
            mandateId: mandateDigest,
            approvalId: approvalId,
            basketHash: basketHash,
            totalAmount: 27_000_000,
            deadline: 1700000120,
            verifierEpoch: 1
        });

        bytes32 approvalStructHash = vault.hashApprovalStruct(a);
        bytes32 approvalDigest = keccak256(abi.encodePacked("\x19\x01", domainSeparator, approvalStructHash));

        // Construct JSON
        string memory output = string.concat(
            "{\n",
            "  \"domainSeparator\": \"", vm.toString(domainSeparator), "\",\n",
            "  \"mandateStructHash\": \"", vm.toString(mandateStructHash), "\",\n",
            "  \"mandateDigest\": \"", vm.toString(mandateDigest), "\",\n",
            "  \"line0StructHash\": \"", vm.toString(line0StructHash), "\",\n",
            "  \"line1StructHash\": \"", vm.toString(line1StructHash), "\",\n",
            "  \"basketHash\": \"", vm.toString(basketHash), "\",\n",
            "  \"approvalStructHash\": \"", vm.toString(approvalStructHash), "\",\n",
            "  \"approvalDigest\": \"", vm.toString(approvalDigest), "\"\n",
            "}"
        );

        string memory root = vm.projectRoot();
        string memory vectorPath = string.concat(root, "/../backend/tests/vectors/eip712_vectors.json");
        vm.writeFile(vectorPath, output);
    }
}
