# AgentVault Build Progress

- **Current Phase**: Phase 1 (Smart contract and verifier) — **GATE PASSED**
- **Done**:
  - Saved complete master prompt (§0 through §15, Appendix A, Appendix B) to `docs/MASTER_PROMPT.md`.
  - Registered Appendix A workspace rule in `.agents/rules/agentvault.md` and `AGENTS.md`.
  - Completed Phase 0 (Environment and SDK execution probes, recorded in `evidence/runs/phase0_probe.json`).
  - Completed Phase 1 (Smart contract and verifier):
    - Implemented `MockUSDC.sol` (6 decimals, test mint) and `PolicyVault.sol` (EIP-712, OpenZeppelin v5, nonReentrant, allowlists, daily/per-purchase caps, atomic transfers).
    - Implemented `FailingToken.sol` mock to test full revert atomicity.
    - Wrote comprehensive unit tests in `PolicyVault.t.sol` (19/19 tests passing).
    - Wrote handler invariant tests in `PolicyVault.invariant.t.sol` (256 runs, 128,000 calls, 0 violations).
    - Generated golden vectors via `GoldenVectors.s.sol` and proved byte-for-byte parity with Python in `test_typed_data_parity.py`.
    - Implemented `ChainClient` (`backend/app/chain/client.py`) and `VerifierService` (`backend/app/verifier/service.py`).
    - Executed Phase 1 gate (`scripts/run_phase1_gate.py`):
      - Deployed to local Anvil (`31337`).
      - Created on-chain mandate with owner signature (ID `0x98930f...`).
      - Executed authorized multi-vendor purchase ($27 USDC, tx `8783a9a1...`).
      - Validated token transfers (15 USDC to Vendor 1, 12 USDC to Vendor 2).
      - Verified real rejections: Verifier rejected non-allowlisted vendor (`VENDOR_NOT_ALLOWED`), contract reverted forged approval.
      - Saved proof artifact to `evidence/runs/phase1_gate.json`.
- **In Progress**:
  - Transitioning to Phase 2: Catalog and classical optimization.
- **Blockers**:
  - None for Phase 2.
- **Decisions**:
  - Enabled `via_ir = true` in Foundry to resolve stack depth while optimizing gas.
  - Used explicit `newTime = block.timestamp + 1 days` in rollover tests to prevent Yul compiler CSE on cheatcodes.
  - Verifier uses independent signing key and performs all on-chain and policy checks fail-closed.
- **Hours Used**: 2.0 hours.
- **Next Three Actions**:
  1. Build the seeded multi-vendor catalog generator (`backend/app/catalog/generator.py` and `vendors.py`).
  2. Implement QpiAI Opt MILP procurement formulation with greedy baseline, OR-Tools CP-SAT benchmark, and fallbacks.
  3. Implement verifier-side waste guard (`waste_guard.py`) and exact integer monetary recalculation.
