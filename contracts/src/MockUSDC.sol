// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title MockUSDC
 * @notice Test-only ERC-20 token with 6 decimals and open minting for simulation and local Anvil tests.
 */
contract MockUSDC is ERC20 {
    constructor() ERC20("Mock USD Coin", "mUSDC") {}

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    /**
     * @notice Open mint for testing purposes on local test environments.
     */
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
