"""Chain client with Web3, nonce management, and custom error decoding."""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from web3 import Web3
from web3.exceptions import ContractCustomError, ContractLogicError
from eth_account import Account
from eth_utils import to_checksum_address, to_hex

from backend.app.chain.errors import decode_custom_error

FORBIDDEN_MAINNET_CHAINS = {1, 10, 56, 137, 8453, 42161, 43114}


class ChainClient:
    def __init__(
        self,
        rpc_url: str = "http://127.0.0.1:8545",
        expected_chain_id: int = 31337,
        allow_public_testnet: bool = False,
        deployments_path: Optional[str] = None,
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC at {rpc_url}")

        actual_chain_id = self.w3.eth.chain_id
        if actual_chain_id in FORBIDDEN_MAINNET_CHAINS:
            raise ValueError(f"CRITICAL: Mainnet chain ID {actual_chain_id} is strictly forbidden!")

        if actual_chain_id != expected_chain_id and not allow_public_testnet:
            raise ValueError(
                f"Chain ID mismatch: expected {expected_chain_id}, got {actual_chain_id}. "
                f"Set ALLOW_PUBLIC_TESTNET=true to permit other testnets."
            )

        self.chain_id = actual_chain_id

        # Load deployments
        if not deployments_path:
            deployments_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "deployments", "local.json"
            )

        self.deployments_path = deployments_path
        self.deployments = {}
        if os.path.exists(deployments_path):
            with open(deployments_path, "r") as f:
                self.deployments = json.load(f)

        # Load ABIs from contracts/out
        contracts_out = os.path.join(os.path.dirname(__file__), "..", "..", "..", "contracts", "out")
        vault_artifact = os.path.join(contracts_out, "PolicyVault.sol", "PolicyVault.json")
        usdc_artifact = os.path.join(contracts_out, "MockUSDC.sol", "MockUSDC.json")

        self.vault_abi = []
        if os.path.exists(vault_artifact):
            with open(vault_artifact, "r") as f:
                self.vault_abi = json.load(f).get("abi", [])

        self.usdc_abi = []
        if os.path.exists(usdc_artifact):
            with open(usdc_artifact, "r") as f:
                self.usdc_abi = json.load(f).get("abi", [])

        self.vault_address = self.deployments.get("policyVault")
        self.usdc_address = self.deployments.get("mockUsdc")

        self.vault = (
            self.w3.eth.contract(address=to_checksum_address(self.vault_address), abi=self.vault_abi)
            if self.vault_address
            else None
        )
        self.usdc = (
            self.w3.eth.contract(address=to_checksum_address(self.usdc_address), abi=self.usdc_abi)
            if self.usdc_address
            else None
        )

    def reload_deployments(self):
        """Reload contract addresses after deployment."""
        if os.path.exists(self.deployments_path):
            with open(self.deployments_path, "r") as f:
                self.deployments = json.load(f)
            self.vault_address = self.deployments.get("policyVault")
            self.usdc_address = self.deployments.get("mockUsdc")
            if self.vault_address:
                self.vault = self.w3.eth.contract(
                    address=to_checksum_address(self.vault_address), abi=self.vault_abi
                )
            if self.usdc_address:
                self.usdc = self.w3.eth.contract(
                    address=to_checksum_address(self.usdc_address), abi=self.usdc_abi
                )

    def get_block_timestamp(self) -> int:
        """Get latest block timestamp from local chain."""
        return self.w3.eth.get_block("latest")["timestamp"]

    def get_token_balance(self, account: str) -> int:
        """Return token balance in micro-units."""
        if not self.usdc:
            return 0
        return self.usdc.functions.balanceOf(to_checksum_address(account)).call()

    def get_token_allowance(self, owner: str, spender: str) -> int:
        """Return token allowance in micro-units."""
        if not self.usdc:
            return 0
        return self.usdc.functions.allowance(
            to_checksum_address(owner), to_checksum_address(spender)
        ).call()

    def send_tx(self, txn_dict: Dict[str, Any], private_key: str) -> Tuple[str, Dict[str, Any]]:
        """Sign and broadcast transaction with explicit nonce, returning tx_hash and receipt."""
        account = Account.from_key(private_key)
        sender = account.address

        if "from" not in txn_dict:
            txn_dict["from"] = sender
        if "nonce" not in txn_dict:
            txn_dict["nonce"] = self.w3.eth.get_transaction_count(sender, "pending")
        if "chainId" not in txn_dict:
            txn_dict["chainId"] = self.chain_id

        # Estimate gas or fallback
        if "gas" not in txn_dict:
            try:
                txn_dict["gas"] = self.w3.eth.estimate_gas(txn_dict) + 50000
            except Exception:
                txn_dict["gas"] = 2_000_000

        if "gasPrice" not in txn_dict and "maxFeePerGas" not in txn_dict:
            txn_dict["gasPrice"] = self.w3.eth.gas_price

        signed = self.w3.eth.account.sign_transaction(txn_dict, private_key=private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex(), receipt

    def create_mandate(
        self,
        mandate: Dict[str, Any],
        owner_sig_hex: str,
        relayer_private_key: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """Relay createMandate call to PolicyVault."""
        if not self.vault:
            raise ValueError("Vault contract not configured")

        sig_bytes = bytes.fromhex(
            owner_sig_hex[2:] if owner_sig_hex.startswith("0x") else owner_sig_hex
        )

        mandate_tuple = (
            to_checksum_address(mandate["owner"]),
            to_checksum_address(mandate["agent"]),
            to_checksum_address(mandate["token"]),
            int(mandate["totalBudget"]),
            int(mandate["perPurchaseCap"]),
            int(mandate["dailyCap"]),
            [bytes.fromhex(v[2:] if v.startswith("0x") else v) for v in mandate["allowedVendorIds"]],
            [bytes.fromhex(c[2:] if c.startswith("0x") else c) for c in mandate["allowedCategoryIds"]],
            int(mandate["validFrom"]),
            int(mandate["expiry"]),
            int(mandate["nonce"]),
        )

        account = Account.from_key(relayer_private_key)
        txn = self.vault.functions.createMandate(mandate_tuple, sig_bytes).build_transaction(
            {"from": account.address}
        )
        return self.send_tx(txn, relayer_private_key)

    def execute_basket(
        self,
        mandate_id_hex: str,
        approval: Dict[str, Any],
        lines: List[Dict[str, Any]],
        verifier_sig_hex: str,
        agent_private_key: str,
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """Simulate and execute executeBasket. Returns (success, tx_hash, receipt, error_code)."""
        if not self.vault:
            raise ValueError("Vault contract not configured")

        mandate_id_bytes = bytes.fromhex(
            mandate_id_hex[2:] if mandate_id_hex.startswith("0x") else mandate_id_hex
        )
        verifier_sig_bytes = bytes.fromhex(
            verifier_sig_hex[2:] if verifier_sig_hex.startswith("0x") else verifier_sig_hex
        )

        approval_tuple = (
            bytes.fromhex(approval["mandateId"][2:] if approval["mandateId"].startswith("0x") else approval["mandateId"]),
            bytes.fromhex(approval["approvalId"][2:] if approval["approvalId"].startswith("0x") else approval["approvalId"]),
            bytes.fromhex(approval["basketHash"][2:] if approval["basketHash"].startswith("0x") else approval["basketHash"]),
            int(approval["totalAmount"]),
            int(approval["deadline"]),
            int(approval["verifierEpoch"]),
        )

        lines_tuples = [
            (
                bytes.fromhex(l["quoteId"][2:] if l["quoteId"].startswith("0x") else l["quoteId"]),
                bytes.fromhex(l["vendorId"][2:] if l["vendorId"].startswith("0x") else l["vendorId"]),
                bytes.fromhex(l["categoryId"][2:] if l["categoryId"].startswith("0x") else l["categoryId"]),
                bytes.fromhex(l["skuId"][2:] if l["skuId"].startswith("0x") else l["skuId"]),
                int(l["units"]),
                int(l["amount"]),
            )
            for l in lines
        ]

        agent_account = Account.from_key(agent_private_key)
        fn = self.vault.functions.executeBasket(
            mandate_id_bytes, approval_tuple, lines_tuples, verifier_sig_bytes
        )

        # Pre-flight eth_call to decode custom error if reverting
        try:
            fn.call({"from": agent_account.address})
        except Exception as e:
            err_str = str(e)
            decoded = "UnknownRevert"
            # 1. Inspect e.args for 0x selector
            for arg in getattr(e, "args", []):
                if isinstance(arg, str) and arg.startswith("0x") and len(arg) >= 10:
                    decoded = decode_custom_error(arg)
                    break
            # 2. Search regex across err_str
            if decoded.startswith("UnknownRevert"):
                import re
                match = re.search(r"0x[0-9a-fA-F]{8,}", err_str)
                if match:
                    decoded = decode_custom_error(match.group(0))
            if decoded.startswith("UnknownRevert") and "execution reverted:" in err_str:
                decoded = err_str.split("execution reverted:")[-1].strip()
            return False, None, None, decoded

        # Broadcast transaction
        txn = fn.build_transaction({"from": agent_account.address})
        tx_hash, receipt = self.send_tx(txn, agent_private_key)

        if receipt["status"] == 1:
            return True, tx_hash, receipt, None
        else:
            return False, tx_hash, receipt, "TransactionReverted"

    def revoke_mandate(self, mandate_id_hex: str, owner_private_key: str) -> Tuple[str, Dict[str, Any]]:
        """Owner revokes mandate."""
        mandate_id_bytes = bytes.fromhex(
            mandate_id_hex[2:] if mandate_id_hex.startswith("0x") else mandate_id_hex
        )
        account = Account.from_key(owner_private_key)
        txn = self.vault.functions.revokeMandate(mandate_id_bytes).build_transaction(
            {"from": account.address}
        )
        return self.send_tx(txn, owner_private_key)

    def pause(self, owner_private_key: str) -> Tuple[str, Dict[str, Any]]:
        account = Account.from_key(owner_private_key)
        txn = self.vault.functions.pause().build_transaction({"from": account.address})
        return self.send_tx(txn, owner_private_key)

    def unpause(self, owner_private_key: str) -> Tuple[str, Dict[str, Any]]:
        account = Account.from_key(owner_private_key)
        txn = self.vault.functions.unpause().build_transaction({"from": account.address})
        return self.send_tx(txn, owner_private_key)

    def bump_verifier_epoch(self, owner_private_key: str) -> Tuple[str, Dict[str, Any]]:
        account = Account.from_key(owner_private_key)
        txn = self.vault.functions.bumpVerifierEpoch().build_transaction({"from": account.address})
        return self.send_tx(txn, owner_private_key)

    def get_mandate(self, mandate_id_hex: str) -> Optional[Dict[str, Any]]:
        """Query mandate state from PolicyVault."""
        if not self.vault:
            return None
        try:
            m_bytes = bytes.fromhex(
                mandate_id_hex[2:] if mandate_id_hex.startswith("0x") else mandate_id_hex
            )
            raw = self.vault.functions.getMandate(m_bytes).call()
            if raw[0] == "0x0000000000000000000000000000000000000000":
                return None
            revoked = self.vault.functions.isRevoked(m_bytes).call()
            spent_total = self.vault.functions.spentTotal(m_bytes).call()
            spent_today = self.vault.functions.spentToday(m_bytes).call()
            return {
                "owner": raw[0],
                "creator": raw[0],
                "agent": raw[1],
                "token": raw[2],
                "totalBudget": raw[3],
                "perPurchaseCap": raw[4],
                "dailyCap": raw[5],
                "allowedVendorIds": ["0x" + (v.hex() if isinstance(v, bytes) else (v[2:] if v.startswith("0x") else v)) for v in raw[6]],
                "allowedCategoryIds": ["0x" + (c.hex() if isinstance(c, bytes) else (c[2:] if c.startswith("0x") else c)) for c in raw[7]],
                "validFrom": raw[8],
                "expiry": raw[9],
                "nonce": raw[10],
                "spentTotal": spent_total,
                "spentToday": spent_today,
                "revoked": revoked,
            }
        except Exception:
            return None

