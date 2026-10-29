import sys, os
sys.path.insert(0, os.path.abspath("."))
import time
import numpy as np
from scipy.optimize import minimize
import qpiai_quantum as qq

from backend.app.catalog.generator import generate_catalog
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver

def run_experiment():
    quotes = generate_catalog(seed=1, now_timestamp=1700000000, vault_address="0x1111111111111111111111111111111111111111")
    allowed = [q for q in quotes if q.get("isAllowedVendor", True)]

    # 3 API, 3 AI, 2 Storage
    api_q = sorted([q for q in allowed if q.get("categoryName") == "API_CALLS"], key=lambda x: (x["units"], x["price"]))[:3]
    ai_q = sorted([q for q in allowed if q.get("categoryName") == "AI_CREDITS"], key=lambda x: (x["units"], x["price"]))[:3]
    storage_q = sorted([q for q in allowed if q.get("categoryName") == "STORAGE"], key=lambda x: (x["units"], x["price"]))[:2]

    candidate_quotes = api_q + ai_q + storage_q
    reqs = {
        api_q[0]["categoryId"]: 1000,
        ai_q[0]["categoryId"]: 500,
        storage_q[0]["categoryId"]: 100,
    }

    # Classical reference
    prob = ProcurementProblem(quotes=candidate_quotes, requirements=reqs, max_budget=40_000_000, max_lines=8)
    opt = ORToolsSolver().solve(prob)
    print(f"Classical reference: cost={opt.total_cost} micro-USDC (${opt.total_cost/1e6:.2f}), indices={opt.selected_indices}")

    # Build QUBO
    total_max_cost = sum(q["price"] for q in candidate_quotes)
    norm_prices = [q["price"] / total_max_cost for q in candidate_quotes]
    lam = 2.5

    Q = np.zeros((11, 11))
    for i in range(8):
        Q[i, i] += norm_prices[i]

    def add_squared_constraint(Q, coeffs, constant, weight):
        offset = weight * (constant ** 2)
        indices = list(coeffs.keys())
        for i in indices:
            a_i = coeffs[i]
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

    # Convert to Ising
    h = [0.0] * 11
    J = {}
    ising_offset = offset
    for i in range(11):
        for j in range(11):
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

    # Helper functions
    def bitstring_to_x(b_str):
        # QpiAI convention: b_str[10 - i] is qubit i
        return np.array([int(b_str[10 - i]) for i in range(11)])

    def energy_of_x(x):
        return float(x.T @ Q @ x + offset)

    def is_feasible_x(x):
        cov_api = 1000 * x[0] + 1000 * x[1] + 2000 * x[2]
        cov_ai = 500 * x[3] + 500 * x[4] + 1000 * x[5]
        cov_storage = 100 * x[6] + 100 * x[7]
        return (cov_api >= 1000) and (cov_ai >= 500) and (cov_storage >= 100)

    def cost_of_x(x):
        return sum(candidate_quotes[i]["price"] for i in range(8) if x[i] == 1)

    # Theoretical values:
    all_energies = [energy_of_x(bitstring_to_x(format(idx, '011b'))) for idx in range(2048)]
    E_min = min(all_energies)
    E_uniform = np.mean(all_energies)

    print(f"\nTheoretical <H>_ground = {E_min:.4f}, <H>_uniform = {E_uniform:.4f}")

    # Build circuit
    def build_circuit(gammas, betas):
        p = len(gammas)
        circ = qq.Circuit(11)
        for q in range(11):
            circ.h(q)
        for l in range(p):
            g, b = gammas[l], betas[l]
            for q in range(11):
                if abs(h[q]) > 1e-6:
                    circ.rz(q, 2.0 * g * h[q])
            for (q1, q2), coeff in J.items():
                if abs(coeff) > 1e-6:
                    circ.rzz(q1, q2, 2.0 * g * coeff)
            for q in range(11):
                circ.rx(q, 2.0 * b)
        circ.measure_all()
        return circ

    def run_and_eval(gammas, betas, shots=1024):
        circ = build_circuit(gammas, betas)
        res = circ.run(shots=shots, device_name="QpiAI-QSV-Local")
        counts = res.get_counts()
        total = sum(counts.values())
        exp_H = sum(cnt * energy_of_x(bitstring_to_x(b)) for b, cnt in counts.items()) / total
        return exp_H, counts

    # 1. Random sample control (1024 shots)
    np.random.seed(42)
    random_bitstrings = [format(np.random.randint(0, 2048), '011b') for _ in range(1024)]
    random_counts = {}
    for b in random_bitstrings:
        random_counts[b] = random_counts.get(b, 0) + 1
    exp_H_random = sum(cnt * energy_of_x(bitstring_to_x(b)) for b, cnt in random_counts.items()) / 1024
    random_feasible = sum(random_counts[b] for b in random_counts if is_feasible_x(bitstring_to_x(b)))
    print(f"\n[Random Control] 1024 shots: <H> = {exp_H_random:.4f}, Feasible shots = {random_feasible}/1024 ({random_feasible/1024*100:.1f}%)")

    # 2. Angle optimization loop for p=1
    print("\n--- Optimizing p=1 QAOA angles ---")
    p1_history = []
    def loss_p1(params):
        g, b = params
        e, _ = run_and_eval([g], [b], shots=256)
        p1_history.append((g, b, e))
        return e

    # Nelder-Mead on small bounds
    res_p1 = minimize(loss_p1, [0.4, 0.4], method="Nelder-Mead", options={"maxiter": 15, "xatol": 0.05, "fatol": 0.05})
    opt_g1, opt_b1 = res_p1.x
    exp_H_p1, counts_p1 = run_and_eval([opt_g1], [opt_b1], shots=1024)
    p1_feasible = sum(counts_p1[b] for b in counts_p1 if is_feasible_x(bitstring_to_x(b)))
    sorted_p1 = sorted(counts_p1.items(), key=lambda x: x[1], reverse=True)
    top_p1_x = bitstring_to_x(sorted_p1[0][0])
    top_p1_cost = cost_of_x(top_p1_x)
    top_p1_feas = is_feasible_x(top_p1_x)
    print(f"p=1 Optimal angles: gamma={opt_g1:.4f}, beta={opt_b1:.4f}")
    print(f"p=1 Eval (1024 shots): <H> = {exp_H_p1:.4f}, Feasible shots = {p1_feasible}/1024 ({p1_feasible/1024*100:.1f}%)")
    print(f"p=1 Top state: {sorted_p1[0][0]} (shots={sorted_p1[0][1]}), Cost={top_p1_cost}, Feasible={top_p1_feas}")

    # 3. Angle optimization loop for p=2
    print("\n--- Optimizing p=2 QAOA angles ---")
    p2_history = []
    def loss_p2(params):
        g1, g2, b1, b2 = params
        e, _ = run_and_eval([g1, g2], [b1, b2], shots=256)
        p2_history.append((params, e))
        return e

    init_p2 = [opt_g1, 0.2, opt_b1, 0.2]
    res_p2 = minimize(loss_p2, init_p2, method="Nelder-Mead", options={"maxiter": 12, "xatol": 0.05, "fatol": 0.05})
    opt_g1_2, opt_g2_2, opt_b1_2, opt_b2_2 = res_p2.x
    exp_H_p2, counts_p2 = run_and_eval([opt_g1_2, opt_g2_2], [opt_b1_2, opt_b2_2], shots=1024)
    p2_feasible = sum(counts_p2[b] for b in counts_p2 if is_feasible_x(bitstring_to_x(b)))
    sorted_p2 = sorted(counts_p2.items(), key=lambda x: x[1], reverse=True)
    top_p2_x = bitstring_to_x(sorted_p2[0][0])
    top_p2_cost = cost_of_x(top_p2_x)
    top_p2_feas = is_feasible_x(top_p2_x)
    print(f"p=2 Optimal angles: gamma=[{opt_g1_2:.4f}, {opt_g2_2:.4f}], beta=[{opt_b1_2:.4f}, {opt_b2_2:.4f}]")
    print(f"p=2 Eval (1024 shots): <H> = {exp_H_p2:.4f}, Feasible shots = {p2_feasible}/1024 ({p2_feasible/1024*100:.1f}%)")
    print(f"p=2 Top state: {sorted_p2[0][0]} (shots={sorted_p2[0][1]}), Cost={top_p2_cost}, Feasible={top_p2_feas}")

    print("\n=== SUMMARY COMPARISON TABLE ===")
    print(f"{'Method':<25} {'Depth':<8} {'<H>':<10} {'Feasible Rate':<16} {'Top State Cost':<16}")
    print(f"{'Theoretical Ground':<25} {'N/A':<8} {E_min:<10.4f} {'100.0%':<16} {opt.total_cost:<16}")
    print(f"{'Theoretical Uniform':<25} {'N/A':<8} {E_uniform:<10.4f} {'57.4%':<16} {'N/A':<16}")
    print(f"{'Random Sample Control':<25} {'N/A':<8} {exp_H_random:<10.4f} {f'{random_feasible/1024*100:.1f}%':<16} {'N/A':<16}")
    print(f"{'QAOA p=1 Optimized':<25} {'p=1':<8} {exp_H_p1:<10.4f} {f'{p1_feasible/1024*100:.1f}%':<16} {top_p1_cost:<16}")
    print(f"{'QAOA p=2 Optimized':<25} {'p=2':<8} {exp_H_p2:<10.4f} {f'{p2_feasible/1024*100:.1f}%':<16} {top_p2_cost:<16}")

if __name__ == "__main__":
    run_experiment()

