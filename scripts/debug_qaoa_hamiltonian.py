import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
from backend.app.catalog.generator import generate_catalog
from backend.app.optimizer.qaoa_path import formulate_reduced_procurement_ising
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver

def main():
    quotes = generate_catalog(seed=1, now_timestamp=1700000000, vault_address="0x1111111111111111111111111111111111111111")
    eligible = [q for q in quotes if q.get("isAllowedVendor", True)]
    api_quotes = sorted([q for q in eligible if q.get("categoryName") == "API_CALLS"], key=lambda q: q["units"])
    ai_quotes = sorted([q for q in eligible if q.get("categoryName") == "AI_CREDITS"], key=lambda q: q["units"])

    four_quotes = [api_quotes[0], api_quotes[1], ai_quotes[0], ai_quotes[1]]
    reduced_reqs = {
        api_quotes[0]["categoryId"]: min(api_quotes[0]["units"], api_quotes[1]["units"]),
        ai_quotes[0]["categoryId"]: min(ai_quotes[0]["units"], ai_quotes[1]["units"]),
    }

    print("=== FOUR QUOTES IN REDUCED 4-QUBIT INSTANCE ===")
    for i, q in enumerate(four_quotes):
        print(f"  q{i}: {q['categoryName']} (sku={q['skuId']}) units={q['units']} price={q['price']} micro-USDC (${q['price']/1e6:.2f})")
    print("\nRequirements:", reduced_reqs)

    # Classical solve
    problem = ProcurementProblem(quotes=four_quotes, requirements=reduced_reqs, max_budget=50_000_000, max_lines=4)
    opt = ORToolsSolver().solve(problem)
    print(f"\nClassical optimum cost: {opt.total_cost} micro-USDC (${opt.total_cost/1e6:.2f}), indices: {opt.selected_indices}")

    h, J, offset = formulate_reduced_procurement_ising(four_quotes, reduced_reqs)
    print("\nHamiltonian Parameters:")
    print("  h:", [round(x, 6) for x in h])
    print("  J:", {k: round(v, 6) for k, v in J.items()})
    print("  offset:", round(offset, 6))

    results = []
    for idx in range(16):
        # b_str is bitstring in QpiAI format: q3 q2 q1 q0
        b_str = format(idx, '04b')
        # Qubit bit-order: qubit 0 is rightmost bit (b_str[3]), qubit 3 is leftmost bit (b_str[0])
        x = [int(b_str[3 - i]) for i in range(4)]
        
        # Z_i = 1 - 2*x_i
        Z = [1 - 2 * x[i] for i in range(4)]
        
        # Energy E = sum h_i Z_i + sum J_ij Z_i Z_j + offset
        E = sum(h[i] * Z[i] for i in range(4))
        for (i, j), coeff in J.items():
            E += coeff * Z[i] * Z[j]
        E += offset
        
        cost = sum(four_quotes[i]["price"] for i in range(4) if x[i] == 1)
        
        cov = {cat: 0 for cat in reduced_reqs}
        for i in range(4):
            if x[i] == 1:
                cov[four_quotes[i]["categoryId"]] += four_quotes[i]["units"]
        feasible = all(cov[cat] >= req for cat, req in reduced_reqs.items())
        
        results.append({
            "bitstring": b_str,
            "x": x,
            "energy": E,
            "cost": cost,
            "feasible": feasible,
            "coverage": cov,
        })

    results.sort(key=lambda r: r["energy"])
    print("\n=== ALL 16 STATES SORTED BY ENERGY H ===")
    print(f"{'Bitstring(q3q2q1q0)':<20} {'x[q0..q3]':<14} {'Energy H':<14} {'Cost (µUSDC)':<15} {'Feasible':<10}")
    for r in results:
        x_str = f"[{r['x'][0]},{r['x'][1]},{r['x'][2]},{r['x'][3]}]"
        print(f"{r['bitstring']:<20} {x_str:<14} {r['energy']:<14.6f} {r['cost']:<15} {str(r['feasible']):<10}")

    # Check argmin H vs classical optimum
    argmin_state = results[0]
    opt_x = [1 if i in opt.selected_indices else 0 for i in range(4)]
    print("\n=== ARGMIN H VS CLASSICAL OPTIMUM ===")
    print(f"argmin H state: bitstring={argmin_state['bitstring']} x={argmin_state['x']} Energy={argmin_state['energy']:.6f} Cost={argmin_state['cost']} Feasible={argmin_state['feasible']}")
    print(f"Classical Opt : x={opt_x} Cost={opt.total_cost}")
    print(f"Does argmin H equal classical optimum? {argmin_state['x'] == opt_x}")

    # Now run QAOA simulation and compute <H> for sampled counts vs uniform distribution
    import qpiai_quantum as qq
    from backend.app.optimizer.qaoa_path import build_qaoa_circuit
    
    circ = build_qaoa_circuit(h, J, gamma=0.80, beta=0.50)
    res = circ.run(shots=1024, device_name="QpiAI-QSV-Local")
    counts = res.get_counts()
    
    energy_map = {r["bitstring"]: r["energy"] for r in results}
    
    # <H> sampled
    total_shots = sum(counts.values())
    exp_H_sampled = sum(counts[b] * energy_map[b] for b in counts) / total_shots
    
    # <H> uniform
    exp_H_uniform = sum(energy_map[format(idx, '04b')] for idx in range(16)) / 16.0
    
    print("\n=== EXPECTATION VALUE <H> ===")
    print(f"Sampled counts (gamma=0.80, beta=0.50): {counts}")
    print(f"<H>_sampled: {exp_H_sampled:.6f}")
    print(f"<H>_uniform: {exp_H_uniform:.6f}")
    print(f"<H>_ground_state (E_min): {argmin_state['energy']:.6f}")

if __name__ == "__main__":
    main()
