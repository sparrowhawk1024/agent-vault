# AgentVault Assumptions and Environment Decisions

## Environment & Tooling
- **OS**: Windows 10/11 x64 (AMD64). PowerShell environment.
- **Python**: 3.12.10 in `.venv`.
- **Foundry**: Foundry v1.8.6 installed at `C:\Users\premc\.foundry\bin` (`forge`, `anvil`, `cast`).
- **Node.js**: v24.19.0 / npm 11.17.0.
- **QpiAI Packages**:
  - `qpiai-quantum` v0.7.5 installed and verified (`qpiai_quantum`).
  - `qpiai-opt` v0.0.9 installed and verified (`qpiai_opt`).
- **Local Chain**: Anvil local testnet on `http://127.0.0.1:8545` with chain ID 31337 and block time 1s (`--chain-id 31337 --block-time 1`).

## Protocol & Architectural Assumptions
- **Funding Model**: Vault holds no funds; pulls from the mandate owner via ERC-20 `transferFrom` using an allowance capped at the mandate's `totalBudget`.
- **Money Representation**: 6 decimals (micro-USDC) as strict integer arithmetic everywhere in the backend, verifier, and contract.
- **Time Sync**: Verifier and backend inject a Clock backed by the latest block timestamp from Anvil, preventing drift from wall clock.
- **Bundle Rebate Allocation**: Deterministic rebate applied to the lowest-sorted quote ID in the basket.
- **Daily Cap**: UTC day boundary (`block.timestamp / 1 days`).
- **Audit Log**: Tamper-evident SQLite database using SHA256 hash-chaining of canonical JSON representations.
