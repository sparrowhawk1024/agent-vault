import sys, os
sys.path.insert(0, os.path.abspath("."))
import numpy as np
from scipy.optimize import minimize
import qpiai_quantum as qq

# Import our test slack problem
from scripts.test_slack_instance import candidate_quotes, reqs, Q, offset, opt, norm_prices

# Convert QUBO Q (11x11) + offset to Ising Hamiltonian:
# x_i = (1 - Z_i) / 2
# H(x) = x^T Q x + offset
# Expanding:
# x_i x_j = (1 - Z_i)(1 - Z_j) / 4 = (1 - Z_i - Z_j + Z_i Z_j) / 4
# x_i^2 = x_i = (1 - Z_i) / 2
h = [0.0] * 11
J = {}
ising_offset = offset

for i in range(11):
    for j in range(11):
        q_ij = Q[i, j]
        if abs(q_ij) < 1e-9:
            continue
        if i == j:
            # q_ii * x_i = q_ii * (1 - Z_i) / 2
            h[i] -= q_ij / 2.0
            ising_offset += q_ij / 2.0
        elif i < j:
            # q_ij * x_i * x_j = q_ij * (1 - Z_i - Z_j + Z_i Z_j) / 4
            pair = (i, j)
            J[pair] = J.get(pair, 0.0) + (q_ij / 4.0)
            h[i] -= q_ij / 4.0
            h[j] -= q_ij / 4.0
            ising_offset += q_ij / 4.0

print(f"Ising formulation: {len(h)} qubits, {len(J)} coupling terms, offset={ising_offset:.4f}")

# Energy evaluator given bitstring b_str (q10..q0)
# b_str in QpiAI format: b_str[10 - i] is qubit i
def compute_energy_bitstring(b_str):
    x = np.array([int(b_str[10 - i]) for i in range(11)])
    return float(x.T @ Q @ x + offset)

def build_qaoa_circuit_p(h, J, gammas, betas):
    p = len(gammas)
    n = len(h)
    circ = qq.Circuit(n)
    # State prep
    for q in range(n):
        circ.h(q)
    # p layers
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

def evaluate_circuit_exp_H(gammas, betas, shots=1024):
    circ = build_qaoa_circuit_p(h, J, gammas, betas)
    res = circ.run(shots=shots, device_name="QpiAI-QSV-Local")
    counts = res.get_counts()
    total = sum(counts.values())
    exp_H = sum(cnt * compute_energy_bitstring(b) for b, cnt in counts.items()) / total
    return exp_H, counts

print("\nTesting single circuit execution with QpiAI Quantum...")
e0, cnt0 = evaluate_circuit_exp_H([0.1], [0.1], shots=256)
print(f"p=1 init [0.1, 0.1]: <H> = {e0:.4f}")

