"""Purchase Proof Bundle Builder for AgentVault.

Constructs comprehensive, auditable proof bundles (§13.2) linking:
- Off-chain requirements & quote cryptographic proofs
- Verifier decisions, reason codes, and EIP-712 approval structures
- On-chain transaction receipts, event logs, and atomic transfer balances
"""

import time
from typing import Dict, Any, List, Optional


class ProofStore:
    def __init__(self):
        self._proofs: Dict[str, Dict[str, Any]] = {}

    def create_proof_bundle(
        self,
        proof_id: str,
        request_id: str,
        requirement_id: str,
        mandate_id: str,
        lines: List[Dict[str, Any]],
        basket_hash: str,
        total_amount: int,
        verifier_decision: Dict[str, Any],
        approval_data: Optional[Dict[str, Any]] = None,
        approval_sig: Optional[str] = None,
        tx_hash: Optional[str] = None,
        receipt_status: Optional[int] = None,
        block_number: Optional[int] = None,
        gas_used: Optional[int] = None,
        contract_address: Optional[str] = None,
        chain_id: int = 31337,
        events: Optional[List[Dict[str, Any]]] = None,
        payee_transfers: Optional[List[Dict[str, Any]]] = None,
        remaining_budget: Optional[int] = None,
        execution_mode: str = "LIVE_QPIAI",
        fallback_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build and store an immutable purchase proof bundle."""
        bundle = {
            "proofId": proof_id,
            "timestamp": time.time(),
            "requestId": request_id,
            "requirementId": requirement_id,
            "mandateId": mandate_id,
            "basketHash": basket_hash,
            "totalAmount": total_amount,
            "lines": lines,
            "quoteIds": [line["quoteId"] for line in lines],
            "verifierDecision": verifier_decision,
            "approval": {
                "approvalId": approval_data.get("approvalId") if approval_data else None,
                "deadline": approval_data.get("deadline") if approval_data else None,
                "epoch": approval_data.get("epoch") if approval_data else None,
                "signature": approval_sig,
            } if approval_data else None,
            "onChainExecution": {
                "submitted": tx_hash is not None,
                "txHash": tx_hash,
                "receiptStatus": receipt_status,
                "blockNumber": block_number,
                "gasUsed": gas_used,
                "contractAddress": contract_address,
                "chainId": chain_id,
                "events": events or [],
                "payeeTransfers": payee_transfers or [],
                "remainingBudget": remaining_budget,
            },
            "telemetry": {
                "executionMode": execution_mode,
                "fallbackStatus": fallback_status or "NONE",
            }
        }
        self._proofs[proof_id] = bundle
        return bundle

    def get_proof(self, proof_id: str) -> Optional[Dict[str, Any]]:
        return self._proofs.get(proof_id)

    def list_proofs(self) -> List[Dict[str, Any]]:
        return list(self._proofs.values())


global_proof_store = ProofStore()
