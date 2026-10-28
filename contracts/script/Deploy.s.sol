// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {PolicyVault} from "../src/PolicyVault.sol";

contract DeployScript is Script {
    string[] internal vendorNames = [
        "nimbusapi",
        "tokenforge",
        "vaultstore",
        "budgetbyte",
        "shadydeals"
    ];

    function run() external {
        string memory seed = vm.envOr("VENDOR_KEY_SEED", string("agentvault-test-seed"));
        uint256 deployerPk = vm.envOr(
            "OWNER_PRIVATE_KEY",
            uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80) // Anvil account 0
        );
        address owner = vm.addr(deployerPk);

        address verifier = vm.envOr(
            "VERIFIER_ADDRESS",
            vm.addr(0x5de4111afa1a4b94908f83103eb2173f1a0977e4c20eddd7feed9e018e5197ff) // Anvil account 2
        );

        vm.startBroadcast(deployerPk);

        MockUSDC usdc = new MockUSDC();
        PolicyVault vault = new PolicyVault(owner, address(usdc), verifier);

        // Register 5 vendors
        string memory jsonVendors = "{";
        for (uint256 i = 0; i < vendorNames.length; i++) {
            string memory vName = vendorNames[i];
            bytes32 vId = keccak256(bytes(vName));

            uint256 payeePk = uint256(keccak256(abi.encodePacked(seed, vName, "payee")));
            uint256 signerPk = uint256(keccak256(abi.encodePacked(seed, vName, "signer")));

            address payee = vm.addr(payeePk);
            address signer = vm.addr(signerPk);

            vault.registerVendor(vId, payee, signer);

            string memory entry = string.concat(
                "\"", vName, "\": {",
                "\"vendorId\": \"", vm.toString(vId), "\",",
                "\"payee\": \"", vm.toString(payee), "\",",
                "\"quoteSigner\": \"", vm.toString(signer), "\",",
                "\"active\": true}"
            );

            if (i > 0) {
                jsonVendors = string.concat(jsonVendors, ",", entry);
            } else {
                jsonVendors = string.concat(jsonVendors, entry);
            }
        }
        jsonVendors = string.concat(jsonVendors, "}");

        // Mint test USDC to owner (10,000 USDC = 10_000_000_000 micro-USDC)
        usdc.mint(owner, 10_000_000_000);

        vm.stopBroadcast();

        // Write deployments/local.json
        string memory output = string.concat(
            "{",
            "\"chainId\": ", vm.toString(block.chainid), ",",
            "\"deployBlock\": ", vm.toString(block.number), ",",
            "\"mockUsdc\": \"", vm.toString(address(usdc)), "\",",
            "\"policyVault\": \"", vm.toString(address(vault)), "\",",
            "\"owner\": \"", vm.toString(owner), "\",",
            "\"verifier\": \"", vm.toString(verifier), "\",",
            "\"vendors\": ", jsonVendors,
            "}"
        );

        string memory root = vm.projectRoot();
        string memory deployPath = string.concat(root, "/../deployments/local.json");
        vm.writeFile(deployPath, output);

        console2.log("Deployment complete.");
        console2.log("MockUSDC:", address(usdc));
        console2.log("PolicyVault:", address(vault));
        console2.log("Deployments written to:", deployPath);
    }
}
