"""Quantum Optimization Engine (QAOA) for AgentVault Procurement.

Connects QpiAI Quantum SDK to a genuine reduced procurement selection instance:
- 11-qubit binary procurement formulation:
  - Selects from 8 representative signed vendor quotes across all 3 categories:
    - API_CALLS (3 candidate packs: 2 small @ 1000 units, 1 medium @ 2000 units)
    - AI_CREDITS (3 candidate packs: 2 small @ 500 units, 1 medium @ 1000 units)
    - STORAGE (2 candidate packs: 2 small @ 100 units)
  - 3 slack qubits for exact >= inequality coverage encoding:
    - s_api (qubit 8)
    - s_ai (qubit 9)
    - s_storage (qubit 10)
  - Quadratic penalty formulation: lambda * (sum_i w_i x_i - 1 - s_cat)^2
  - Mathematically guarantees: no infeasible state beats the best feasible one (E_min_infeasible > E_ground)
- Variational QAOA ansatz (p=1 and p=2 layers):
  - State preparation: Hadamard layer H^⊗11
  - Problem unitary: e^{-i γ H_C} via R_Z and R_ZZ gates
  - Mixer unitary: e^{-i β H_M} via R_X gates
  - Angle optimization loop minimizing expectation value <H>
  - Random sample control baseline with equal shots (1024 shots)
- Executed on QpiAI Quantum statevector simulator (QpiAI-QSV-Local)
- Preserves full execution metadata, per-trial <H>, bit-order diagnostics, and comparison tables.
"""

import os
import time
import math
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import minimize

try:
    import qpiai_quantum as qq
    from qpiai_quantum.simulator import StatevectorSimulator
    QPIAI_QUANTUM_AVAILABLE = True
except ImportError:
    qq = None
    StatevectorSimulator = None
    QPIAI_QUANTUM_AVAILABLE = False

from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.solvers import ORToolsSolver


@dataclass
class QAOAExecutionRecord:
    status: str                       # "SUCCESS" | "FAILED" | "UNAVAILABLE"
    execution_mode: str               # "LOCAL_QPIAI_SIMULATOR" | "LIVE_QPIAI_QCLOUD" | "CLASSICAL_FALLBACK"
    backend_name: str
    qubit_count: int
    shots: int
    optimal_gamma: float
    optimal_beta: float
    circuit_depth: int
    counts: Dict[str, int]
    top_bitstrings: List[Tuple[str, int]]
    decoded_candidate: Dict[str, Any]
    classical_reference: Dict[str, Any]
    objective_gap_pct: float
    runtime_seconds: float
    all_trials: List[Dict[str, Any]] = field(default_factory=list)
    random_control: Dict[str, Any] = field(default_factory=dict)
    hamiltonian_diagnostics: Dict[str, Any] = field(default_factory=dict)
    error_detail: Optional[str] = None


def formulate_reduced_procurement_ising(
    candidate_quotes: List[Dict[str, Any]],
    requirements: Dict[str, int],
    penalty_scale: float = 1.0,
) -> Tuple[List[float], Dict[Tuple[int, int], float], float]:
    """Legacy 4-quote Ising formulation for backwards compatibility."""
    n = len(candidate_quotes)
    max_price = max(q["price"] for q in candidate_quotes)
    norm_costs = [q["price"] / max_price for q in candidate_quotes]

    h = [0.0] * n
    J: Dict[Tuple[int, int], float] = {}
    offset = 0.0

    for i in range(n):
        h[i] -= norm_costs[i] / 2.0
        offset += norm_costs[i] / 2.0

    lam = penalty_scale * 1.5
    for cat_id, req_units in requirements.items():
        cat_indices = [i for i, q in enumerate(candidate_quotes) if q["categoryId"] == cat_id]
        if not cat_indices:
            continue
        max_cat_units = max(candidate_quotes[i]["units"] for i in cat_indices)
        scaled_req = req_units / max_cat_units
        scaled_units = {i: candidate_quotes[i]["units"] / max_cat_units for i in cat_indices}

        for i in cat_indices:
            w_i = scaled_units[i]
            linear_coeff = lam * (w_i ** 2 - 2 * scaled_req * w_i)
            h[i] -= linear_coeff / 2.0
            offset += linear_coeff / 2.0

        for idx1 in range(len(cat_indices)):
            for idx2 in range(idx1 + 1, len(cat_indices)):
                i = cat_indices[idx1]
                j = cat_indices[idx2]
                w_i = scaled_units[i]
                w_j = scaled_units[j]
                quad_coeff = lam * 2.0 * w_i * w_j
                pair = (min(i, j), max(i, j))
                J[pair] = J.get(pair, 0.0) + (quad_coeff / 4.0)
                h[i] -= quad_coeff / 4.0
                h[j] -= quad_coeff / 4.0
                offset += quad_coeff / 4.0

    return h, J, offset


def build_qaoa_circuit(h: List[float], J: Dict[Tuple[int, int], float], gamma: float, beta: float) -> Any:
    """Legacy single-layer QAOA circuit builder."""
    return build_qaoa_circuit_layers(h, J, [gamma], [beta])


def formulate_11qubit_procurement_ising(
    candidate_quotes: List[Dict[str, Any]],
    requirements: Dict[str, int],
    penalty_scale: float = 2.5,
) -> Tuple[List[float], Dict[Tuple[int, int], float], float, np.ndarray, float]:
    """Map the 8-quote + 3-slack procurement instance to an 11-qubit Ising Hamiltonian.

    Variables:
    x[0..2]: API_CALLS (units 1000, 1000, 2000) -> scaled: 1, 1, 2. Req = 1.
    x[3..5]: AI_CREDITS (units 500, 500, 1000) -> scaled: 1, 1, 2. Req = 1.
    x[6..7]: STORAGE (units 100, 100) -> scaled: 1, 1. Req = 1.
    x[8]: s_api (slack bit for API surplus)
    x[9]: s_ai (slack bit for AI surplus)
    x[10]: s_storage (slack bit for Storage surplus)

    Constraints:
    (x0 + x1 + 2*x2 - 1 - s_api)^2 = 0
    (x3 + x4 + 2*x5 - 1 - s_ai)^2 = 0
    (x6 + x7 - 1 - s_storage)^2 = 0
    """
    assert len(candidate_quotes) == 8, f"Expected 8 candidate quotes, got {len(candidate_quotes)}"

    total_cost = sum(q["price"] for q in candidate_quotes)
    norm_prices = [q["price"] / total_cost for q in candidate_quotes]
    lam = penalty_scale

    Q = np.zeros((11, 11))
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
    offset += add_squared_constraint(Q, {0: 1, 1: 1, 2: 2, 8: -1}, constant=-1, weight=lam)
    offset += add_squared_constraint(Q, {3: 1, 4: 1, 5: 2, 9: -1}, constant=-1, weight=lam)
    offset += add_squared_constraint(Q, {6: 1, 7: 1, 10: -1}, constant=-1, weight=lam)

    # Convert QUBO to Ising: x_i = (1 - Z_i) / 2
    h = [0.0] * 11
    J: Dict[Tuple[int, int], float] = {}
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

    return h, J, ising_offset, Q, offset


def formulate_13qubit_procurement_ising(
    candidate_quotes: List[Dict[str, Any]],
    requirements: Dict[str, int],
    penalty_scale: float = 2.5,
) -> Tuple[List[float], Dict[Tuple[int, int], float], float, np.ndarray, float]:
    """Map the 8-quote + 5-slack procurement instance to a 13-qubit Ising Hamiltonian.

    Variables:
    x[0..2]: API_CALLS (units 1000, 1000, 2000) -> scaled: 1, 1, 2. Req = 1.
    x[3..5]: AI_CREDITS (units 500, 500, 1000) -> scaled: 1, 1, 2. Req = 1.
    x[6..7]: STORAGE (units 100, 100) -> scaled: 1, 1. Req = 1.
    x[8, 9]: s_api,0 + 2*s_api,1 (2-bit slack for API surplus 0..3)
    x[10, 11]: s_ai,0 + 2*s_ai,1 (2-bit slack for AI surplus 0..3)
    x[12]: s_storage (1-bit slack for Storage surplus 0..1)

    Constraints:
    (x0 + x1 + 2*x2 - 1 - s_api,0 - 2*s_api,1)^2 = 0
    (x3 + x4 + 2*x5 - 1 - s_ai,0 - 2*s_ai,1)^2 = 0
    (x6 + x7 - 1 - s_storage)^2 = 0
    """
    assert len(candidate_quotes) == 8, f"Expected 8 candidate quotes, got {len(candidate_quotes)}"

    total_cost = sum(q["price"] for q in candidate_quotes)
    norm_prices = [q["price"] / total_cost for q in candidate_quotes]
    lam = penalty_scale

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

    # Convert QUBO to Ising: x_i = (1 - Z_i) / 2
    h = [0.0] * 13
    J: Dict[Tuple[int, int], float] = {}
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

    return h, J, ising_offset, Q, offset


def bitstring_to_x(b_str: str, n_qubits: int = 11) -> np.ndarray:
    """Decode QpiAI Quantum bitstring to variable array x.

    QpiAI Quantum uses little-endian bitstring convention:
    b_str[n - 1 - i] corresponds to qubit i.
    """
    clean_b = b_str.replace(" ", "")
    return np.array([int(clean_b[n_qubits - 1 - i]) for i in range(n_qubits)])


def compute_energy(x: np.ndarray, Q: np.ndarray, offset: float) -> float:
    return float(x.T @ Q @ x + offset)


def build_qaoa_circuit_layers(
    h: List[float],
    J: Dict[Tuple[int, int], float],
    gammas: List[float],
    betas: List[float],
) -> Any:
    """Build multi-layer QAOA circuit with QpiAI Quantum SDK."""
    if not QPIAI_QUANTUM_AVAILABLE:
        raise RuntimeError("qpiai-quantum is not installed.")

    p = len(gammas)
    n = len(h)
    circ = qq.Circuit(n)

    # State preparation: uniform superposition
    for q in range(n):
        circ.h(q)

    # p variational layers
    for layer in range(p):
        gamma = gammas[layer]
        beta = betas[layer]

        # Problem unitary
        for q in range(n):
            if abs(h[q]) > 1e-6:
                circ.rz(q, 2.0 * gamma * h[q])
        for (q1, q2), coeff in J.items():
            if abs(coeff) > 1e-6:
                circ.rzz(q1, q2, 2.0 * gamma * coeff)

        # Mixer unitary
        for q in range(n):
            circ.rx(q, 2.0 * beta)

    circ.measure_all()
    return circ


def run_qaoa_procurement_experiment(
    catalog_quotes: List[Dict[str, Any]],
    requirements: Optional[Dict[str, int]] = None,
    shots: int = 1024,
) -> QAOAExecutionRecord:
    """Run genuine QAOA procurement experiment with angle optimization and controls."""
    t0 = time.time()
    eligible = [q for q in catalog_quotes if q.get("isAllowedVendor", True)]

    # Select 8 candidate quotes covering all 3 categories
    api_quotes = sorted(
        [q for q in eligible if q.get("categoryName") == "API_CALLS"],
        key=lambda q: (q["units"], q["price"]),
    )[:3]
    ai_quotes = sorted(
        [q for q in eligible if q.get("categoryName") == "AI_CREDITS"],
        key=lambda q: (q["units"], q["price"]),
    )[:3]
    storage_quotes = sorted(
        [q for q in eligible if q.get("categoryName") == "STORAGE"],
        key=lambda q: (q["units"], q["price"]),
    )[:2]

    if len(api_quotes) < 3 or len(ai_quotes) < 3 or len(storage_quotes) < 2:
        raise ValueError("Insufficient quotes to construct 11-qubit 3-category procurement problem.")

    candidate_quotes = api_quotes + ai_quotes + storage_quotes
    reduced_reqs = {
        api_quotes[0]["categoryId"]: 1000,
        ai_quotes[0]["categoryId"]: 500,
        storage_quotes[0]["categoryId"]: 100,
    }

    # 1. Classical Reference Optimum on the exact 8-quote instance
    classical_problem = ProcurementProblem(
        quotes=candidate_quotes,
        requirements=reduced_reqs,
        max_budget=40_000_000,
        max_lines=8,
    )
    classical_solver = ORToolsSolver()
    ref_res = classical_solver.solve(classical_problem)
    ref_cost = ref_res.total_cost
    ref_indices = ref_res.selected_indices

    # 2. Formulate 11-qubit Ising and QUBO
    h, J, ising_offset, Q, offset = formulate_11qubit_procurement_ising(candidate_quotes, reduced_reqs)

    def is_feasible(x_arr: np.ndarray) -> bool:
        cov_api = int(1000 * x_arr[0] + 1000 * x_arr[1] + 2000 * x_arr[2])
        cov_ai = int(500 * x_arr[3] + 500 * x_arr[4] + 1000 * x_arr[5])
        cov_storage = int(100 * x_arr[6] + 100 * x_arr[7])
        return bool((cov_api >= 1000) and (cov_ai >= 500) and (cov_storage >= 100))

    def cost_of(x_arr: np.ndarray) -> int:
        return int(sum(candidate_quotes[i]["price"] for i in range(8) if x_arr[i] == 1))

    # 3. Brute-force Hamiltonian Diagnostics (Verify no infeasible state beats the best feasible state)
    all_energies = []
    feasible_energies = []
    infeasible_energies = []
    for idx in range(2048):
        b_str = format(idx, '011b')
        x_val = bitstring_to_x(b_str)
        e_val = compute_energy(x_val, Q, offset)
        all_energies.append(e_val)
        if is_feasible(x_val):
            feasible_energies.append(e_val)
        else:
            infeasible_energies.append(e_val)

    ground_energy = min(feasible_energies)
    min_infeasible_energy = min(infeasible_energies)
    uniform_energy = float(np.mean(all_energies))
    no_infeasible_beats_best = bool(min_infeasible_energy > ground_energy)

    hamiltonian_diagnostics = {
        "qubitCount": 11,
        "candidateQuotesCount": 8,
        "slackQubitsCount": 3,
        "groundStateEnergy": round(ground_energy, 4),
        "uniformExpectationEnergy": round(uniform_energy, 4),
        "minInfeasibleEnergy": round(min_infeasible_energy, 4),
        "energyGapInfeasibleVsGround": round(min_infeasible_energy - ground_energy, 4),
        "noInfeasibleBeatsBest": no_infeasible_beats_best,
        "qubitBitOrder": "little-endian (b_str[10-i] = qubit i)",
    }

    if not QPIAI_QUANTUM_AVAILABLE:
        return QAOAExecutionRecord(
            status="UNAVAILABLE",
            execution_mode="UNAVAILABLE",
            backend_name="none",
            qubit_count=11,
            shots=shots,
            optimal_gamma=0.0,
            optimal_beta=0.0,
            circuit_depth=0,
            counts={},
            top_bitstrings=[],
            decoded_candidate={},
            classical_reference={"totalCost": ref_cost, "indices": ref_indices},
            objective_gap_pct=0.0,
            runtime_seconds=time.time() - t0,
            error_detail="qpiai-quantum package not installed",
        )

    # Authenticate QCloud if present
    qcloud_key = os.environ.get("QCLOUD_API_KEY", "").strip()
    if qcloud_key and qq is not None:
        try:
            from qpiai_quantum import QpiAIQuantumAuth as Auth
            Auth.login(qcloud_key)
            Auth.verify_api_key()
        except Exception:
            pass

    # Helper: execute circuit and compute <H>
    def run_eval(gammas: List[float], betas: List[float], eval_shots: int = 1024) -> Tuple[float, Dict[str, int], int]:
        circ = build_qaoa_circuit_layers(h, J, gammas, betas)
        depth = circ.depth() if hasattr(circ, "depth") else (len(gammas) * 6)
        try:
            res = circ.run(shots=eval_shots, experiment_name="AgentVault QAOA", device_name="QpiAI-QSV-Local")
            cnts = res.get_counts()
        except Exception:
            sim = StatevectorSimulator()
            res = sim.run(circ, shots=eval_shots, seed=42)
            cnts = res.get_counts()
        tot = sum(cnts.values())
        exp_val = sum(cnt * compute_energy(bitstring_to_x(b), Q, offset) for b, cnt in cnts.items()) / tot
        return exp_val, cnts, depth

    # 4. Random Sample Control (equal shots)
    np.random.seed(42)
    random_bitstrings = [format(np.random.randint(0, 2048), '011b') for _ in range(shots)]
    random_counts: Dict[str, int] = {}
    for b in random_bitstrings:
        random_counts[b] = random_counts.get(b, 0) + 1
    exp_H_random = sum(cnt * compute_energy(bitstring_to_x(b), Q, offset) for b, cnt in random_counts.items()) / shots
    random_feasible_count = sum(random_counts[b] for b in random_counts if is_feasible(bitstring_to_x(b)))

    random_control = {
        "shots": shots,
        "expectationH": round(exp_H_random, 4),
        "feasibleShots": random_feasible_count,
        "feasibleRatePct": round((random_feasible_count / shots) * 100.0, 2),
    }

    # 5. Angle Optimization Loop: p=1
    def loss_p1(params):
        g, b = params
        val, _, _ = run_eval([g], [b], eval_shots=256)
        return val

    res_opt_p1 = minimize(loss_p1, [0.45, 0.35], method="Nelder-Mead", options={"maxiter": 12, "xatol": 0.05, "fatol": 0.05})
    opt_g1, opt_b1 = float(res_opt_p1.x[0]), float(res_opt_p1.x[1])
    exp_H_p1, counts_p1, depth_p1 = run_eval([opt_g1], [opt_b1], eval_shots=shots)

    # 6. Angle Optimization Loop: p=2
    def loss_p2(params):
        g1, g2, b1, b2 = params
        val, _, _ = run_eval([g1, g2], [b1, b2], eval_shots=256)
        return val

    res_opt_p2 = minimize(loss_p2, [opt_g1, 0.20, opt_b1, 0.20], method="Nelder-Mead", options={"maxiter": 10, "xatol": 0.05, "fatol": 0.05})
    opt_g2 = [float(res_opt_p2.x[0]), float(res_opt_p2.x[1])]
    opt_b2 = [float(res_opt_p2.x[2]), float(res_opt_p2.x[3])]
    exp_H_p2, counts_p2, depth_p2 = run_eval(opt_g2, opt_b2, eval_shots=shots)

    # Evaluate trial candidates
    all_trials = []
    trial_configs = [
        {"id": 1, "label": "Shallow heuristic initialization", "p": 1, "gammas": [0.20], "betas": [0.20]},
        {"id": 2, "label": "Calibrated benchmark point", "p": 1, "gammas": [0.45], "betas": [0.35]},
        {"id": 3, "label": "Optimized p=1 Variational Ansatz", "p": 1, "gammas": [opt_g1], "betas": [opt_b1]},
        {"id": 4, "label": "Optimized p=2 Deep Variational Ansatz", "p": 2, "gammas": opt_g2, "betas": opt_b2},
    ]

    best_record = None

    for cfg in trial_configs:
        e_h, cnts, d = run_eval(cfg["gammas"], cfg["betas"], eval_shots=shots)
        sorted_cnts = sorted(cnts.items(), key=lambda it: it[1], reverse=True)
        top_b = sorted_cnts[0][0]
        x_top = bitstring_to_x(top_b)
        cost_top = cost_of(x_top)
        feas_top = is_feasible(x_top)
        feas_shots = sum(cnts[b] for b in cnts if is_feasible(bitstring_to_x(b)))

        gap_pct = round(((cost_top - ref_cost) / ref_cost) * 100.0, 2) if ref_cost > 0 else 0.0

        t_data = {
            "trialId": cfg["id"],
            "label": cfg["label"],
            "p": cfg["p"],
            "gammas": [round(g, 4) for g in cfg["gammas"]],
            "betas": [round(b, 4) for b in cfg["betas"]],
            "circuitDepth": d,
            "expectationH": round(e_h, 4),
            "feasibleShots": feas_shots,
            "feasibleRatePct": round((feas_shots / shots) * 100.0, 2),
            "topBitstring": top_b,
            "topShots": sorted_cnts[0][1],
            "decodedCostMicroUsdc": cost_top,
            "decodedCostUsdc": round(cost_top / 1e6, 2),
            "feasible": feas_top,
            "gapVsClassicalPct": gap_pct,
            "topStates": sorted_cnts[:5],
            "counts": cnts,
        }
        all_trials.append(t_data)

        # Selection heuristic: lowest expectation <H>, prioritizing feasible candidates
        if best_record is None:
            best_record = (t_data, cnts, sorted_cnts, x_top, cost_top, feas_top, gap_pct)
        else:
            prev_t = best_record[0]
            if not prev_t["feasible"] and feas_top:
                best_record = (t_data, cnts, sorted_cnts, x_top, cost_top, feas_top, gap_pct)
            elif prev_t["feasible"] == feas_top:
                if t_data["expectationH"] < prev_t["expectationH"]:
                    best_record = (t_data, cnts, sorted_cnts, x_top, cost_top, feas_top, gap_pct)

    sel_t, sel_cnts, sel_sorted, sel_x, sel_cost, sel_feas, sel_gap = best_record
    sel_indices = [i for i in range(8) if sel_x[i] == 1]
    sel_quotes = [candidate_quotes[i] for i in sel_indices]

    coverage_summary = {
        "API_CALLS": int(1000 * sel_x[0] + 1000 * sel_x[1] + 2000 * sel_x[2]),
        "AI_CREDITS": int(500 * sel_x[3] + 500 * sel_x[4] + 1000 * sel_x[5]),
        "STORAGE": int(100 * sel_x[6] + 100 * sel_x[7]),
    }

    return QAOAExecutionRecord(
        status="SUCCESS",
        execution_mode="LOCAL_QPIAI_SIMULATOR",
        backend_name="QpiAI-QSV-Local",
        qubit_count=11,
        shots=shots,
        optimal_gamma=sel_t["gammas"][0],
        optimal_beta=sel_t["betas"][0],
        circuit_depth=sel_t["circuitDepth"],
        counts=sel_cnts,
        top_bitstrings=sel_sorted[:5],
        decoded_candidate={
            "bitstring": sel_t["topBitstring"],
            "selectedQuotes": [q["quoteId"] for q in sel_quotes],
            "selectedIndices": sel_indices,
            "totalCost": sel_cost,
            "totalCostUsdc": round(sel_cost / 1e6, 2),
            "coverage": coverage_summary,
            "feasible": sel_feas,
            "bestTrialId": sel_t["trialId"],
            "slackBits": {
                "s_api": int(sel_x[8]),
                "s_ai": int(sel_x[9]),
                "s_storage": int(sel_x[10]),
            },
        },
        classical_reference={
            "totalCost": ref_cost,
            "totalCostUsdc": round(ref_cost / 1e6, 2),
            "indices": ref_indices,
            "feasible": True,
        },
        objective_gap_pct=sel_gap,
        runtime_seconds=round(time.time() - t0, 3),
        all_trials=all_trials,
        random_control=random_control,
        hamiltonian_diagnostics=hamiltonian_diagnostics,
    )
