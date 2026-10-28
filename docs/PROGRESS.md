# AgentVault Build Progress

- **Current Phase**: Phase 2 (Catalog and classical optimization) — **GATE PASSED**
- **Done**:
  - Saved complete master prompt (§0 through §15, Appendix A, Appendix B) to `docs/MASTER_PROMPT.md`.
  - Registered Appendix A workspace rule in `.agents/rules/agentvault.md` and `AGENTS.md`.
  - Completed Phase 0 (Environment and SDK execution probes, recorded in `evidence/runs/phase0_probe.json`).
  - Completed Phase 1 (Smart contract and verifier, recorded in `evidence/runs/phase1_gate.json`).
  - Completed Phase 2 (Catalog and classical optimization):
    - Implemented vendor registry (`backend/app/catalog/vendors.py`) with 5 vendors and deterministic key derivation matching `Deploy.s.sol`.
    - Implemented seeded synthetic catalog generator (`backend/app/catalog/generator.py`) producing ~50 signed quotes across 3 categories with volume discounts, near-expiry quotes, and adversarial prompt injections for `shadydeals`.
    - Implemented mathematical procurement model builder (`backend/app/optimizer/model_builder.py`) supporting `qpiai_opt.opt_modeller.Model`.
    - Implemented `ORToolsSolver` (CP-SAT exact integer solver) and `QpiAIOptSolver` (MILP with honest `CLASSICAL_FALLBACK` labeling).
    - Implemented `GreedyBaselineSolver` (effective unit price heuristic) and `VendorRuleBaselineSolver` (naive single-vendor policy).
    - Implemented `run_solver_comparison` (`backend/app/optimizer/selection.py`) computing runtimes, feasibility, and percentage savings against baselines.
    - Implemented independent `WasteGuard` (`backend/app/verifier/waste_guard.py`) and integrated it into `VerifierService`, checking integer optimum and rejecting wasteful baskets or failing closed on missing solver (F-04).
    - All 10 backend unit tests passing in `backend/tests/unit/`.
    - Executed Phase 2 Gate (`scripts/run_phase2_gate.py`):
      - Tested Seeds 1, 2, and 3: Optimal cost ~$23.03 - $23.39 USDC.
      - Naive vendor-rule baseline costs ~$30.92 - $32.20 USDC; optimal solver delivers 24.34% to 28.47% savings (exceeding 15% calibration target).
      - Verifier independently validated and approved the optimal candidate basket.
      - Verifier Waste Guard rejected an inflated candidate (+30%) with `WASTEFUL_BASKET`.
      - Saved gate evidence artifact to `evidence/runs/phase2_gate.json`.
- **In Progress**:
  - Phase 3: Quantum procurement experiment (QpiAI QCloud / Quantum SDK QAOA path).
- **Blockers**:
  - `QCLOUD_API_KEY`: Remote cloud execution requires QpiAI QCloud credentials. Will run the genuine QAOA variational circuit locally on `qpiai_quantum.simulator.StatevectorSimulator` and honestly record execution mode as `CLASSICAL_FALLBACK` / local simulator, documenting remote status.
- **Decisions**:
  - Added safe mock guard for `pandas` if blocked by Windows Application Control, allowing OR-Tools CP-SAT to execute without external native DLL dependency.
  - Used effective unit price `price / min(units, deficit)` in greedy heuristic to avoid knapsack lumpiness bias.
- **Hours Used**: 3.0 hours.
- **Next Three Actions**:
  1. Implement reduced procurement QUBO mapping and QAOA variational circuit in `backend/app/optimizer/qaoa_path.py`.
  2. Execute QAOA on `qpiai_quantum.simulator.StatevectorSimulator`, decode bitstrings to candidate offers, and compare with classical reference.
  3. Save quantum run evidence and circuit histogram artifacts to `evidence/runs/phase3_gate.json`.
