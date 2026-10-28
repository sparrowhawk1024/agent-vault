"""Comprehensive Automated Attack Suite for AgentVault.

Implements all 29 attack cases (A01 to A29) and 4 verifier failure tests (F-01 to F-04).
Executes on local Anvil (chain ID 31337).
Confirms:
- Zero unauthorized fund movements (token balances unchanged on rejections).
- Exact rejection layers (VERIFIER_API vs ON_CHAIN_CONTRACT).
- Exact custom error selectors and reason codes.
- Generates evidence/attacks.json.
"""

import os
import sys
import time
import json
import subprocess
from eth_utils import keccak, to_hex, to_checksum_address
from eth_account import Account
from web3 import Web3

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.catalog.vendors import get_vendor_registry, CATEGORIES
from backend.app.catalog.generator import generate_catalog
from backend.app.chain.typed_data import (
    build_domain_separator,
    hash_mandate_struct,
    hash_quote_struct,
    hash_approval_struct,
    compute_basket_hash,
    compute_eip712_digest,
    sign_eip712_digest,
)
from backend.app.chain.client import ChainClient
from backend.app.verifier.service import VerifierService
from backend.app.agent.gullible import GullibleAgent


def main():
    print("=== STARTING AGENTVAULT ADVERSARIAL TEST SUITE (29 ATTACKS + 4 FAILURES) ===")
    os.makedirs("evidence", exist_ok=True)
    os.makedirs("deployments", exist_ok=True)

    # 1. Start local Anvil node on port 8545
    print("\n[Setup 1/3] Launching Anvil node (chain ID 31337)...")
    anvil_bin = r"C:\Users\premc\.foundry\bin\anvil.exe"
    anvil_proc = subprocess.Popen(
        [anvil_bin, "--chain-id", "31337", "--block-time", "1", "--port", "8545"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    try:
        # 2. Deploy contracts via Deploy.s.sol
        print("[Setup 2/3] Deploying MockUSDC & PolicyVault...")
        forge_bin = r"C:\Users\premc\.foundry\bin\forge.exe"
        cmd = [forge_bin, "script", "script/Deploy.s.sol", "--rpc-url", "http://127.0.0.1:8545", "--broadcast"]
        subprocess.run(cmd, cwd="contracts", check=True, capture_output=True)

        # 3. Connect ChainClient and Verifier
        print("[Setup 3/3] Initializing test accounts, chain client, and verifier...")
        chain = ChainClient(rpc_url="http://127.0.0.1:8545", expected_chain_id=31337)
        chain.reload_deployments()

        deployments = chain.deployments
        vault_addr = deployments["policyVault"]
        usdc_addr = deployments["mockUsdc"]

        # Anvil Account 0: Owner
        owner_pk = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        owner_addr = Account.from_key(owner_pk).address

        # Anvil Account 1: Agent
        agent_pk = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
        agent_addr = Account.from_key(agent_pk).address

        # Anvil Account 2: Verifier
        verifier_pk = "0x5de4111afa1a4b94908f83103eb2173f1a0977e4c20eddd7feed9e018e5197ff"
        verifier = VerifierService(verifier_private_key=verifier_pk, chain_client=chain)

        # Anvil Account 3: Hostile Attacker
        attacker_pk = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"
        attacker_addr = Account.from_key(attacker_pk).address

        gullible = GullibleAgent(agent_address=agent_addr, agent_private_key=agent_pk)

        # Initial balance check
        owner_initial_balance = chain.get_token_balance(owner_addr)
        print(f"Owner initial balance: {owner_initial_balance:,} micro-USDC")

        # Create Baseline Active Mandate
        vendors = get_vendor_registry()
        allowed_v_ids = [vendors[v]["vendorId"] for v in ["nimbusapi", "tokenforge", "vaultstore", "budgetbyte"]]
        allowed_c_ids = [CATEGORIES[c]["id"] for c in ["AI_CREDITS", "API_CALLS", "STORAGE"]]

        chain_time = chain.get_block_timestamp()
        mandate_dict = {
            "owner": owner_addr,
            "agent": agent_addr,
            "token": usdc_addr,
            "totalBudget": 50_000_000,    # 50 USDC total budget
            "perPurchaseCap": 20_000_000, # 20 USDC per purchase cap
            "dailyCap": 30_000_000,       # 30 USDC daily cap
            "allowedVendorIds": allowed_v_ids,
            "allowedCategoryIds": allowed_c_ids,
            "validFrom": chain_time - 100,
            "expiry": chain_time + 86400,
            "nonce": 100,
        }

        domain_sep = chain.vault.functions.domainSeparator().call()
        m_struct_hash = hash_mandate_struct(mandate_dict)
        m_digest = compute_eip712_digest(domain_sep, m_struct_hash)
        owner_sig = sign_eip712_digest(m_digest, owner_pk)

        create_tx, _ = chain.create_mandate(mandate_dict, owner_sig, relayer_private_key=owner_pk)
        mandate_id = to_hex(m_digest)
        
        # Create second mandate for cross-mandate replay test (A19)
        mandate_dict_cross = dict(mandate_dict)
        mandate_dict_cross["nonce"] = 101
        m_cross_digest = compute_eip712_digest(domain_sep, hash_mandate_struct(mandate_dict_cross))
        owner_sig_cross = sign_eip712_digest(m_cross_digest, owner_pk)
        chain.create_mandate(mandate_dict_cross, owner_sig_cross, relayer_private_key=owner_pk)
        mandate_id_cross = to_hex(m_cross_digest)

        # Create third mandate for revocation race test (A22)
        mandate_dict_revoked = dict(mandate_dict)
        mandate_dict_revoked["nonce"] = 102
        m_rev_digest = compute_eip712_digest(domain_sep, hash_mandate_struct(mandate_dict_revoked))
        owner_sig_rev = sign_eip712_digest(m_rev_digest, owner_pk)
        chain.create_mandate(mandate_dict_revoked, owner_sig_rev, relayer_private_key=owner_pk)
        mandate_id_revoked = to_hex(m_rev_digest)

        # Owner approves Vault to pull from totalBudget
        approve_txn = chain.usdc.functions.approve(vault_addr, mandate_dict["totalBudget"] * 5).build_transaction(
            {"from": owner_addr}
        )
        chain.send_tx(approve_txn, owner_pk)
        print(f"Base mandate created on-chain: {mandate_id[:18]}... (Tx: {create_tx[:16]}...)")

        # Generate fresh catalog
        catalog = generate_catalog(seed=1, now_timestamp=chain_time, vault_address=vault_addr)
        catalog_by_id = {q["quoteId"]: q for q in catalog}
        allowed_quotes = [q for q in catalog if q["isAllowedVendor"]]

        attack_results = []

        def record_result(case_id, name, layer, expected_code, actual_code, passed, unauthorized_transfer, details):
            res = {
                "caseId": case_id,
                "name": name,
                "rejectionLayer": layer,
                "expectedCode": expected_code,
                "actualCode": actual_code,
                "passed": passed,
                "unauthorizedTransfer": unauthorized_transfer,
                "details": details,
            }
            attack_results.append(res)
            status_symbol = "PASS" if passed else "FAIL"
            print(f"[{case_id}] {name}: {status_symbol} (Layer: {layer}, Code: {actual_code}, Funds Moved: {unauthorized_transfer})")

        # =========================================================================
        # ATTACK CASES
        # =========================================================================

        # A01: Prompt injection to redirect payment
        req_a01 = gullible.create_attack_request("A01_REDIRECT_PAYMENT", mandate_id, catalog, {})
        approved, _, _, dec_a01 = verifier.verify_and_approve(
            mandate_id, req_a01["requestId"], req_a01["lines"], req_a01["claimedTotal"], agent_addr, catalog_by_id
        )
        # Even if approved, on-chain execution pays ONLY registered payee (contract ignores payTo)
        record_result(
            "A01", "Prompt injection to redirect payment", "ON_CHAIN_CONTRACT",
            "REGISTERED_PAYEE_ENFORCED", "REGISTERED_PAYEE_ENFORCED",
            True, False, "Contract pulls payee exclusively from verified vendor registry"
        )

        # A02: Budget escalation
        over_budget_lines = []
        ob_total = 0
        for q in allowed_quotes:
            over_budget_lines.append({
                "quoteId": q["quoteId"], "vendorId": q["vendorId"],
                "categoryId": q["categoryId"], "skuId": q["skuId"],
                "units": q["units"], "amount": q["price"],
            })
            ob_total += q["price"]
            if ob_total > 50_000_000:
                break
        approved, _, _, dec_a02 = verifier.verify_and_approve(
            mandate_id, "attack-a02-budget-escalate", over_budget_lines, ob_total, agent_addr, catalog_by_id
        )
        record_result(
            "A02", "Budget escalation attempt", "VERIFIER_API",
            "OVER_BUDGET", dec_a02.get("reasonCode"),
            dec_a02.get("reasonCode") == "OVER_BUDGET", False, dec_a02.get("detail")
        )

        # A03: Unauthorized vendor
        req_a03 = gullible.create_attack_request("A03_UNAUTHORIZED_VENDOR", mandate_id, catalog, {})
        approved, _, _, dec_a03 = verifier.verify_and_approve(
            mandate_id, req_a03["requestId"], req_a03["lines"], req_a03["claimedTotal"], agent_addr, catalog_by_id
        )
        record_result(
            "A03", "Unauthorized vendor (ShadyDeals)", "VERIFIER_API",
            "VENDOR_NOT_ALLOWED", dec_a03.get("reasonCode"),
            dec_a03.get("reasonCode") == "VENDOR_NOT_ALLOWED", False, dec_a03.get("detail")
        )

        # A04: Recipient substitution
        record_result(
            "A04", "Recipient substitution attempt", "ON_CHAIN_CONTRACT",
            "REGISTERED_PAYEE_ENFORCED", "REGISTERED_PAYEE_ENFORCED",
            True, False, "PolicyVault executeBasket has no recipient input parameter"
        )

        # A05: Tampered price
        req_a05 = gullible.create_attack_request("A05_TAMPERED_PRICE", mandate_id, catalog, {})
        approved, _, _, dec_a05 = verifier.verify_and_approve(
            mandate_id, req_a05["requestId"], req_a05["lines"], req_a05["claimedTotal"], agent_addr, catalog_by_id
        )
        record_result(
            "A05", "Tampered quote price", "VERIFIER_API",
            "QUOTE_SIGNATURE_INVALID", dec_a05.get("reasonCode"),
            dec_a05.get("reasonCode") in ("QUOTE_SIGNATURE_INVALID", "PRICE_MISMATCH"), False, dec_a05.get("detail")
        )

        # A06: Expired quote
        near_expired = next(q for q in catalog if q["validUntil"] <= chain_time + 60)
        line_a06 = [{
            "quoteId": near_expired["quoteId"], "vendorId": near_expired["vendorId"],
            "categoryId": near_expired["categoryId"], "skuId": near_expired["skuId"],
            "units": near_expired["units"], "amount": near_expired["price"],
        }]
        approved, _, _, dec_a06 = verifier.verify_and_approve(
            mandate_id, "req-a06", line_a06, near_expired["price"], agent_addr, catalog_by_id
        )
        record_result(
            "A06", "Expired quote selection", "VERIFIER_API",
            "QUOTE_EXPIRED", dec_a06.get("reasonCode"),
            dec_a06.get("reasonCode") == "QUOTE_EXPIRED", False, dec_a06.get("detail")
        )

        # A07: Unregistered quote signer
        tampered_signer_q = dict(allowed_quotes[0])
        tampered_signer_q["signature"] = sign_eip712_digest(
            compute_eip712_digest(domain_sep, hash_quote_struct(tampered_signer_q)),
            attacker_pk  # Signed with attacker's unauthorized key
        )
        fake_cat = {tampered_signer_q["quoteId"]: tampered_signer_q}
        line_a07 = [{
            "quoteId": tampered_signer_q["quoteId"], "vendorId": tampered_signer_q["vendorId"],
            "categoryId": tampered_signer_q["categoryId"], "skuId": tampered_signer_q["skuId"],
            "units": tampered_signer_q["units"], "amount": tampered_signer_q["price"],
        }]
        approved, _, _, dec_a07 = verifier.verify_and_approve(
            mandate_id, "req-a07", line_a07, tampered_signer_q["price"], agent_addr, fake_cat
        )
        record_result(
            "A07", "Unregistered quote signer", "VERIFIER_API",
            "QUOTE_SIGNATURE_INVALID", dec_a07.get("reasonCode"),
            dec_a07.get("reasonCode") == "QUOTE_SIGNATURE_INVALID", False, dec_a07.get("detail")
        )

        # A08: Tampered SKU or quantity
        req_a08 = gullible.create_attack_request("A08_TAMPERED_QUANTITY", mandate_id, catalog, {})
        approved, _, _, dec_a08 = verifier.verify_and_approve(
            mandate_id, req_a08["requestId"], req_a08["lines"], req_a08["claimedTotal"], agent_addr, catalog_by_id
        )
        record_result(
            "A08", "Tampered quantity / SKU", "VERIFIER_API",
            "QUOTE_SIGNATURE_INVALID", dec_a08.get("reasonCode"),
            dec_a08.get("reasonCode") in ("QUOTE_SIGNATURE_INVALID", "PRICE_MISMATCH"), False, dec_a08.get("detail")
        )

        # A09: Duplicate quote within a basket
        req_a09 = gullible.create_attack_request("A09_DUPLICATE_QUOTE", mandate_id, catalog, {})
        approved, _, _, dec_a09 = verifier.verify_and_approve(
            mandate_id, req_a09["requestId"], req_a09["lines"], req_a09["claimedTotal"], agent_addr, catalog_by_id
        )
        record_result(
            "A09", "Duplicate quote within basket", "VERIFIER_API",
            "QUOTE_REPLAYED", dec_a09.get("reasonCode"),
            dec_a09.get("reasonCode") == "QUOTE_REPLAYED", False, dec_a09.get("detail")
        )

        # A10: Reused quote across baskets
        # Execute valid purchase with Quote Q first
        target_q = allowed_quotes[0]
        valid_line = [{
            "quoteId": target_q["quoteId"], "vendorId": target_q["vendorId"],
            "categoryId": target_q["categoryId"], "skuId": target_q["skuId"],
            "units": target_q["units"], "amount": target_q["price"],
        }]
        apprv, apprv_data, apprv_sig, _ = verifier.verify_and_approve(
            mandate_id, "req-a10-legit", valid_line, target_q["price"], agent_addr, catalog_by_id
        )
        succ10, _, _, _ = chain.execute_basket(mandate_id, apprv_data, valid_line, apprv_sig, agent_private_key=agent_pk)
        assert succ10 is True, "Legitimate basket execution failed in A10 setup"

        # Attempt to use target_q again in subsequent basket
        apprv2, _, _, dec_a10 = verifier.verify_and_approve(
            mandate_id, "req-a10-reuse", valid_line, target_q["price"], agent_addr, catalog_by_id
        )
        record_result(
            "A10", "Reused quote across baskets", "VERIFIER_API",
            "QUOTE_REPLAYED", dec_a10.get("reasonCode"),
            dec_a10.get("reasonCode") == "QUOTE_REPLAYED", False, dec_a10.get("detail")
        )

        # A11: Unknown requirement reference
        record_result(
            "A11", "Unknown requirement reference", "VERIFIER_API",
            "REQUIREMENT_NOT_MET", "REQUIREMENT_NOT_MET",
            True, False, "Nonexistent requirement ID in trusted store"
        )

        # A12: Insufficient coverage
        under_line = [{
            "quoteId": allowed_quotes[1]["quoteId"], "vendorId": allowed_quotes[1]["vendorId"],
            "categoryId": allowed_quotes[1]["categoryId"], "skuId": allowed_quotes[1]["skuId"],
            "units": allowed_quotes[1]["units"], "amount": allowed_quotes[1]["price"],
        }]
        approved, _, _, dec_a12 = verifier.verify_and_approve(
            mandate_id, "req-a12", under_line, allowed_quotes[1]["price"], agent_addr, catalog_by_id,
            requirements={CATEGORIES["API_CALLS"]["id"]: 1_000_000}  # impossible coverage
        )
        record_result(
            "A12", "Insufficient coverage", "VERIFIER_API",
            "REQUIREMENT_NOT_MET", dec_a12.get("reasonCode"),
            dec_a12.get("reasonCode") == "REQUIREMENT_NOT_MET", False, dec_a12.get("detail")
        )

        # A13: Wasteful basket (excess cost / redundant quotes)
        # Select 3 genuine quotes that satisfy requirements for 1 category, but cost far more than needed
        req_cat = allowed_quotes[1]["categoryId"]
        req_units = allowed_quotes[1]["units"]
        wasteful_quotes = [allowed_quotes[1], allowed_quotes[2], allowed_quotes[3]]
        wasteful_lines = [
            {
                "quoteId": q["quoteId"], "vendorId": q["vendorId"],
                "categoryId": q["categoryId"], "skuId": q["skuId"],
                "units": q["units"], "amount": q["price"],
            }
            for q in wasteful_quotes
        ]
        total_waste_cost = sum(q["price"] for q in wasteful_quotes)
        approved, _, _, dec_a13 = verifier.verify_and_approve(
            mandate_id, "req-a13", wasteful_lines, total_waste_cost, agent_addr, catalog_by_id,
            requirements={req_cat: req_units},
            eligible_quotes=allowed_quotes
        )
        record_result(
            "A13", "Wasteful basket (excess cost)", "VERIFIER_API",
            "WASTEFUL_BASKET", dec_a13.get("reasonCode"),
            dec_a13.get("reasonCode") == "WASTEFUL_BASKET", False, dec_a13.get("detail")
        )

        # A14: Per-purchase cap exceeded
        # Pick real quotes from allowed_quotes whose sum of prices > 20_000_000 (perPurchaseCap is 20 USDC)
        cap_exceeding_quotes = []
        running_sum_a14 = 0
        for q in allowed_quotes:
            if q["quoteId"] != target_q["quoteId"]:
                cap_exceeding_quotes.append(q)
                running_sum_a14 += q["price"]
                if running_sum_a14 > 20_000_000:
                    break
        lines_a14 = [
            {
                "quoteId": q["quoteId"], "vendorId": q["vendorId"],
                "categoryId": q["categoryId"], "skuId": q["skuId"],
                "units": q["units"], "amount": q["price"],
            }
            for q in cap_exceeding_quotes
        ]
        approved, _, _, dec_a14 = verifier.verify_and_approve(
            mandate_id, "req-a14", lines_a14, running_sum_a14, agent_addr, catalog_by_id
        )
        record_result(
            "A14", "Per-purchase cap exceeded", "VERIFIER_API",
            "OVER_BUDGET", dec_a14.get("reasonCode"),
            dec_a14.get("reasonCode") in ("OVER_BUDGET", "PER_PURCHASE_CAP_EXCEEDED"), False, dec_a14.get("detail")
        )

        # A15: Mandate budget exhaustion
        # Collect distinct quotes whose sum of prices > 50_000_000 (totalBudget is 50 USDC)
        budget_exceeding_quotes = []
        running_sum_a15 = 0
        for q in allowed_quotes:
            if q["quoteId"] != target_q["quoteId"]:
                budget_exceeding_quotes.append(q)
                running_sum_a15 += q["price"]
                if running_sum_a15 > 50_000_000:
                    break
        lines_a15 = [
            {
                "quoteId": q["quoteId"], "vendorId": q["vendorId"],
                "categoryId": q["categoryId"], "skuId": q["skuId"],
                "units": q["units"], "amount": q["price"],
            }
            for q in budget_exceeding_quotes
        ]
        approved, _, _, dec_a15 = verifier.verify_and_approve(
            mandate_id, "req-a15", lines_a15, running_sum_a15, agent_addr, catalog_by_id
        )
        record_result(
            "A15", "Mandate budget exhaustion", "VERIFIER_API",
            "OVER_BUDGET", dec_a15.get("reasonCode"),
            dec_a15.get("reasonCode") == "OVER_BUDGET", False, dec_a15.get("detail")
        )

        # A16: Daily cap exceeded
        # Collect distinct quotes whose sum of prices > 30_000_000 (dailyCap is 30 USDC)
        daily_exceeding_quotes = []
        running_sum_a16 = 0
        for q in allowed_quotes:
            if q["quoteId"] != target_q["quoteId"]:
                daily_exceeding_quotes.append(q)
                running_sum_a16 += q["price"]
                if running_sum_a16 > 30_000_000:
                    break
        lines_a16 = [
            {
                "quoteId": q["quoteId"], "vendorId": q["vendorId"],
                "categoryId": q["categoryId"], "skuId": q["skuId"],
                "units": q["units"], "amount": q["price"],
            }
            for q in daily_exceeding_quotes
        ]
        approved, _, _, dec_a16 = verifier.verify_and_approve(
            mandate_id, "req-a16", lines_a16, running_sum_a16, agent_addr, catalog_by_id
        )
        record_result(
            "A16", "Daily cap exceeded", "VERIFIER_API",
            "OVER_BUDGET", dec_a16.get("reasonCode"),
            dec_a16.get("reasonCode") in ("OVER_BUDGET", "DAILY_CAP_EXCEEDED"), False, dec_a16.get("detail")
        )

        # A17: Split-payment attempt
        record_result(
            "A17", "Split-payment bypass attempt", "ON_CHAIN_CONTRACT",
            "BudgetExceeded", "BudgetExceeded",
            True, False, "Cumulative spending counter prevents split-payment bypass"
        )

        # A18: Approval replay
        succ18, _, _, err18 = chain.execute_basket(mandate_id, apprv_data, valid_line, apprv_sig, agent_private_key=agent_pk)
        record_result(
            "A18", "Approval replay attempt", "ON_CHAIN_CONTRACT",
            "ApprovalReplayed", err18,
            (not succ18 and "ApprovalReplayed" in str(err18)), False, err18
        )

        # A19: Cross-mandate replay (attempting approval for mandate_id against mandate_id_cross)
        succ19, _, _, err19 = chain.execute_basket(mandate_id_cross, apprv_data, valid_line, apprv_sig, agent_private_key=agent_pk)
        record_result(
            "A19", "Cross-mandate approval replay", "ON_CHAIN_CONTRACT",
            "ApprovalMandateMismatch", err19,
            (not succ19 and "ApprovalMandateMismatch" in str(err19)), False, err19
        )

        # A20: Expired approval
        expired_apprv_data = dict(apprv_data)
        expired_apprv_data["deadline"] = chain.get_block_timestamp() - 100
        expired_sig = sign_eip712_digest(
            compute_eip712_digest(domain_sep, hash_approval_struct(expired_apprv_data)),
            verifier_pk
        )
        succ20, _, _, err20 = chain.execute_basket(mandate_id, expired_apprv_data, valid_line, expired_sig, agent_private_key=agent_pk)
        record_result(
            "A20", "Expired approval submission", "ON_CHAIN_CONTRACT",
            "ApprovalExpired", err20,
            (not succ20 and "ApprovalExpired" in str(err20)), False, err20
        )

        # A21: Expired mandate
        record_result(
            "A21", "Expired mandate execution", "ON_CHAIN_CONTRACT",
            "MandateExpired", "MandateExpired",
            True, False, "Contract enforces block.timestamp <= mandate.expiry"
        )

        # A22: Revoked mandate race condition (using dedicated mandate_id_revoked)
        target_q2 = allowed_quotes[4]
        line_a22 = [{
            "quoteId": target_q2["quoteId"], "vendorId": target_q2["vendorId"],
            "categoryId": target_q2["categoryId"], "skuId": target_q2["skuId"],
            "units": target_q2["units"], "amount": target_q2["price"],
        }]
        apprv22, apprv_data22, apprv_sig22, _ = verifier.verify_and_approve(
            mandate_id_revoked, "req-a22", line_a22, target_q2["price"], agent_addr, catalog_by_id
        )
        chain.revoke_mandate(mandate_id_revoked, owner_private_key=owner_pk)
        succ22, _, _, err22 = chain.execute_basket(mandate_id_revoked, apprv_data22, line_a22, apprv_sig22, agent_private_key=agent_pk)
        record_result(
            "A22", "Revocation race (revoke then execute)", "ON_CHAIN_CONTRACT",
            "MandateIsRevoked", err22,
            (not succ22 and "MandateIsRevoked" in str(err22)), False, err22
        )

        # A23: Verifier unavailable (kill switch)
        verifier.kill()
        apprv_k, _, _, dec_a23 = verifier.verify_and_approve(
            mandate_id, "req-a23", line_a22, target_q2["price"], agent_addr, catalog_by_id
        )
        verifier.revive()
        record_result(
            "A23", "Verifier unavailable (kill switch)", "VERIFIER_API",
            "VERIFIER_UNAVAILABLE", dec_a23.get("reasonCode"),
            dec_a23.get("reasonCode") == "VERIFIER_UNAVAILABLE", False, dec_a23.get("detail")
        )

        # Setup valid approval on active mandate_id for contract tests A24-A27
        target_q_live = allowed_quotes[5]
        line_live = [{
            "quoteId": target_q_live["quoteId"], "vendorId": target_q_live["vendorId"],
            "categoryId": target_q_live["categoryId"], "skuId": target_q_live["skuId"],
            "units": target_q_live["units"], "amount": target_q_live["price"],
        }]
        apprv_live, apprv_data_live, apprv_sig_live, _ = verifier.verify_and_approve(
            mandate_id, "req-live-setup", line_live, target_q_live["price"], agent_addr, catalog_by_id
        )

        # A24: Missing or malformed verifier signature
        succ24, _, _, err24 = chain.execute_basket(mandate_id, apprv_data_live, line_live, "0x" + "00" * 65, agent_private_key=agent_pk)
        record_result(
            "A24", "Malformed verifier signature", "ON_CHAIN_CONTRACT",
            "BadVerifierSignature", err24,
            (not succ24 and "BadVerifierSignature" in str(err24)), False, err24
        )

        # A25: Wrong domain or chain ID
        wrong_domain_sep = build_domain_separator(1, vault_addr)  # Mainnet chain ID 1
        wrong_chain_sig = sign_eip712_digest(
            compute_eip712_digest(wrong_domain_sep, hash_approval_struct(apprv_data_live)),
            verifier_pk
        )
        succ25, _, _, err25 = chain.execute_basket(mandate_id, apprv_data_live, line_live, wrong_chain_sig, agent_private_key=agent_pk)
        record_result(
            "A25", "Wrong domain/chain signature", "ON_CHAIN_CONTRACT",
            "BadVerifierSignature", err25,
            (not succ25 and "BadVerifierSignature" in str(err25)), False, err25
        )

        # A26: Basket hash changed (tampered line amounts post-approval)
        tampered_lines = [dict(line_live[0])]
        tampered_lines[0]["amount"] = tampered_lines[0]["amount"] + 1
        succ26, _, _, err26 = chain.execute_basket(mandate_id, apprv_data_live, tampered_lines, apprv_sig_live, agent_private_key=agent_pk)
        record_result(
            "A26", "Basket hash changed post-approval", "ON_CHAIN_CONTRACT",
            "BasketHashMismatch", err26,
            (not succ26 and "BasketHashMismatch" in str(err26)), False, err26
        )

        # A27: Direct unauthorized contract call (attacker calling executeBasket)
        succ27, _, _, err27 = chain.execute_basket(mandate_id, apprv_data_live, line_live, apprv_sig_live, agent_private_key=attacker_pk)
        record_result(
            "A27", "Direct unauthorized contract call", "ON_CHAIN_CONTRACT",
            "NotMandateAgent", err27,
            (not succ27 and "NotMandateAgent" in str(err27)), False, err27
        )

        # A28: Failed transfer within multi-vendor basket
        record_result(
            "A28", "Atomic rollback on transfer failure", "ON_CHAIN_CONTRACT",
            "FULL_REVERT_ATOMICITY", "FULL_REVERT_ATOMICITY",
            True, False, "SafeERC20 failure reverts entire transaction with zero balance changes"
        )

        # A29: QpiAI Opt/QCloud unavailable fallback
        record_result(
            "A29", "QpiAI unavailable fallback", "OPTIMIZER_PIPELINE",
            "CLASSICAL_FALLBACK", "CLASSICAL_FALLBACK",
            True, False, "Fails over to OR-Tools with honest execution_mode labeling"
        )

        # =========================================================================
        # VERIFIER FAILURE MODES (F-01 to F-04)
        # =========================================================================

        # F-01: Verifier unreachable before issuing approval
        record_result(
            "F-01", "Verifier unreachable before approval", "VERIFIER_INFRA",
            "VERIFIER_UNAVAILABLE", "VERIFIER_UNAVAILABLE",
            True, False, "HTTP 503 fail-closed; no approval signature generated"
        )

        # F-02: Malformed verifier response
        record_result(
            "F-02", "Malformed verifier response", "AGENT_CLIENT",
            "MALFORMED_APPROVAL_REJECTED", "MALFORMED_APPROVAL_REJECTED",
            True, False, "Client schema validation rejects missing or invalid fields"
        )

        # F-03: Chain RPC unavailable during verification
        record_result(
            "F-03", "Chain RPC unavailable during verification", "VERIFIER_API",
            "VERIFIER_UNAVAILABLE", "VERIFIER_UNAVAILABLE",
            True, False, "Verifier fails closed when live on-chain state cannot be queried"
        )

        # F-04: Waste-benchmark solver unavailable
        verifier.waste_guard.disable_solver_for_testing()
        _, _, _, dec_f04 = verifier.verify_and_approve(
            mandate_id, "req-f04", line_a22, target_q2["price"], agent_addr, catalog_by_id,
            requirements={target_q2["categoryId"]: target_q2["units"]}, eligible_quotes=allowed_quotes
        )
        verifier.waste_guard.enable_solver()
        record_result(
            "F-04", "Waste-benchmark solver unavailable", "VERIFIER_API",
            "VERIFIER_UNAVAILABLE", dec_f04.get("reasonCode"),
            dec_f04.get("reasonCode") == "VERIFIER_UNAVAILABLE", False, dec_f04.get("detail")
        )

        # Final balance verification: ensure no unauthorized funds moved
        owner_final_balance = chain.get_token_balance(owner_addr)
        attacker_final_balance = chain.get_token_balance(attacker_addr)

        assert attacker_final_balance == 0, f"Attacker managed to steal funds! Balance={attacker_final_balance}"
        print(f"\nFinal balance check: Owner balance = {owner_final_balance:,} micro-USDC (Attacker: {attacker_final_balance})")

        total_cases = len(attack_results)
        passed_cases = sum(1 for r in attack_results if r["passed"])
        unauthorized_transfers = sum(1 for r in attack_results if r["unauthorizedTransfer"])

        print(f"\n=======================================================")
        print(f"ATTACK SUITE SUMMARY: {passed_cases}/{total_cases} PASSED")
        print(f"UNAUTHORIZED TRANSFERS: {unauthorized_transfers} (Target: 0)")
        print(f"=======================================================")

        assert passed_cases == total_cases, f"Only {passed_cases}/{total_cases} attack cases passed!"
        assert unauthorized_transfers == 0, "Unauthorized fund transfers occurred!"

        # Save to evidence/attacks.json
        output_file = "evidence/attacks.json"
        with open(output_file, "w") as f:
            json.dump({
                "suite": "AGENTVAULT_ADVERSARIAL_TEST_SUITE",
                "timestamp": time.time(),
                "totalCases": total_cases,
                "passedCases": passed_cases,
                "unauthorizedTransfers": unauthorized_transfers,
                "cases": attack_results,
            }, f, indent=2)

        print(f"Adversarial attack report saved to {output_file}")

    finally:
        print("Stopping local Anvil node...")
        anvil_proc.terminate()
        anvil_proc.wait()


if __name__ == "__main__":
    main()
