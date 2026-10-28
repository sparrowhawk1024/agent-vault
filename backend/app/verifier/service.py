"""Independent Verifier Service for AgentVault.

Enforces deterministic policy validation, checks quotes, verifies limits against chain state,
and issues short-lived EIP-712 Approval signatures.
"""

import time
from typing import Dict, Any, List, Tuple, Optional
from eth_utils import keccak, to_hex, to_checksum_address
from eth_account import Account

from backend.app.chain.typed_data import (
    build_domain_separator,
    hash_quote_struct,
    hash_approval_struct,
    compute_basket_hash,
    compute_eip712_digest,
    sign_eip712_digest,
    recover_eip712_signer,
)
from backend.app.verifier.waste_guard import WasteGuard


class VerifierService:
    def __init__(
        self,
        verifier_private_key: str,
        chain_client: Any,
        approval_ttl_seconds: int = 120,
        waste_tolerance_bps: int = 1000,
        excess_units_margin_bps: int = 1000,
    ):
        self.private_key = verifier_private_key
        self.account = Account.from_key(verifier_private_key)
        self.address = self.account.address
        self.chain = chain_client
        self.approval_ttl_seconds = approval_ttl_seconds
        self.is_active = True  # admin kill switch toggle
        self.waste_guard = WasteGuard(
            waste_tolerance_bps=waste_tolerance_bps,
            excess_units_margin_bps=excess_units_margin_bps,
        )

    def kill(self):
        """Emergency kill switch: stops issuing new approvals."""
        self.is_active = False

    def revive(self):
        """Restore verifier operations."""
        self.is_active = True

    def verify_and_approve(
        self,
        mandate_id: str,
        request_id: str,
        lines: List[Dict[str, Any]],
        claimed_total: int,
        agent_address: str,
        quotes_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        requirements: Optional[Dict[str, int]] = None,
        eligible_quotes: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], Dict[str, Any]]:
        """Run all verification checks.

        Returns (approved, approval_dict, signature_hex, decision_record).
        """
        decision_record = {
            "mandateId": mandate_id,
            "requestId": request_id,
            "timestamp": time.time(),
            "checks": {},
            "status": "REJECTED",
            "reasonCode": None,
        }

        # 0. Kill switch check
        if not self.is_active:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "VERIFIER_UNAVAILABLE"
            decision_record["detail"] = "Verifier service is currently deactivated (kill switch)"
            return False, None, None, decision_record

        # 1. On-chain mandate check
        if not self.chain.vault:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "VERIFIER_UNAVAILABLE"
            decision_record["detail"] = "Chain client not connected to PolicyVault"
            return False, None, None, decision_record

        mandate_id_bytes = bytes.fromhex(mandate_id[2:] if mandate_id.startswith("0x") else mandate_id)
        exists = self.chain.vault.functions.mandateExists(mandate_id_bytes).call()
        if not exists:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "MANDATE_NOT_FOUND"
            return False, None, None, decision_record

        is_revoked = self.chain.vault.functions.isRevoked(mandate_id_bytes).call()
        if is_revoked:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "MANDATE_REVOKED"
            return False, None, None, decision_record

        on_chain_mandate = self.chain.vault.functions.getMandate(mandate_id_bytes).call()
        # mandate tuple: owner, agent, token, totalBudget, perPurchaseCap, dailyCap, vendors, categories, validFrom, expiry, nonce
        m_agent = on_chain_mandate[1]
        m_total_budget = on_chain_mandate[3]
        m_per_purchase_cap = on_chain_mandate[4]
        m_daily_cap = on_chain_mandate[5]
        m_valid_from = on_chain_mandate[8]
        m_expiry = on_chain_mandate[9]

        if to_checksum_address(agent_address) != to_checksum_address(m_agent):
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "AGENT_NOT_AUTHORIZED"
            return False, None, None, decision_record

        chain_time = self.chain.get_block_timestamp()
        if chain_time < m_valid_from or chain_time > m_expiry:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "MANDATE_INACTIVE"
            return False, None, None, decision_record

        # 2. Basket line validation
        if not lines or len(lines) > 16:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "INVALID_REQUEST"
            decision_record["detail"] = "Basket lines count must be between 1 and 16"
            return False, None, None, decision_record

        calculated_total = 0
        seen_quotes = set()

        for idx, line in enumerate(lines):
            quote_id = line["quoteId"]
            vendor_id = line["vendorId"]
            category_id = line["categoryId"]
            amount = int(line["amount"])

            if amount <= 0:
                decision_record["status"] = "REJECTED"
                decision_record["reasonCode"] = "INVALID_REQUEST"
                decision_record["detail"] = f"Line {idx} amount must be > 0"
                return False, None, None, decision_record

            if quote_id in seen_quotes:
                decision_record["status"] = "REJECTED"
                decision_record["reasonCode"] = "QUOTE_REPLAYED"
                decision_record["detail"] = f"Duplicate quoteId {quote_id} in basket"
                return False, None, None, decision_record
            seen_quotes.add(quote_id)

            # Check on-chain quote usage
            quote_id_bytes = bytes.fromhex(quote_id[2:] if quote_id.startswith("0x") else quote_id)
            if self.chain.vault.functions.quoteUsed(quote_id_bytes).call():
                decision_record["status"] = "REJECTED"
                decision_record["reasonCode"] = "QUOTE_REPLAYED"
                decision_record["detail"] = f"Quote {quote_id} already consumed on-chain"
                return False, None, None, decision_record

            # Check vendor on-chain registration & activity
            vendor_id_bytes = bytes.fromhex(vendor_id[2:] if vendor_id.startswith("0x") else vendor_id)
            vendor_info = self.chain.vault.functions.vendors(vendor_id_bytes).call()
            # (payee, quoteSigner, active)
            payee, quote_signer, is_active = vendor_info
            if payee == "0x0000000000000000000000000000000000000000" or not is_active:
                decision_record["status"] = "REJECTED"
                decision_record["reasonCode"] = "VENDOR_NOT_ALLOWED"
                decision_record["detail"] = f"Vendor {vendor_id} not registered or inactive on-chain"
                return False, None, None, decision_record

            # Check allowlists
            if not self.chain.vault.functions.isVendorAllowed(mandate_id_bytes, vendor_id_bytes).call():
                decision_record["status"] = "REJECTED"
                decision_record["reasonCode"] = "VENDOR_NOT_ALLOWED"
                decision_record["detail"] = f"Vendor {vendor_id} not on mandate allowlist"
                return False, None, None, decision_record

            category_id_bytes = bytes.fromhex(category_id[2:] if category_id.startswith("0x") else category_id)
            if not self.chain.vault.functions.isCategoryAllowed(mandate_id_bytes, category_id_bytes).call():
                decision_record["status"] = "REJECTED"
                decision_record["reasonCode"] = "CATEGORY_NOT_ALLOWED"
                decision_record["detail"] = f"Category {category_id} not on mandate allowlist"
                return False, None, None, decision_record

            # If signed quote metadata provided, verify quote signature & expiry & match
            if quotes_metadata and quote_id in quotes_metadata:
                qmeta = quotes_metadata[quote_id]
                valid_until = int(qmeta["validUntil"])
                
                # Quote must not be expired and must outlive the approval deadline
                if valid_until <= chain_time + self.approval_ttl_seconds:
                    decision_record["status"] = "REJECTED"
                    decision_record["reasonCode"] = "QUOTE_EXPIRED"
                    decision_record["detail"] = f"Quote {quote_id} validUntil ({valid_until}) does not outlive approval deadline ({chain_time + self.approval_ttl_seconds})"
                    return False, None, None, decision_record

                # Line fields must match signed quote fields
                if amount != int(qmeta["price"]):
                    decision_record["status"] = "REJECTED"
                    decision_record["reasonCode"] = "PRICE_MISMATCH"
                    decision_record["detail"] = f"Line amount {amount} != signed quote price {qmeta['price']}"
                    return False, None, None, decision_record

                if "units" in line and int(line["units"]) != int(qmeta["units"]):
                    decision_record["status"] = "REJECTED"
                    decision_record["reasonCode"] = "QUOTE_SIGNATURE_INVALID"
                    decision_record["detail"] = f"Line units {line['units']} != signed quote units {qmeta['units']}"
                    return False, None, None, decision_record

                if "skuId" in line and line["skuId"].lower() != qmeta["skuId"].lower():
                    decision_record["status"] = "REJECTED"
                    decision_record["reasonCode"] = "QUOTE_SIGNATURE_INVALID"
                    decision_record["detail"] = f"Line skuId {line['skuId']} != signed quote skuId {qmeta['skuId']}"
                    return False, None, None, decision_record

                if "signature" in qmeta:
                    domain_sep = self.chain.vault.functions.domainSeparator().call()
                    q_struct_hash = hash_quote_struct(qmeta)
                    q_digest = compute_eip712_digest(domain_sep, q_struct_hash)
                    recovered_signer = recover_eip712_signer(q_digest, qmeta["signature"])
                    if recovered_signer.lower() != quote_signer.lower():
                        decision_record["status"] = "REJECTED"
                        decision_record["reasonCode"] = "QUOTE_SIGNATURE_INVALID"
                        return False, None, None, decision_record

            calculated_total += amount

        if calculated_total != claimed_total:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "PRICE_MISMATCH"
            decision_record["detail"] = f"Calculated total {calculated_total} != claimed {claimed_total}"
            return False, None, None, decision_record

        # 3. Limits checks
        if calculated_total > m_per_purchase_cap:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "OVER_BUDGET"
            decision_record["detail"] = f"Amount {calculated_total} exceeds perPurchaseCap {m_per_purchase_cap}"
            return False, None, None, decision_record

        spent_total = self.chain.vault.functions.spentTotal(mandate_id_bytes).call()
        if spent_total + calculated_total > m_total_budget:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "OVER_BUDGET"
            decision_record["detail"] = f"Cumulative spend {spent_total + calculated_total} exceeds budget {m_total_budget}"
            return False, None, None, decision_record

        spent_today = self.chain.vault.functions.spentToday(mandate_id_bytes).call()
        if spent_today + calculated_total > m_daily_cap:
            decision_record["status"] = "REJECTED"
            decision_record["reasonCode"] = "DAILY_CAP_EXCEEDED"
            decision_record["detail"] = f"Daily spend {spent_today + calculated_total} exceeds dailyCap {m_daily_cap}"
            return False, None, None, decision_record

        # 3.5. Waste Guard & Coverage Check (if requirements provided)
        if requirements:
            guard_quotes = eligible_quotes or (list(quotes_metadata.values()) if quotes_metadata else [])
            passed, reason_code, detail, bench_meta = self.waste_guard.evaluate_basket(
                candidate_lines=lines,
                quotes_by_id=quotes_metadata or {},
                eligible_quotes=guard_quotes,
                requirements=requirements,
                max_budget=min(m_per_purchase_cap, m_total_budget - spent_total, m_daily_cap - spent_today),
            )
            decision_record["wasteGuard"] = bench_meta
            if not passed:
                decision_record["status"] = "REJECTED"
                decision_record["reasonCode"] = reason_code
                decision_record["detail"] = detail
                return False, None, None, decision_record

        # 4. Generate Approval
        basket_hash_bytes = compute_basket_hash(lines)
        basket_hash_hex = to_hex(basket_hash_bytes)

        nonce = int(time.time() * 1000) % 1_000_000_000
        approval_id_bytes = keccak(
            mandate_id_bytes + basket_hash_bytes + request_id.encode("utf-8") + str(nonce).encode("utf-8")
        )
        approval_id_hex = to_hex(approval_id_bytes)

        deadline = chain_time + self.approval_ttl_seconds
        verifier_epoch = self.chain.vault.functions.verifierEpoch().call()

        approval_data = {
            "mandateId": mandate_id,
            "approvalId": approval_id_hex,
            "basketHash": basket_hash_hex,
            "totalAmount": calculated_total,
            "deadline": deadline,
            "verifierEpoch": verifier_epoch,
        }

        # Sign with Verifier's private key
        domain_sep = self.chain.vault.functions.domainSeparator().call()
        approval_struct_hash = hash_approval_struct(approval_data)
        approval_digest = compute_eip712_digest(domain_sep, approval_struct_hash)
        signature = sign_eip712_digest(approval_digest, self.private_key)

        decision_record["status"] = "APPROVED"
        decision_record["approvalId"] = approval_id_hex
        decision_record["deadline"] = deadline
        decision_record["totalAmount"] = calculated_total

        return True, approval_data, signature, decision_record
