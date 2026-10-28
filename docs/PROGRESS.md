# AgentVault Build Progress

- **Current Phase**: Phase 0 (Environment and SDK execution probes) — **GATE PASSED**
- **Done**:
  - Saved complete master prompt (§0 through §15, Appendix A, Appendix B) to `docs/MASTER_PROMPT.md`.
  - Registered Appendix A as always-on workspace rule in `.agents/rules/agentvault.md` and `AGENTS.md`.
  - Pinned and verified Foundry v1.8.6 (`forge`, `anvil`, `cast`).
  - Discovered real APIs and signatures of `qpiai_opt` v0.0.9 and `qpiai_quantum` v0.7.5.
  - Executed Phase 0 probe (`scripts/phase0_probe.py`):
    - Formulated real procurement model with `qpiai_opt.opt_modeller.Model`.
    - Captured exact authentication blocker for `qpiai_opt.opt_solvers.solve` (`Local solving requires client=Client(api_key=...)`).
    - Evaluated classical reference benchmark (37 USDC).
    - Constructed 4-qubit QAOA variational circuit with $H, R_Z, R_{ZZ}, R_X$ and `measure_all()`.
    - Successfully executed circuit on `qpiai_quantum.simulator.StatevectorSimulator` in 1.29s (1024 shots).
    - Documented QCloud remote API key requirement.
  - Verified local Anvil node startup with `--chain-id 31337 --block-time 1` and `cast` queries.
  - Saved evidence to `evidence/runs/phase0_probe.json`.
  - Updated `docs/SDK_NOTES.md` and `docs/ASSUMPTIONS.md`.
- **In Progress**:
  - Transitioning to Phase 1: Smart contracts (Foundry) & Verifier core.
- **Blockers**:
  - `QPIAI_OPT_API_KEY` and `QCLOUD_API_KEY` are not set in `.env`.
    - As per Section 4 & Section 15: Exact external blocker is documented, local `StatevectorSimulator` executes quantum circuits as `LIVE_QPIAI`, and classical fallback (`CLASSICAL_FALLBACK` / OR-Tools) will serve as fallback when API key is missing.
- **Decisions**:
  - QpiAI Quantum gate operations use exact parameter orders: `rz(qubit, theta)`, `rzz(qubit1, qubit2, theta)`, `rx(qubit, theta)`.
  - Opt solving requires handling `AuthenticationError` gracefully by defaulting to transparent classical optimization while marking the execution mode honestly.
- **Hours Used**: 1.0 hours.
- **Next Three Actions**:
  1. Initialize Foundry project under `contracts/` with pinned OpenZeppelin v5.1.0 contracts.
  2. Implement `MockUSDC.sol` and `PolicyVault.sol` (EIP-712 domain, vendor registry, createMandate, executeBasket with single-use quotes, verifier signature verification, daily/per-purchase caps, nonReentrant).
  3. Write comprehensive Foundry tests (`contracts/test/PolicyVault.t.sol`) covering happy path, authority, budget caps, replay, revocation, and failure modes.
