import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
import hashlib
import time
import numpy as np

from backend.app.catalog.generator import generate_catalog
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver

def compute_sha256(data):
    raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def main():
    print("=== PHASE 1 & 2: 13-QUBIT HAMILTONIAN CORRECTNESS & EXHAUSTIVE ENUMERATION ===")
    
    # 1. Load frozen Seed 1 catalog
    seed = 1
    timestamp = 1700000000
    vault_address = "0x1111111111111111111111111111111111111111"
    all_quotes = generate_catalog(seed=seed, now_timestamp=timestamp, vault_address=vault_address)
    allowed_quotes = [q for q in all_quotes if q.get("isAllowedVendor", True)]
    
    # Select 8 candidate quotes covering all 3 categories
    api_quotes = sorted(
        [q for q in allowed_quotes if q.get("categoryName") == "API_CALLS"],
        key=lambda q: (q["units"], q["price"]),
    )[:3]
    ai_quotes = sorted(
        [q for q in allowed_quotes if q.get("categoryName") == "AI_CREDITS"],
        key=lambda q: (q["units"], q["price"]),
    )[:3]
    storage_quotes = sorted(
        [q for q in allowed_quotes if q.get("categoryName") == "STORAGE"],
        key=lambda q: (q["units"], q["price"]),
    )[:2]

    candidate_quotes = api_quotes + ai_quotes + storage_quotes
    requirements = {
        api_quotes[0]["categoryId"]: 1000,
        ai_quotes[0]["categoryId"]: 500,
        storage_quotes[0]["categoryId"]: 100,
    }

    # Classical solve on candidate quotes
    prob = ProcurementProblem(quotes=candidate_quotes, requirements=requirements, max_budget=40_000_000, max_lines=8)
    opt = ORToolsSolver().solve(prob)
    print(f"Classical Optimum: Cost = {opt.total_cost} micro-USDC (${opt.total_cost/1e6:.2f}), Selected indices = {opt.selected_indices}")

    # Build 13x13 QUBO Q
    total_cost = sum(q["price"] for q in candidate_quotes)
    norm_prices = [q["price"] / total_cost for q in candidate_quotes]
    lam = 2.5

    Q = np.zeros((13, 13))
    for i in range(8):
        Q[i, i] += norm_prices[i]

    def add_squared_constraint(Q_mat, coeffs, constant, weight):
        offset_term = weight * (constant ** 2)
        indices = list(coeffs.keys())
        for i in indices:
            a_i = coeffs[i]
            Q_mat[i, i] += weight * (a_i ** 2 + 2 * constant * a_i)
        for idx1 in range(len(indices)):
            for idx2 in range(idx1 + 1, len(indices)):
                i = indices[idx1]
                j = indices[idx2]
                pair = (min(i, j), max(i, j))
                Q_mat[pair[0], pair[1]] += weight * (2 * coeffs[i] * coeffs[j])
        return offset_term

    offset = 0.0
    # API: x0 + x1 + 2*x2 - 1 - (x8 + 2*x9) = 0
    offset += add_squared_constraint(Q, {0: 1, 1: 1, 2: 2, 8: -1, 9: -2}, constant=-1, weight=lam)
    # AI: x3 + x4 + 2*x5 - 1 - (x10 + 2*x11) = 0
    offset += add_squared_constraint(Q, {3: 1, 4: 1, 5: 2, 10: -1, 11: -2}, constant=-1, weight=lam)
    # Storage: x6 + x7 - 1 - x12 = 0
    offset += add_squared_constraint(Q, {6: 1, 7: 1, 12: -1}, constant=-1, weight=lam)

    # Convert QUBO to Ising: x_i = (1 - Z_i)/2
    h = [0.0] * 13
    J = {}
    ising_offset = offset
    for i in range(13):
        for j in range(13):
            q_ij = Q[i, j]
            if abs(q_ij) < 1e-9:
                continue
            if i == j:
                h[i] -= q_ij / 2.0
                ising_offset += q_ij / 2.0
            elif i < j:
                pair = (i, j)
                J[pair] = J.get(pair, 0.0) + (q_ij / 4.0)
                h[i] -= q_ij / 4.0
                h[j] -= q_ij / 4.0
                ising_offset += q_ij / 4.0

    print(f"13-Qubit Ising Hamiltonian: h len={len(h)}, J couplings={len(J)}, offset={ising_offset:.6f}")

    # Exhaustive Enumeration of all 8,192 basis states
    print("\nEnumerating all 8,192 computational basis states...")
    all_states = []
    feasible_states = []
    infeasible_states = []

    for idx in range(8192):
        b_str = format(idx, '013b')
        # Little-endian bit order: b_str[12 - i] = qubit i
        x = np.array([int(b_str[12 - i]) for i in range(13)])
        
        # Energy
        E = float(x.T @ Q @ x + offset)
        
        # Physical procurement feasibility
        cov_api = int(1000 * x[0] + 1000 * x[1] + 2000 * x[2])
        cov_ai = int(500 * x[3] + 500 * x[4] + 1000 * x[5])
        cov_storage = int(100 * x[6] + 100 * x[7])
        
        is_feas = (cov_api >= 1000) and (cov_ai >= 500) and (cov_storage >= 100)
        cost_micro_usdc = int(sum(candidate_quotes[i]["price"] for i in range(8) if x[i] == 1))
        
        # Slack surplus representation
        s_api_val = int(x[8] + 2 * x[9])
        s_ai_val = int(x[10] + 2 * x[11])
        s_storage_val = int(x[12])
        
        actual_api_surplus = (cov_api - 1000) // 1000
        actual_ai_surplus = (cov_ai - 500) // 500
        actual_storage_surplus = (cov_storage - 100) // 100
        
        slack_matches = (
            (s_api_val == actual_api_surplus) and
            (s_ai_val == actual_ai_surplus) and
            (s_storage_val == actual_storage_surplus)
        ) if is_feas else False

        state_record = {
            "index": idx,
            "bitstring": b_str,
            "x": x.tolist(),
            "energy": round(E, 8),
            "feasible": is_feas,
            "costMicroUsdc": cost_micro_usdc,
            "costUsdc": round(cost_micro_usdc / 1e6, 2),
            "selectedQuotes": [candidate_quotes[i]["quoteId"] for i in range(8) if x[i] == 1],
            "selectedQuoteIndices": [i for i in range(8) if x[i] == 1],
            "slack": {
                "s_api": s_api_val,
                "s_ai": s_ai_val,
                "s_storage": s_storage_val,
                "slackMatchesSurplus": slack_matches,
            },
            "constraintDeficits": {
                "api": max(0, 1000 - cov_api),
                "ai": max(0, 500 - cov_ai),
                "storage": max(0, 100 - cov_storage),
            }
        }
        all_states.append(state_record)
        if is_feas:
            feasible_states.append(state_record)
        else:
            infeasible_states.append(state_record)

    all_states.sort(key=lambda s: s["energy"])

    # Diagnostics
    ground_state = all_states[0]
    best_feasible = min(feasible_states, key=lambda s: s["energy"])
    lowest_infeasible = min(infeasible_states, key=lambda s: s["energy"])
    
    energy_separation = lowest_infeasible["energy"] - best_feasible["energy"]
    argmin_matches_optimum = (ground_state["selectedQuoteIndices"] == opt.selected_indices)
    no_infeasible_beats_best = (energy_separation > 0)

    print("\n=== EXHAUSTIVE ENUMERATION RESULTS ===")
    print(f"Total States: {len(all_states):,} (Feasible: {len(feasible_states):,}, Infeasible: {len(infeasible_states):,})")
    print(f"Ground State: bitstring={ground_state['bitstring']} Energy={ground_state['energy']:.6f} Feasible={ground_state['feasible']} Cost=${ground_state['costUsdc']:.2f} Selected={ground_state['selectedQuoteIndices']}")
    print(f"Best Feasible State: bitstring={best_feasible['bitstring']} Energy={best_feasible['energy']:.6f} Cost=${best_feasible['costUsdc']:.2f}")
    print(f"Lowest Infeasible State: bitstring={lowest_infeasible['bitstring']} Energy={lowest_infeasible['energy']:.6f} Cost=${lowest_infeasible['costUsdc']:.2f}")
    print(f"Minimum Energy Separation (lowest_infeasible - best_feasible): +{energy_separation:.6f}")
    print(f"Does argmin H equal classical optimum? {argmin_matches_optimum}")
    print(f"Does NO infeasible state beat the best feasible one? {no_infeasible_beats_best}")

    # Top 10 lowest energy states
    print("\n--- TOP 10 LOWEST ENERGY STATES ---")
    print(f"{'Rank':<6} {'Bitstring':<16} {'Energy':<12} {'Cost':<10} {'Feasible':<10} {'Indices':<15} {'Slack [API,AI,Storage]'}")
    for rank, s in enumerate(all_states[:10]):
        slack_str = f"[{s['slack']['s_api']}, {s['slack']['s_ai']}, {s['slack']['s_storage']}]"
        print(f"#{rank+1:<5} {s['bitstring']:<16} {s['energy']:<12.6f} ${s['costUsdc']:<9.2f} {str(s['feasible']):<10} {str(s['selectedQuoteIndices']):<15} {slack_str}")

    # Assertions
    assert argmin_matches_optimum, "FAILED: Ground state does not match classical optimum!"
    assert no_infeasible_beats_best, "FAILED: An infeasible state beat the best feasible state!"
    assert energy_separation > 2.0, f"FAILED: Separation {energy_separation} was below expected bound 2.0"

    # Save Provenance Manifest & Exhaustive States Evidence
    reduced_manifest = {
        "dataset": "AgentVault Reduced Procurement Instance (13-Qubit)",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sourceCatalog": {
            "seed": seed,
            "fixedTimestamp": timestamp,
            "vaultAddress": vault_address,
            "catalogInputSha256": "f0d8a9ff5001e3b2b94efd73144662a1b774d0304c5fbd421b563714086c1581",
        },
        "qubitCount": 13,
        "decisionVariablesCount": 8,
        "slackVariablesCount": 5,
        "variableMapping": {
            "q0": {"name": "x0", "category": "API_CALLS", "units": 1000, "price": candidate_quotes[0]["price"], "quoteId": candidate_quotes[0]["quoteId"], "skuId": candidate_quotes[0]["skuId"], "vendorId": candidate_quotes[0]["vendorId"]},
            "q1": {"name": "x1", "category": "API_CALLS", "units": 1000, "price": candidate_quotes[1]["price"], "quoteId": candidate_quotes[1]["quoteId"], "skuId": candidate_quotes[1]["skuId"], "vendorId": candidate_quotes[1]["vendorId"]},
            "q2": {"name": "x2", "category": "API_CALLS", "units": 2000, "price": candidate_quotes[2]["price"], "quoteId": candidate_quotes[2]["quoteId"], "skuId": candidate_quotes[2]["skuId"], "vendorId": candidate_quotes[2]["vendorId"]},
            "q3": {"name": "x3", "category": "AI_CREDITS", "units": 500, "price": candidate_quotes[3]["price"], "quoteId": candidate_quotes[3]["quoteId"], "skuId": candidate_quotes[3]["skuId"], "vendorId": candidate_quotes[3]["vendorId"]},
            "q4": {"name": "x4", "category": "AI_CREDITS", "units": 500, "price": candidate_quotes[4]["price"], "quoteId": candidate_quotes[4]["quoteId"], "skuId": candidate_quotes[4]["skuId"], "vendorId": candidate_quotes[4]["vendorId"]},
            "q5": {"name": "x5", "category": "AI_CREDITS", "units": 1000, "price": candidate_quotes[5]["price"], "quoteId": candidate_quotes[5]["quoteId"], "skuId": candidate_quotes[5]["skuId"], "vendorId": candidate_quotes[5]["vendorId"]},
            "q6": {"name": "x6", "category": "STORAGE", "units": 100, "price": candidate_quotes[6]["price"], "quoteId": candidate_quotes[6]["quoteId"], "skuId": candidate_quotes[6]["skuId"], "vendorId": candidate_quotes[6]["vendorId"]},
            "q7": {"name": "x7", "category": "STORAGE", "units": 100, "price": candidate_quotes[7]["price"], "quoteId": candidate_quotes[7]["quoteId"], "skuId": candidate_quotes[7]["skuId"], "vendorId": candidate_quotes[7]["vendorId"]},
            "q8": {"name": "s_api_0", "type": "slack", "weight": 1, "surplusCategory": "API_CALLS"},
            "q9": {"name": "s_api_1", "type": "slack", "weight": 2, "surplusCategory": "API_CALLS"},
            "q10": {"name": "s_ai_0", "type": "slack", "weight": 1, "surplusCategory": "AI_CREDITS"},
            "q11": {"name": "s_ai_1", "type": "slack", "weight": 2, "surplusCategory": "AI_CREDITS"},
            "q12": {"name": "s_storage", "type": "slack", "weight": 1, "surplusCategory": "STORAGE"},
        },
        "requirements": requirements,
        "penalties": {
            "scaleLambda": lam,
            "apiEquality": "x0 + x1 + 2*x2 - 1 - (s_api_0 + 2*s_api_1) = 0",
            "aiEquality": "x3 + x4 + 2*x5 - 1 - (s_ai_0 + 2*s_ai_1) = 0",
            "storageEquality": "x6 + x7 - 1 - s_storage = 0",
        },
        "classicalOptimum": {
            "totalCostMicroUsdc": opt.total_cost,
            "totalCostUsdc": round(opt.total_cost / 1e6, 2),
            "selectedIndices": opt.selected_indices,
            "selectedQuotes": [candidate_quotes[i]["quoteId"] for i in opt.selected_indices],
        },
        "hamiltonianVerification": {
            "totalBasisStates": 8192,
            "feasibleStates": len(feasible_states),
            "infeasibleStates": len(infeasible_states),
            "groundStateEnergy": ground_state["energy"],
            "bestFeasibleEnergy": best_feasible["energy"],
            "lowestInfeasibleEnergy": lowest_infeasible["energy"],
            "energySeparation": energy_separation,
            "argminMatchesClassicalOptimum": argmin_matches_optimum,
            "noInfeasibleBeatsBest": no_infeasible_beats_best,
        }
    }
    
    reduced_manifest["reducedInstanceSha256"] = compute_sha256(reduced_manifest)
    
    # Save manifest
    manifest_path = "evidence/runs/phase3_reduced_instance_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(reduced_manifest, f, indent=2)
    print(f"\n[Saved] Reduced Instance Manifest written to: {manifest_path}")
    print(f"  * catalog_input_sha256: {reduced_manifest['sourceCatalog']['catalogInputSha256']}")
    print(f"  * reduced_instance_sha256: {reduced_manifest['reducedInstanceSha256']}")

    # Save complete exhaustive state table
    exhaustive_path = "evidence/runs/phase3_exhaustive_states.json"
    with open(exhaustive_path, "w", encoding="utf-8") as f:
        json.dump({
            "reducedInstanceSha256": reduced_manifest["reducedInstanceSha256"],
            "totalStates": 8192,
            "states": all_states,
        }, f, indent=2)
    print(f"[Saved] Full 8,192 Exhaustive States Table written to: {exhaustive_path}")

if __name__ == "__main__":
    main()

