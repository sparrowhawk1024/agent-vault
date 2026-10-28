"""Phase 1 Gate Execution Script.

Deploys MockUSDC & PolicyVault to local Anvil node.
Executes an authorized multi-vendor payment end-to-end.
Attempts an unauthorized payment and verifies rejection.
Saves proof artifact to evidence/runs/phase1_gate.json.
"""

import os
import sys
import time
import json
import subprocess
from eth_utils import keccak, to_hex
from eth_account import Account

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.chain.typed_data import (
    hash_mandate_struct,
    compute_eip712_digest,
    sign_eip712_digest,
    build_domain_separator,
)
from backend.app.chain.client import ChainClient
from backend.app.verifier.service import VerifierService


def main():
    print("=== STARTING PHASE 1 RELEASE GATE ===")
    os.makedirs("deployments", exist_ok=True)
    os.makedirs("evidence/runs", exist_ok=True)

    # 1. Start Anvil node
    print("\n[1/6] Launching local Anvil node (chain-id 31337, block-time 1s)...")
    anvil_bin = r"C:\Users\premc\.foundry\bin\anvil.exe"
    anvil_proc = subprocess.Popen(
        [anvil_bin, "--chain-id", "31337", "--block-time", "1", "--port", "8545"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    try:
        # 2. Deploy contracts via Deploy.s.sol
        print("[2/6] Running forge deploy script to deploy MockUSDC and PolicyVault...")
        forge_bin = r"C:\Users\premc\.foundry\bin\forge.exe"
        cmd = [
            forge_bin,
            "script",
            "script/Deploy.s.sol",
            "--rpc-url",
            "http://127.0.0.1:8545",
            "--broadcast",
        ]
        ret = subprocess.run(cmd, cwd="contracts", capture_output=True, text=True)
        if ret.returncode != 0:
            print("Deploy failed:\n", ret.stderr)
            raise RuntimeError(f"Deploy script failed: {ret.stderr}")

        print("Contracts deployed successfully!")

        # 3. Initialize ChainClient and VerifierService
        print("[3/6] Initializing ChainClient and VerifierService...")
        chain = ChainClient(rpc_url="http://127.0.0.1:8545", expected_chain_id=31337)
        chain.reload_deployments()

        deployments = chain.deployments
        vault_addr = deployments["policyVault"]
        usdc_addr = deployments["mockUsdc"]
        print(f"PolicyVault: {vault_addr}")
        print(f"MockUSDC: {usdc_addr}")

        # Anvil standard accounts
        # Account 0: Owner (0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80)
        owner_pk = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        owner_addr = Account.from_key(owner_pk).address

        # Account 1: Agent (0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d)
        agent_pk = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
        agent_addr = Account.from_key(agent_pk).address

        # Account 2: Verifier (0x5de4111afa1a4b94908f83103eb2173f1a0977e4c20eddd7feed9e018e5197ff)
        verifier_pk = "0x5de4111afa1a4b94908f83103eb2173f1a0977e4c20eddd7feed9e018e5197ff"
        verifier = VerifierService(verifier_private_key=verifier_pk, chain_client=chain)

        # 4. Create Mandate on-chain & approve allowance
        print("[4/6] Creating on-chain Mandate and setting owner allowance...")
        v1_id = to_hex(keccak(text="nimbusapi"))
        v2_id = to_hex(keccak(text="tokenforge"))
        cat_ai = to_hex(keccak(text="AI_CREDITS"))
        cat_api = to_hex(keccak(text="API_CALLS"))

        chain_time = chain.get_block_timestamp()
        mandate_dict = {
            "owner": owner_addr,
            "agent": agent_addr,
            "token": usdc_addr,
            "totalBudget": 100_000_000,    # 100 USDC
            "perPurchaseCap": 40_000_000,   # 40 USDC
            "dailyCap": 60_000_000,         # 60 USDC
            "allowedVendorIds": [v1_id, v2_id],
            "allowedCategoryIds": [cat_ai, cat_api],
            "validFrom": chain_time,
            "expiry": chain_time + 30 * 86400,
            "nonce": 1,
        }

        domain_sep = chain.vault.functions.domainSeparator().call()
        m_struct_hash = hash_mandate_struct(mandate_dict)
        mandate_digest = compute_eip712_digest(domain_sep, m_struct_hash)
        mandate_id = to_hex(mandate_digest)
        owner_sig = sign_eip712_digest(mandate_digest, owner_pk)

        create_tx, receipt = chain.create_mandate(mandate_dict, owner_sig, owner_pk)
        print(f"Mandate created! ID: {mandate_id}, Tx: {create_tx}")

        # Owner approves Vault to spend totalBudget (never max uint as per §7.6)
        approve_txn = chain.usdc.functions.approve(vault_addr, 100_000_000).build_transaction(
            {"from": owner_addr}
        )
        chain.send_tx(approve_txn, owner_pk)
        print("Owner approved Vault allowance of 100 USDC.")

        # 5. Execute Authorized Multi-Vendor Basket
        print("\n[5/6] Executing Authorized Multi-Vendor Basket on local Anvil...")
        lines = [
            {
                "quoteId": to_hex(keccak(text="quote-anvil-1")),
                "vendorId": v1_id,
                "categoryId": cat_ai,
                "skuId": to_hex(keccak(text="sku-anvil-ai")),
                "units": 100,
                "amount": 15_000_000,  # 15 USDC
            },
            {
                "quoteId": to_hex(keccak(text="quote-anvil-2")),
                "vendorId": v2_id,
                "categoryId": cat_api,
                "skuId": to_hex(keccak(text="sku-anvil-api")),
                "units": 50,
                "amount": 12_000_000,  # 12 USDC
            },
        ]
        claimed_total = 27_000_000  # 27 USDC

        v1_payee = deployments["vendors"]["nimbusapi"]["payee"]
        v2_payee = deployments["vendors"]["tokenforge"]["payee"]

        bal_owner_before = chain.get_token_balance(owner_addr)
        bal_v1_before = chain.get_token_balance(v1_payee)
        bal_v2_before = chain.get_token_balance(v2_payee)

        approved, approval_data, verifier_sig, decision = verifier.verify_and_approve(
            mandate_id=mandate_id,
            request_id="req-anvil-001",
            lines=lines,
            claimed_total=claimed_total,
            agent_address=agent_addr,
        )
        assert approved, f"Verifier rejected: {decision}"
        print(f"Verifier approved basket! Approval ID: {approval_data['approvalId']}")

        success, tx_hash, exec_receipt, err = chain.execute_basket(
            mandate_id_hex=mandate_id,
            approval=approval_data,
            lines=lines,
            verifier_sig_hex=verifier_sig,
            agent_private_key=agent_pk,
        )
        assert success, f"executeBasket failed: {err}"
        print(f"executeBasket SUCCEEDED on-chain! Tx: {tx_hash}")

        # Check balances
        bal_owner_after = chain.get_token_balance(owner_addr)
        bal_v1_after = chain.get_token_balance(v1_payee)
        bal_v2_after = chain.get_token_balance(v2_payee)

        assert bal_owner_after == bal_owner_before - 27_000_000
        assert bal_v1_after == bal_v1_before + 15_000_000
        assert bal_v2_after == bal_v2_before + 12_000_000

        spent_tot = chain.vault.functions.spentTotal(bytes.fromhex(mandate_id[2:])).call()
        assert spent_tot == 27_000_000
        print("Balances verified! Exactly 27 USDC transferred to registered payees.")

        # 6. Test Unauthorized Payment Rejection
        print("\n[6/6] Testing Unauthorized Payment Rejection...")
        # Attack A: Non-allowlisted vendor "shadydeals"
        unauth_v_id = to_hex(keccak(text="shadydeals"))
        bad_lines = [
            {
                "quoteId": to_hex(keccak(text="quote-bad")),
                "vendorId": unauth_v_id,
                "categoryId": cat_ai,
                "skuId": to_hex(keccak(text="sku-bad")),
                "units": 100,
                "amount": 5_000_000,
            }
        ]
        approved, _, _, decision = verifier.verify_and_approve(
            mandate_id=mandate_id,
            request_id="req-bad-001",
            lines=bad_lines,
            claimed_total=5_000_000,
            agent_address=agent_addr,
        )
        assert not approved
        assert decision["reasonCode"] == "VENDOR_NOT_ALLOWED"
        print(f"Unauthorized purchase successfully rejected by Verifier: {decision['reasonCode']}")

        # Attack B: Bypassing verifier and calling contract with forged approval
        fake_approval = {
            "mandateId": mandate_id,
            "approvalId": to_hex(keccak(text="fake-approval")),
            "basketHash": to_hex(keccak(text="fake-basket")),
            "totalAmount": 5_000_000,
            "deadline": chain_time + 120,
            "verifierEpoch": 1,
        }
        rogue_sig = sign_eip712_digest(keccak(b"forged"), owner_pk)

        success, _, _, contract_err = chain.execute_basket(
            mandate_id_hex=mandate_id,
            approval=fake_approval,
            lines=bad_lines,
            verifier_sig_hex=rogue_sig,
            agent_private_key=agent_pk,
        )
        assert not success
        print(f"Contract execution with forged approval reverted on-chain with: {contract_err}")

        # Save Phase 1 proof artifact
        proof_bundle = {
            "phase": "Phase 1: Smart contract and verifier",
            "gate_status": "PASSED",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "contracts": {
                "policyVault": vault_addr,
                "mockUsdc": usdc_addr,
                "chainId": 31337,
            },
            "happy_path_execution": {
                "mandateId": mandate_id,
                "approvalId": approval_data["approvalId"],
                "basketHash": approval_data["basketHash"],
                "totalPaidMicroUsdc": claimed_total,
                "txHash": tx_hash,
                "blockNumber": exec_receipt["blockNumber"],
                "gasUsed": exec_receipt["gasUsed"],
                "status": "SUCCESS",
                "balances": {
                    "ownerBefore": bal_owner_before,
                    "ownerAfter": bal_owner_after,
                    "vendor1PayeeBefore": bal_v1_before,
                    "vendor1PayeeAfter": bal_v1_after,
                    "vendor2PayeeBefore": bal_v2_before,
                    "vendor2PayeeAfter": bal_v2_after,
                },
            },
            "unauthorized_rejections": [
                {
                    "attack": "Non-allowlisted vendor",
                    "layer": "Verifier",
                    "reasonCode": decision["reasonCode"],
                    "status": "REJECTED",
                },
                {
                    "attack": "Forged approval direct contract call",
                    "layer": "PolicyVault Contract",
                    "error": contract_err,
                    "status": "REVERTED",
                },
            ],
        }

        with open("evidence/runs/phase1_gate.json", "w") as f:
            json.dump(proof_bundle, f, indent=2)

        print("\n=== PHASE 1 RELEASE GATE PASSED ===")
        print("Proof bundle written to evidence/runs/phase1_gate.json")

    finally:
        print("\nStopping Anvil process...")
        anvil_proc.terminate()
        try:
            anvil_proc.wait(timeout=3)
        except Exception:
            anvil_proc.kill()


if __name__ == "__main__":
    main()
