"""Phase 2 Gate Execution Script for AgentVault.

Verifies:
1. Seeded catalog generation (seeds 1, 2, 3) across 5 vendors.
2. Procurement formulation and multi-solver benchmarking:
   - QpiAI Opt MILP (with documented CLASSICAL_FALLBACK)
   - OR-Tools CP-SAT (reference optimum)
   - Greedy baseline
   - Vendor-rule baseline
3. Purchasing-cost calibration: savings vs naive vendor rule >= 15%.
4. Verifier independent acceptance of the optimal basket.
5. Verifier waste guard rejection of an inflated/wasteful basket.
6. Saves detailed benchmark and proof artifacts to evidence/runs/phase2_gate.json.
"""

import os
import sys
import time
import json
from dataclasses import asdict

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.catalog.generator import generate_catalog
from backend.app.catalog.vendors import CATEGORIES
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.selection import run_solver_comparison
from backend.app.verifier.service import VerifierService


from backend.app.catalog.vendors import get_vendor_registry
from backend.app.chain.typed_data import build_domain_separator

DUMMY_VAULT = "0x1111111111111111111111111111111111111111"
REAL_DOMAIN_SEP = build_domain_separator(31337, DUMMY_VAULT)
REAL_VENDORS = get_vendor_registry()


class MockChainForGate:
    """Lightweight chain double for verifier testing during gate validation."""
    def __init__(self):
        self.vault = self

    class functions:
        @staticmethod
        def mandateExists(*_args):
            return type("Call", (), {"call": lambda *a, **k: True})()

        @staticmethod
        def isRevoked(*_args):
            return type("Call", (), {"call": lambda *a, **k: False})()

        @staticmethod
        def getMandate(*_args):
            return type("Call", (), {"call": lambda *a, **k: (
                "0x1111111111111111111111111111111111111111",
                "0x2222222222222222222222222222222222222222",
                "0x4444444444444444444444444444444444444444",
                100_000_000,  # 100 USDC total budget
                40_000_000,   # 40 USDC per purchase cap
                60_000_000,   # 60 USDC daily cap
                [], [],
                1700000000,
                1702592000,
                1
            )})()

        @staticmethod
        def quoteUsed(*_args):
            return type("Call", (), {"call": lambda *a, **k: False})()

        @staticmethod
        def vendors(vendor_id_bytes):
            v_hex = "0x" + vendor_id_bytes.hex()
            for vdata in REAL_VENDORS.values():
                if vdata["vendorId"].lower() == v_hex.lower():
                    return type("Call", (), {"call": lambda *a, **k: (
                        vdata["payee"],
                        vdata["quoteSigner"],
                        vdata["active"]
                    )})()
            return type("Call", (), {"call": lambda *a, **k: (
                "0x0000000000000000000000000000000000000000",
                "0x0000000000000000000000000000000000000000",
                False
            )})()

        @staticmethod
        def isVendorAllowed(*_args):
            return type("Call", (), {"call": lambda *a, **k: True})()

        @staticmethod
        def isCategoryAllowed(*_args):
            return type("Call", (), {"call": lambda *a, **k: True})()

        @staticmethod
        def spentTotal(*_args):
            return type("Call", (), {"call": lambda *a, **k: 0})()

        @staticmethod
        def spentToday(*_args):
            return type("Call", (), {"call": lambda *a, **k: 0})()

        @staticmethod
        def verifierEpoch(*_args):
            return type("Call", (), {"call": lambda *a, **k: 1})()

        @staticmethod
        def domainSeparator(*_args):
            return type("Call", (), {"call": lambda *a, **k: REAL_DOMAIN_SEP})()

    def get_block_timestamp(self):
        return 1700000500


def main():
    print("=== STARTING PHASE 2 RELEASE GATE ===")
    os.makedirs("evidence/runs", exist_ok=True)

    seeds = [1, 2, 3]
    gate_results = []

    mock_chain = MockChainForGate()
    verifier = VerifierService(
        verifier_private_key="0x5de4111afa1a4b94908f83103eb2173f1a0977e4c20eddd7feed9e018e5197ff",
        chain_client=mock_chain,
    )

    dummy_mandate_id = "0x" + "aa" * 32
    dummy_agent_addr = "0x2222222222222222222222222222222222222222"

    requirements = {
        CATEGORIES["API_CALLS"]["id"]: 15_000,
        CATEGORIES["AI_CREDITS"]["id"]: 8_000,
        CATEGORIES["STORAGE"]["id"]: 1_200,
    }

    print("\n[1/3] Benchmarking multi-vendor optimization across Seeds 1, 2, 3...")
    for s in seeds:
        print(f"\n--- Testing Seed {s} ---")
        quotes = generate_catalog(seed=s, now_timestamp=1700000000, vault_address=DUMMY_VAULT)
        allowed_quotes = [q for q in quotes if q["isAllowedVendor"]]

        problem = ProcurementProblem(
            quotes=allowed_quotes,
            requirements=requirements,
            max_budget=40_000_000,  # 40 USDC limit
            max_lines=16,
        )

        comparison = run_solver_comparison(problem)

        ref_opt = comparison.results["ortools"]
        qpiai_res = comparison.results["qpiai"]
        greedy_res = comparison.results["greedy"]
        vendor_res = comparison.results["vendor_rule"]

        print(f"Quotes in catalog: {len(quotes)} (eligible: {len(allowed_quotes)})")
        print(f"Optimal Reference (OR-Tools): {ref_opt.total_cost:,} micro-USDC (${ref_opt.total_cost/1e6:.2f}) | {ref_opt.runtime_ms:.2f}ms")
        print(f"QpiAI Opt ({qpiai_res.execution_mode}): {qpiai_res.total_cost:,} micro-USDC (${qpiai_res.total_cost/1e6:.2f})")
        print(f"Greedy Baseline: {greedy_res.total_cost:,} micro-USDC (${greedy_res.total_cost/1e6:.2f}) | Savings vs Greedy: {comparison.savings_vs_greedy_pct}%")
        print(f"Vendor-Rule Baseline: {vendor_res.total_cost:,} micro-USDC (${vendor_res.total_cost/1e6:.2f}) | Savings vs Vendor-Rule: {comparison.savings_vs_vendor_rule_pct}%")

        assert ref_opt.feasible, f"Seed {s} OR-Tools solver was infeasible"
        assert qpiai_res.feasible, f"Seed {s} QpiAI Opt solver was infeasible"
        assert comparison.savings_vs_vendor_rule_pct >= 15.0, (
            f"Seed {s} savings vs vendor rule ({comparison.savings_vs_vendor_rule_pct}%) was below 15% calibration target!"
        )

        # 2. Test Verifier Independent Verification & Waste Guard
        print("\n[2/3] Verifying candidate basket through VerifierService & Waste Guard...")
        candidate_lines = [
            {
                "quoteId": q["quoteId"],
                "vendorId": q["vendorId"],
                "categoryId": q["categoryId"],
                "skuId": q["skuId"],
                "units": q["units"],
                "amount": q["price"],
            }
            for q in ref_opt.selected_quotes
        ]
        quotes_meta = {q["quoteId"]: q for q in allowed_quotes}

        approved, approval, sig, decision = verifier.verify_and_approve(
            mandate_id=dummy_mandate_id,
            request_id=f"req-gate2-seed-{s}",
            lines=candidate_lines,
            claimed_total=ref_opt.total_cost,
            agent_address=dummy_agent_addr,
            quotes_metadata=quotes_meta,
            requirements=requirements,
            eligible_quotes=allowed_quotes,
        )

        assert approved is True, f"Verifier failed to approve optimal candidate: {decision}"
        assert approval is not None
        assert sig is not None
        print(f"Optimal candidate APPROVED! ApprovalId: {approval['approvalId'][:18]}...")

        # 3. Test Waste Guard Rejection on Inflated Basket (+30% price)
        print("\n[3/3] Testing Verifier Waste Guard rejection on wasteful candidate...")
        wasteful_lines = [
            {
                "quoteId": q["quoteId"],
                "vendorId": q["vendorId"],
                "categoryId": q["categoryId"],
                "skuId": q["skuId"],
                "units": q["units"],
                "amount": int(round(q["price"] * 1.30)),
            }
            for q in ref_opt.selected_quotes
        ]
        wasteful_total = sum(l["amount"] for l in wasteful_lines)

        w_approved, _, _, w_decision = verifier.verify_and_approve(
            mandate_id=dummy_mandate_id,
            request_id=f"req-gate2-wasteful-{s}",
            lines=wasteful_lines,
            claimed_total=wasteful_total,
            agent_address=dummy_agent_addr,
            quotes_metadata=quotes_meta,
            requirements=requirements,
            eligible_quotes=allowed_quotes,
        )

        assert w_approved is False, "Waste Guard should have rejected wasteful candidate!"
        assert w_decision["reasonCode"] == "WASTEFUL_BASKET"
        print(f"Wasteful basket REJECTED as expected: reasonCode={w_decision['reasonCode']}, detail={w_decision.get('detail')}")

        gate_results.append({
            "seed": s,
            "optimalCost": ref_opt.total_cost,
            "qpiaiExecutionMode": qpiai_res.execution_mode,
            "qpiaiStatus": qpiai_res.status,
            "greedyCost": greedy_res.total_cost,
            "savingsVsGreedyPct": comparison.savings_vs_greedy_pct,
            "vendorRuleCost": vendor_res.total_cost,
            "savingsVsVendorRulePct": comparison.savings_vs_vendor_rule_pct,
            "verifierDecision": decision["status"],
            "wastefulRejectionReason": w_decision["reasonCode"],
        })

    # Save evidence artifact
    output_path = "evidence/runs/phase2_gate.json"
    evidence_payload = {
        "gate": "PHASE_2_CATALOG_AND_OPTIMIZATION",
        "timestamp": time.time(),
        "status": "PASSED",
        "requirements": requirements,
        "runs": gate_results,
    }
    with open(output_path, "w") as f:
        json.dump(evidence_payload, f, indent=2)

    print(f"\nPhase 2 Gate PASSED! Evidence written to {output_path}")


if __name__ == "__main__":
    main()
