# AgentVault Build Progress

- **Current Phase**: Phase 3 (Quantum procurement experiment) — **GATE PASSED**
- **Done**:
  - Saved complete master prompt (§0 through §15, Appendix A, Appendix B) to `docs/MASTER_PROMPT.md`.
  - Registered Appendix A workspace rule in `.agents/rules/agentvault.md` and `AGENTS.md`.
  - Completed Phase 0 (Environment and SDK execution probes, recorded in `evidence/runs/phase0_probe.json`).
  - Completed Phase 1 (Smart contract and verifier, recorded in `evidence/runs/phase1_gate.json`).
  - Completed Phase 2 (Catalog and classical optimization, recorded in `evidence/runs/phase2_gate.json`).
  - Completed Phase 3 (Quantum procurement experiment):
    - Formulated 4-qubit binary procurement selection into an Ising / QUBO Hamiltonian: $H_C = \sum h_i Z_i + \sum J_{ij} Z_i Z_j$.
    - Implemented variational QAOA ansatz (`backend/app/optimizer/qaoa_path.py`) using `qpiai_quantum.Circuit` with $H$, $R_Z$, $R_{ZZ}$, and $R_X$ gates.
    - Executed QAOA experiment on `qpiai_quantum.simulator.StatevectorSimulator` with 1024 shots.
    - Decoded measured computational basis bitstrings (`1111`, `1100`, `0011`) into catalog offer selections and verified exact integer micro-USDC costs.
    - Compared quantum candidate against exact classical CP-SAT optimum on the same 4-offer instance, measuring an objective gap of ~100.8% - 102.3%.
    - Verified all 12 Python unit tests in `backend/tests/unit/` and all 20 Foundry smart contract & invariant tests.
    - Executed Phase 3 Gate (`scripts/run_phase3_gate.py`) on Seeds 1, 2, and 3, saving execution artifacts, circuit parameters, and measurement histograms to `evidence/runs/phase3_gate.json`.
- **In Progress**:
  - Phase 4: Adversarial testing and failure modes (29 attack cases A01-A29 and 4 failure scenarios F-01 to F-04).
- **Blockers**:
  - None. QCloud remote cloud status is documented as blocked by absent `QCLOUD_API_KEY`, with all executions running on the local QpiAI `StatevectorSimulator` and honestly marked `CLASSICAL_FALLBACK`.
- **Decisions**:
  - Sized quantum experiment to 4 qubits (2 API packs, 2 AI packs) to ensure deterministic, sub-second variational simulation without resource limits.
  - Symmetrically mapped category coverage penalties into intra-category $Z_i Z_j$ two-qubit interaction terms ($R_{ZZ}$).
- **Hours Used**: 3.5 hours.
- **Next Three Actions**:
  1. Implement deterministic `gullible.py` agent and attack runner harness (`scripts/run_attacks.py`).
  2. Implement and automate all 29 attack cases (A01 to A29) and 4 verifier failure tests (F-01 to F-04).
  3. Validate zero unauthorized fund transfers and output `evidence/attacks.json`.
