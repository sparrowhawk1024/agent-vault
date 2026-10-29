import sys, os
sys.path.insert(0, os.path.abspath("."))
import numpy as np
from backend.app.catalog.generator import generate_catalog
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver

def test_slack_instance():
    quotes = generate_catalog(seed=1, now_timestamp=1700000000, vault_address="0x1111111111111111111111111111111111111111")
    allowed = [q for q in quotes if q.get("isAllowedVendor", True)]

    # 3 API quotes: 2 small (1000 units), 1 medium (2000 units)
    api_q = sorted([q for q in allowed if q.get("categoryName") == "API_CALLS"], key=lambda x: (x["units"], x["price"]))[:3]
    # 3 AI quotes: 2 small (500 units), 1 medium (1000 units)
    ai_q = sorted([q for q in allowed if q.get("categoryName") == "AI_CREDITS"], key=lambda x: (x["units"], x["price"]))[:3]
    # 2 Storage quotes: 2 small (100 units)
    storage_q = sorted([q for q in allowed if q.get("categoryName") == "STORAGE"], key=lambda x: (x["units"], x["price"]))[:2]

    # Total quotes = 3 + 3 + 2 = 8 quotes
    candidate_quotes = api_q + ai_q + storage_q
    # Requirements: API = 1000, AI = 500, Storage = 100
    reqs = {
        api_q[0]["categoryId"]: 1000,
        ai_q[0]["categoryId"]: 500,
        storage_q[0]["categoryId"]: 100,
    }

    # Plus 3 slack bits:
    # s_api for API surplus (0 or 1000)
    # s_ai for AI surplus (0 or 500)
    # s_storage for Storage surplus (0 or 100)
    # Total qubits = 8 + 3 = 11 qubits!

    print(f"=== CANDIDATE QUOTES (8 quotes + 3 slack bits = 11 qubits) ===")
    for i, q in enumerate(candidate_quotes):
        print(f"  q{i}: {q['categoryName']} units={q['units']} price={q['price']} (${q['price']/1e6:.2f})")
    print("Requirements:", reqs)

    # Classical solve on candidate quotes
    problem = ProcurementProblem(quotes=candidate_quotes, requirements=reqs, max_budget=40_000_000, max_lines=8)
    opt = ORToolsSolver().solve(problem)
    print(f"\nClassical Optimum Cost: {opt.total_cost} micro-USDC (${opt.total_cost/1e6:.2f})")
    print(f"Classical Selected Indices: {opt.selected_indices}")
    for idx in opt.selected_indices:
        print(f"  Selected: q{idx} ({candidate_quotes[idx]['categoryName']}) price={candidate_quotes[idx]['price']}")

    # Formulate QUBO / Ising:
    # Variables:
    # x0, x1, x2: API (units 1000, 1000, 2000) -> scaled: 1, 1, 2. Req = 1.
    # x3, x4, x5: AI (units 500, 500, 1000) -> scaled: 1, 1, 2. Req = 1.
    # x6, x7: Storage (units 100, 100) -> scaled: 1, 1. Req = 1.
    # x8: s_api (weight 1 or 2)
    # x9: s_ai (weight 1 or 2)
    # x10: s_storage (weight 1)
    
    # Let's verify constraint equations:
    # API: x0 + x1 + 2*x2 - 1 - s_api = 0.
    # Note: if x2=1, sum=2, surplus=1 => s_api=1 gives 2 - 1 - 1 = 0!
    # If x0=1, sum=1, surplus=0 => s_api=0 gives 1 - 1 - 0 = 0!
    # If x0=1 and x1=1, sum=2, surplus=1 => s_api=1 gives 2 - 1 - 1 = 0!
    # If all 0: sum=0 => min (0 - 1 - s)^2 is (-1)^2 = 1 (when s=0).
    
    # Similarly for AI:
    # x3 + x4 + 2*x5 - 1 - s_ai = 0.
    
    # Storage:
    # x6 + x7 - 1 - s_storage = 0.

    # Objective: Cost / max_cost
    # Choose penalty weight lambda:
    # Max feasible cost is sum of all quotes:
    total_max_cost = sum(q["price"] for q in candidate_quotes)
    norm_prices = [q["price"] / total_max_cost for q in candidate_quotes]
    
    # We want lambda > max possible cost difference:
    # Since norm_prices sum to 1.0, cost is in [0, 1.0].
    # Setting lambda = 2.0 guarantees that any penalty >= 1.0 (lambda * 1 = 2.0)
    # strictly exceeds any possible cost in the feasible region!
    lam = 2.5

    # QUBO matrix Q (11x11) where H(x) = x^T Q x
    Q = np.zeros((11, 11))
    
    # 1. Linear cost on quotes (indices 0..7)
    for i in range(8):
        Q[i, i] += norm_prices[i]
        
    # 2. Penalty API: lam * (x0 + x1 + 2*x2 - x8 - 1)^2
    # Expanding (w0 x0 + w1 x1 + w2 x2 - x8 - 1)^2:
    # = (sum a_i x_i - 1)^2 = sum a_i^2 x_i + 2 sum_{i<j} a_i a_j x_i x_j - 2 sum a_i x_i + 1
    # where a = {0: 1, 1: 1, 2: 2, 8: -1}
    def add_squared_constraint(Q, coeffs, constant, weight):
        # (sum a_i x_i + constant)^2
        # = sum a_i^2 x_i^2 + 2 sum_{i<j} a_i a_j x_i x_j + 2 * constant * sum a_i x_i + constant^2
        # Note: constant^2 is constant offset
        offset = weight * (constant ** 2)
        indices = list(coeffs.keys())
        for i in indices:
            a_i = coeffs[i]
            # linear term: a_i^2 * x_i + 2 * constant * a_i * x_i
            Q[i, i] += weight * (a_i ** 2 + 2 * constant * a_i)
        for idx1 in range(len(indices)):
            for idx2 in range(idx1 + 1, len(indices)):
                i = indices[idx1]
                j = indices[idx2]
                pair = (min(i, j), max(i, j))
                Q[pair[0], pair[1]] += weight * (2 * coeffs[i] * coeffs[j])
        return offset

    offset = 0.0
    offset += add_squared_constraint(Q, {0: 1, 1: 1, 2: 2, 8: -1}, constant=-1, weight=lam)
    offset += add_squared_constraint(Q, {3: 1, 4: 1, 5: 2, 9: -1}, constant=-1, weight=lam)
    offset += add_squared_constraint(Q, {6: 1, 7: 1, 10: -1}, constant=-1, weight=lam)

    print(f"\nOffset: {offset:.4f}")

    # Now brute-force all 2^11 = 2048 states!
    all_states = []
    opt_indices_set = set(opt.selected_indices)

    for idx in range(2048):
        b_str = format(idx, '011b')
        # x[i] for qubit i
        x = np.array([int(b_str[10 - i]) for i in range(11)])
        
        # Energy = x^T Q x + offset
        E = float(x.T @ Q @ x + offset)
        
        # Check actual procurement feasibility on candidate quotes x[0..7]
        cov_api = 1000 * x[0] + 1000 * x[1] + 2000 * x[2]
        cov_ai = 500 * x[3] + 500 * x[4] + 1000 * x[5]
        cov_storage = 100 * x[6] + 100 * x[7]
        
        is_feasible = (cov_api >= 1000) and (cov_ai >= 500) and (cov_storage >= 100)
        cost_actual = sum(candidate_quotes[i]["price"] for i in range(8) if x[i] == 1)
        
        all_states.append({
            "idx": idx,
            "b_str": b_str,
            "x": x.tolist(),
            "energy": E,
            "feasible": is_feasible,
            "cost": cost_actual,
        })

    all_states.sort(key=lambda s: s["energy"])

    # Analyze lowest energy states
    ground = all_states[0]
    print(f"\nGround state: idx={ground['idx']} Energy={ground['energy']:.6f} Feasible={ground['feasible']} Cost={ground['cost']}")
    print(f"Quotes selected: {[i for i in range(8) if ground['x'][i] == 1]}")
    print(f"Slack bits: s_api={ground['x'][8]}, s_ai={ground['x'][9]}, s_storage={ground['x'][10]}")

    # Verify: Does argmin H match classical optimum?
    ground_quotes = [i for i in range(8) if ground['x'][i] == 1]
    is_classical_opt = (ground_quotes == opt.selected_indices)
    print(f"\nDoes argmin H equal classical optimum? {is_classical_opt}")

    # Verify: Is every infeasible state strictly higher in energy than the ground state?
    feasible_states = [s for s in all_states if s["feasible"]]
    infeasible_states = [s for s in all_states if not s["feasible"]]
    
    min_infeasible_E = min(s["energy"] for s in infeasible_states)
    max_feasible_best_E = ground["energy"]
    
    print(f"\nFeasible states count: {len(feasible_states)}")
    print(f"Infeasible states count: {len(infeasible_states)}")
    print(f"Best feasible energy (Ground state): {max_feasible_best_E:.6f}")
    print(f"Lowest infeasible energy: {min_infeasible_E:.6f}")
    print(f"Energy gap (min_infeasible - best_feasible): {min_infeasible_E - max_feasible_best_E:.6f}")
    
    no_infeasible_beats_best = min_infeasible_E > max_feasible_best_E
    print(f"CHECK: Does no infeasible state beat the best feasible one? {no_infeasible_beats_best}")
    assert no_infeasible_beats_best, "FAILED: An infeasible state beat the best feasible state!"
    assert is_classical_opt, "FAILED: Ground state is not the classical optimum!"

if __name__ == "__main__":
    test_slack_instance()

