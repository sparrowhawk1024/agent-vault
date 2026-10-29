import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
import time
import numpy as np
from scipy.optimize import minimize
import qpiai_quantum as qq
from qpiai_quantum import QpiAIQuantumAuth

from backend.app.catalog.generator import generate_catalog
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver
from scripts.validate_13qubit_hamiltonian import compute_sha256

def main():
    print("================================================================================")
    print("  PHASE 3: MULTI-START QAOA ANGLE OPTIMIZATION STUDY (p=1,2,3,4; 80 STARTS)")
    print("================================================================================\n")
    
    t_start_total = time.time()
    
    # Authenticate QCloud for local simulator
    qkey = os.environ.get("QCLOUD_API_KEY", "").strip()
    if qkey:
        QpiAIQuantumAuth.login(qkey)
        print(f"[Auth] QpiAI Quantum Auth verified: {QpiAIQuantumAuth.verify_api_key()}")

    # 1. Load manifest and problem instance
    with open("evidence/runs/phase3_reduced_instance_manifest.json") as f:
        manifest = json.load(f)

    # 8 candidate quotes
    all_quotes = generate_catalog(seed=1, now_timestamp=1700000000, vault_address="0x1111111111111111111111111111111111111111")
    allowed = [q for q in all_quotes if q.get("isAllowedVendor", True)]
    api_q = sorted([q for q in allowed if q.get("categoryName") == "API_CALLS"], key=lambda q: (q["units"], q["price"]))[:3]
    ai_q = sorted([q for q in allowed if q.get("categoryName") == "AI_CREDITS"], key=lambda q: (q["units"], q["price"]))[:3]
    storage_q = sorted([q for q in allowed if q.get("categoryName") == "STORAGE"], key=lambda q: (q["units"], q["price"]))[:2]
    candidate_quotes = api_q + ai_q + storage_q
    
    reqs = manifest["requirements"]
    classical_opt_cost = manifest["classicalOptimum"]["totalCostMicroUsdc"]
    classical_opt_indices = manifest["classicalOptimum"]["selectedIndices"]

    # Reconstruct 13-qubit QUBO and Ising
    total_cost = sum(q["price"] for q in candidate_quotes)
    norm_prices = [q["price"] / total_cost for q in candidate_quotes]
    lam = manifest["penalties"]["scaleLambda"]

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
    offset += add_squared_constraint(Q, {0: 1, 1: 1, 2: 2, 8: -1, 9: -2}, constant=-1, weight=lam)
    offset += add_squared_constraint(Q, {3: 1, 4: 1, 5: 2, 10: -1, 11: -2}, constant=-1, weight=lam)
    offset += add_squared_constraint(Q, {6: 1, 7: 1, 12: -1}, constant=-1, weight=lam)

    # Convert to Ising
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

    # Helper evaluators
    def bitstring_to_x(b_str):
        clean_b = b_str.replace(" ", "")
        return np.array([int(clean_b[12 - i]) for i in range(13)])

    def energy_of_x(x):
        return float(x.T @ Q @ x + offset)

    def is_feasible_x(x):
        cov_api = int(1000 * x[0] + 1000 * x[1] + 2000 * x[2])
        cov_ai = int(500 * x[3] + 500 * x[4] + 1000 * x[5])
        cov_storage = int(100 * x[6] + 100 * x[7])
        return (cov_api >= 1000) and (cov_ai >= 500) and (cov_storage >= 100)

    def cost_of_x(x):
        return int(sum(candidate_quotes[i]["price"] for i in range(8) if x[i] == 1))

    # Circuit builder
    def build_circuit(gammas, betas):
        p = len(gammas)
        circ = qq.Circuit(13)
        for q in range(13):
            circ.h(q)
        for l in range(p):
            g, b = gammas[l], betas[l]
            for q in range(13):
                if abs(h[q]) > 1e-6:
                    circ.rz(q, 2.0 * g * h[q])
            for (q1, q2), coeff in J.items():
                if abs(coeff) > 1e-6:
                    circ.rzz(q1, q2, 2.0 * g * coeff)
            for q in range(13):
                circ.rx(q, 2.0 * b)
        circ.measure_all()
        return circ

    # CVaR calculation with exact alpha=0.25 handling
    def compute_cvar(counts, alpha=0.25):
        total_shots = sum(counts.values())
        # Sort items by energy
        items = []
        for b, cnt in counts.items():
            e = energy_of_x(bitstring_to_x(b))
            items.append((e, cnt / total_shots))
        items.sort(key=lambda it: it[0])

        accum_p = 0.0
        weighted_e = 0.0
        for e, p in items:
            if accum_p + p <= alpha:
                weighted_e += p * e
                accum_p += p
            else:
                remaining = alpha - accum_p
                weighted_e += remaining * e
                accum_p = alpha
                break
        return weighted_e / alpha

    # Circuit runner
    def run_circuit_eval(gammas, betas, eval_shots=256):
        circ = build_circuit(gammas, betas)
        res = circ.run(shots=eval_shots, device_name="QpiAI-QSV-Local")
        cnts = res.get_counts()
        total = sum(cnts.values())
        exp_H = sum(c * energy_of_x(bitstring_to_x(b)) for b, c in cnts.items()) / total
        cvar_val = compute_cvar(cnts, alpha=0.25)
        return exp_H, cvar_val, cnts

    # 2. Multi-Start Parameter Search
    # Depths p in [1, 2, 3, 4]
    # 10 starts per depth for Expected Energy (<H>)
    # 10 starts per depth for CVaR (alpha=0.25)
    # Total: 80 starts
    all_trials_records = []
    best_configs = {} # (p, objective_type) -> best trial data

    print("[Phase 3.A] Launching 80 multi-start optimization runs...")
    start_count = 0

    for p in [1, 2, 3, 4]:
        for obj_type in ["EXPECTED_ENERGY", "CVAR"]:
            print(f"\n--- Depth p={p}, Objective: {obj_type} (10 Starts) ---")
            for trial_idx in range(1, 11):
                start_count += 1
                seed = p * 1000 + (1 if obj_type == "EXPECTED_ENERGY" else 2) * 100 + trial_idx
                rng = np.random.default_rng(seed)
                # Sample random initial angles in [0, pi]
                init_gammas = rng.uniform(0.1, 0.8, p).tolist()
                init_betas = rng.uniform(0.1, 0.8, p).tolist()
                init_params = init_gammas + init_betas

                # Loss function
                def objective_func(params):
                    gs = params[:p].tolist()
                    bs = params[p:].tolist()
                    e_h, cvar_h, _ = run_circuit_eval(gs, bs, eval_shots=256)
                    return e_h if obj_type == "EXPECTED_ENERGY" else cvar_h

                t_trial_0 = time.time()
                res = minimize(
                    objective_func,
                    init_params,
                    method="Nelder-Mead",
                    options={"maxiter": 6, "xatol": 0.08, "fatol": 0.08}
                )
                trial_runtime = time.time() - t_trial_0

                final_params = res.x.tolist()
                final_gammas = final_params[:p]
                final_betas = final_params[p:]
                final_loss = float(res.fun)

                trial_record = {
                    "startId": start_count,
                    "depth_p": p,
                    "objectiveType": obj_type,
                    "randomSeed": seed,
                    "initialGammas": [round(g, 4) for g in init_gammas],
                    "initialBetas": [round(b, 4) for b in init_betas],
                    "finalGammas": [round(g, 4) for g in final_gammas],
                    "finalBetas": [round(b, 4) for b in final_betas],
                    "optimizedObjectiveValue": round(final_loss, 4),
                    "iterations": int(res.nit),
                    "evaluations": int(res.nfev),
                    "terminationStatus": "CONVERGED" if res.success else "MAX_ITER_REACHED",
                    "runtimeSeconds": round(trial_runtime, 3),
                }
                all_trials_records.append(trial_record)

                print(f"  Start #{start_count:02d} (p={p}, {obj_type:<15}, seed={seed}): init={np.round(init_params, 2)} -> final={np.round(final_params, 2)} | Val={final_loss:.4f} ({trial_runtime:.2f}s)")

                # Track best
                key = (p, obj_type)
                if key not in best_configs or final_loss < best_configs[key]["optimizedObjectiveValue"]:
                    best_configs[key] = trial_record

    print(f"\n[Completed] All 80 optimization starts finished successfully.")

    # 3. Phase 3.B: Final Evaluation for 8 Best Configurations (1,024 shots each)
    print("\n[Phase 3.B] Performing final independent evaluation (1,024 shots) for 8 best configurations...")
    final_evaluation_results = []

    # Ground state bitstring(s) for degeneracy check
    ground_bitstrings = {"0000001001001"} # unique absolute minimum from exhaustive check

    for (p, obj_type), best_t in best_configs.items():
        gs = best_t["finalGammas"]
        bs = best_t["finalBetas"]
        t_eval_0 = time.time()
        circ = build_circuit(gs, bs)
        res_1024 = circ.run(shots=1024, device_name="QpiAI-QSV-Local")
        eval_runtime = time.time() - t_eval_0
        counts_1024 = res_1024.get_counts()

        # Compute metrics
        tot = sum(counts_1024.values())
        exp_H = sum(cnt * energy_of_x(bitstring_to_x(b)) for b, cnt in counts_1024.items()) / tot
        cvar_val = compute_cvar(counts_1024, alpha=0.25)
        
        # Ground state probability mass
        opt_state_mass = sum(counts_1024.get(b, 0) for b in ground_bitstrings) / tot
        
        # Most frequent bitstring
        sorted_counts = sorted(counts_1024.items(), key=lambda it: it[1], reverse=True)
        top_bitstring, top_shots = sorted_counts[0]
        top_x = bitstring_to_x(top_bitstring)
        top_cost = cost_of_x(top_x)
        top_feasible = is_feasible_x(top_x)

        # BEST FEASIBLE sampled basket across all 1,024 shots
        feasible_samples = [
            (b, cnt, cost_of_x(bitstring_to_x(b)), energy_of_x(bitstring_to_x(b)))
            for b, cnt in counts_1024.items()
            if is_feasible_x(bitstring_to_x(b))
        ]
        feasible_shots_total = sum(item[1] for item in feasible_samples)
        feasible_rate_pct = round((feasible_shots_total / tot) * 100.0, 2)

        if feasible_samples:
            # Sort by cost (lowest cost)
            feasible_samples.sort(key=lambda it: it[2])
            best_feas_b, best_feas_cnt, best_feas_cost, best_feas_energy = feasible_samples[0]
            best_feas_x = bitstring_to_x(best_feas_b)
            best_feas_indices = [i for i in range(8) if best_feas_x[i] == 1]
            optimality_gap_pct = round(((best_feas_cost - classical_opt_cost) / classical_opt_cost) * 100.0, 2)
        else:
            best_feas_b = "NONE"
            best_feas_cost = 0
            best_feas_indices = []
            optimality_gap_pct = 999.0

        eval_data = {
            "depth_p": p,
            "objectiveType": obj_type,
            "bestStartId": best_t["startId"],
            "seed": best_t["randomSeed"],
            "finalGammas": gs,
            "finalBetas": bs,
            "expectationH": round(exp_H, 4),
            "cvarH": round(cvar_val, 4),
            "optimalStateProbabilityMass": round(opt_state_mass, 6),
            "mostFrequentBitstring": top_bitstring,
            "mostFrequentShots": top_shots,
            "mostFrequentCostUsdc": round(top_cost / 1e6, 2),
            "mostFrequentFeasible": top_feasible,
            "bestFeasibleBitstring": best_feas_b,
            "bestFeasibleCostMicroUsdc": best_feas_cost,
            "bestFeasibleCostUsdc": round(best_feas_cost / 1e6, 2),
            "bestFeasibleSelectedIndices": best_feas_indices,
            "feasibleRatePct": feasible_rate_pct,
            "optimalityGapPct": optimality_gap_pct,
            "evalRuntimeSeconds": round(eval_runtime, 3),
            "totalShots": 1024,
            "topFiveBasisStates": sorted_counts[:5],
            "fullCounts": counts_1024,
        }
        final_evaluation_results.append(eval_data)
        print(f"  [p={p}, {obj_type:<15}] <H> = {exp_H:.4f} | CVaR = {cvar_val:.4f} | Feas Rate = {feasible_rate_pct}% | Best Feas Cost = ${best_feas_cost/1e6:.2f} (Gap: {optimality_gap_pct:+.2f}%)")

    # 4. Phase 3.C: Random Sampling Control (1,024 shots)
    print("\n[Phase 3.C] Evaluating Uniform Random Sampling Control Baseline...")
    rng_control = np.random.default_rng(42)
    random_bitstrings = [format(rng_control.integers(0, 8192), '013b') for _ in range(1024)]
    random_counts = {}
    for b in random_bitstrings:
        random_counts[b] = random_counts.get(b, 0) + 1

    rand_tot = 1024
    rand_exp_H = sum(cnt * energy_of_x(bitstring_to_x(b)) for b, cnt in random_counts.items()) / rand_tot
    rand_cvar = compute_cvar(random_counts, alpha=0.25)
    rand_opt_mass = sum(random_counts.get(b, 0) for b in ground_bitstrings) / rand_tot
    rand_feasible_samples = [
        (b, cnt, cost_of_x(bitstring_to_x(b)))
        for b, cnt in random_counts.items()
        if is_feasible_x(bitstring_to_x(b))
    ]
    rand_feas_shots = sum(item[1] for item in rand_feasible_samples)
    rand_feas_rate = round((rand_feas_shots / rand_tot) * 100.0, 2)
    rand_feasible_samples.sort(key=lambda it: it[2])
    rand_best_cost = rand_feasible_samples[0][2] if rand_feasible_samples else 0
    rand_gap_pct = round(((rand_best_cost - classical_opt_cost) / classical_opt_cost) * 100.0, 2)

    random_control_summary = {
        "method": "Uniform Random Sampling Baseline",
        "shots": 1024,
        "seed": 42,
        "expectationH": round(rand_exp_H, 4),
        "cvarH": round(rand_cvar, 4),
        "optimalStateProbabilityMass": round(rand_opt_mass, 6),
        "bestFeasibleCostMicroUsdc": rand_best_cost,
        "bestFeasibleCostUsdc": round(rand_best_cost / 1e6, 2),
        "feasibleRatePct": rand_feas_rate,
        "optimalityGapPct": rand_gap_pct,
    }
    print(f"  Random Control (1024 shots): <H> = {rand_exp_H:.4f} | CVaR = {rand_cvar:.4f} | Feas Rate = {rand_feas_rate}% | Best Feas Cost = ${rand_best_cost/1e6:.2f} (Gap: {rand_gap_pct:+.2f}%)")

    # 5. Save Artifact
    artifact_path = "evidence/runs/phase3_qaoa_multistart.json"
    study_payload = {
        "experiment": "QAOA_MULTISTART_OPTIMIZATION_STUDY",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "totalOptimizerStarts": len(all_trials_records),
        "qubitCount": 13,
        "evaluatedDepths": [1, 2, 3, 4],
        "objectiveVariants": ["EXPECTED_ENERGY", "CVAR_ALPHA_0_25"],
        "classicalReference": manifest["classicalOptimum"],
        "randomSamplingControl": random_control_summary,
        "bestConfigurationsFinalEvaluation": final_evaluation_results,
        "allOptimizationStarts": all_trials_records,
    }

    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(study_payload, f, indent=2)

    print(f"\n[Saved] Multi-Start QAOA Study Evidence written to: {artifact_path}")
    print(f"Total time elapsed: {time.time() - t_start_total:.2f}s")

if __name__ == "__main__":
    main()

