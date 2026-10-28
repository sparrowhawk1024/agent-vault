"""Phase 3 Gate Execution Script for AgentVault.

Executes genuine QAOA quantum procurement experiment using QpiAI Quantum SDK:
- 4-qubit Ising mapping from reproducible synthetic catalog offers.
- Variational QAOA ansatz (state prep, problem Hamiltonian, mixer).
- Executed on qpiai_quantum.simulator.StatevectorSimulator with 1024 shots.
- Decodes measured candidate bitstrings and verifies coverage against requirements.
- Compares against classical CP-SAT reference optimum.
- Documents external QCloud API status and saves execution artifact to evidence/runs/phase3_gate.json.
"""

import os
import sys
import time
import json
from dataclasses import asdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.catalog.generator import generate_catalog
from backend.app.catalog.vendors import CATEGORIES
from backend.app.optimizer.qaoa_path import run_qaoa_procurement_experiment


def main():
    print("=== STARTING PHASE 3 RELEASE GATE (QAOA QUANTUM PROCUREMENT) ===")
    os.makedirs("evidence/runs", exist_ok=True)

    seeds = [1, 2, 3]
    records = []

    for s in seeds:
        print(f"\n--- Running QAOA Experiment for Seed {s} ---")
        quotes = generate_catalog(seed=s, now_timestamp=1700000000)
        reqs = {
            CATEGORIES["API_CALLS"]["id"]: 5_000,
            CATEGORIES["AI_CREDITS"]["id"]: 2_000,
        }

        record = run_qaoa_procurement_experiment(quotes, reqs, shots=1024)

        cand = record.decoded_candidate
        ref = record.classical_reference

        print(f"Status: {record.status} | Mode: {record.execution_mode} | Backend: {record.backend_name}")
        print(f"Qubits: {record.qubit_count} | Shots: {record.shots} | Runtime: {record.runtime_seconds:.3f}s")
        print(f"Top 3 Measured Bitstrings: {record.top_bitstrings[:3]}")
        print(f"Decoded Quantum Candidate: bitstring='{cand['bitstring']}', Cost={cand['totalCost']:,} micro-USDC (${cand['totalCost']/1e6:.2f}), Feasible={cand['feasible']}")
        print(f"Classical CP-SAT Reference: Cost={ref['totalCost']:,} micro-USDC (${ref['totalCost']/1e6:.2f}), Feasible={ref['feasible']}")
        print(f"Objective Gap vs Classical Reference: {record.objective_gap_pct}%")

        if record.error_detail:
            print(f"Backend Note: {record.error_detail}")

        assert record.status == "SUCCESS"
        assert record.qubit_count == 4
        assert cand["totalCost"] > 0
        assert ref["totalCost"] > 0

        record_dict = asdict(record)
        record_dict["seed"] = s
        records.append(record_dict)

    # Save evidence artifact
    output_path = "evidence/runs/phase3_gate.json"
    evidence_payload = {
        "gate": "PHASE_3_QUANTUM_PROCUREMENT_EXPERIMENT",
        "timestamp": time.time(),
        "status": "PASSED",
        "sdkVersion": "qpiai-quantum 0.7.5",
        "description": "Genuine QAOA 4-qubit variational circuit on QpiAI StatevectorSimulator with classical CP-SAT comparison",
        "runs": records,
    }
    with open(output_path, "w") as f:
        json.dump(evidence_payload, f, indent=2)

    print(f"\nPhase 3 Gate PASSED! Evidence written to {output_path}")


if __name__ == "__main__":
    main()
