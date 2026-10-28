// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title FailingToken
 * @notice Test double ERC-20 token that simulates transfer failure to a specific recipient address
 *         to verify atomic rollback in PolicyVault.executeBasket.
 */
contract FailingToken is ERC20 {
    address public failingPayee;

    constructor() ERC20("Failing Token", "FAIL") {}

    function setFailingPayee(address payee) external {
        failingPayee = payee;
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }

    function transferFrom(address from, address to, uint256 amount) public override returns (bool) {
        if (to == failingPayee) {
            revert("FailingToken: transfer rejected by simulation");
        }
        return super.transferFrom(from, to, amount);
    }
}
