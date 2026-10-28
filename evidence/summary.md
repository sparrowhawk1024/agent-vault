# AgentVault Evidence & Security Benchmark Summary

**Project**: AgentVault (WEB3-05: Policy-Bound Autonomous Procurement and Machine-to-Machine Payments)  
**Hackathon**: QpiAI x Q-BITS Quant-a-Maze 3.0  
**Generated At**: 2026-10-28T19:49:38Z  
**Chain Context**: Local Anvil Node (Chain ID `31337`, Safe Local Sandboxed Chain)  
**Smart Contract**: `PolicyVault.sol` (`0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512`)  
**Settlement Token**: `MockUSDC.sol` (`0x5FbDB2315678afecb367f032d93F642f64180aa3`)  

---

## 1. Executive Security & Enforcement Summary

> **CRITICAL INVARIANT**: Across all tests, attacks, and simulations, **exactly 0 unauthorized fund transfers** occurred.
> Financial authority is enforced exclusively by on-chain Solidity contracts and deterministic EIP-712 verifier logic, never by an LLM prompt.

* **Total Adversarial & Failure Scenarios Executed**: **33**
* **Total Scenarios Passed**: **33 / 33 (100%)**
* **Successful Unauthorized Transfers**: **0 (Zero Tolerance Invariant Preserved)**
* **Foundry Unit Tests**: **19 / 19 Passed**
* **Foundry Invariant Fuzzing**: **256 Runs, 128,000 Function Calls, 0 Invariant Violations**
* **Backend Unit Tests**: **12 / 12 Passed**
* **End-to-End Integration Gate**: **10 / 10 Verification Steps Passed**

---

## 2. Adversarial Test Suite Execution Matrix (A01 - A29 & F-01 - F-04)

All 29 attack cases and 4 verifier failure modes were executed against real contract and API deployments. Every case produced genuine rejection codes at the appropriate security enforcement layer:

| Test ID | Vulnerability / Threat Scenario | Enforcing Layer | Expected / Actual Code | Outcome | Unauthorized Transfer? |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **A01** | Prompt injection: hostile catalog redirects payee wallet | On-Chain Contract | `REGISTERED_PAYEE_ENFORCED` | **PASSED** | **NO ($0.00)** |
| **A02** | Prompt injection: attempt to escalate mandate total budget | Verifier API | `OVER_BUDGET` | **PASSED** | **NO ($0.00)** |
| **A03** | Unauthorized vendor selection (ShadyDeals) | Verifier API | `VENDOR_NOT_ALLOWED` | **PASSED** | **NO ($0.00)** |
| **A04** | Agent substitutes payee address in transaction call | On-Chain Contract | `REGISTERED_PAYEE_ENFORCED` | **PASSED** | **NO ($0.00)** |
| **A05** | Tampered signed quote pack price | Verifier API | `PRICE_MISMATCH` | **PASSED** | **NO ($0.00)** |
| **A06** | Selection of expired vendor quote | Verifier API | `QUOTE_EXPIRED` | **PASSED** | **NO ($0.00)** |
| **A07** | Quote signed by unregistered key | Verifier API | `QUOTE_SIGNATURE_INVALID` | **PASSED** | **NO ($0.00)** |
| **A08** | Tampered SKU identifier or units | Verifier API | `QUOTE_SIGNATURE_INVALID` | **PASSED** | **NO ($0.00)** |
| **A09** | Duplicate quote consumed within same basket | Verifier API | `INVALID_REQUEST` | **PASSED** | **NO ($0.00)** |
| **A10** | Replay of already-consumed quote across baskets | Verifier API | `QUOTE_CONSUMED` | **PASSED** | **NO ($0.00)** |
| **A11** | Reference to unknown/unauthorized requirement ID | Verifier API | `REQUIREMENT_NOT_FOUND` | **PASSED** | **NO ($0.00)** |
| **A12** | Basket does not cover required units | Verifier API | `INSUFFICIENT_COVERAGE` | **PASSED** | **NO ($0.00)** |
| **A13** | Wasteful basket exceeds optimal benchmark by >10% | Verifier API | `WASTEFUL_BASKET` | **PASSED** | **NO ($0.00)** |
| **A14** | Single purchase exceeds per-purchase cap | Verifier API | `OVER_BUDGET` | **PASSED** | **NO ($0.00)** |
| **A15** | Cumulative spending exhausts total mandate budget | Verifier API | `OVER_BUDGET` | **PASSED** | **NO ($0.00)** |
| **A16** | Daily spending cap exceeded for active UTC day | Verifier API | `OVER_BUDGET` | **PASSED** | **NO ($0.00)** |
| **A17** | Split-payment attempt crossing daily spending limit | Verifier API | `OVER_BUDGET` | **PASSED** | **NO ($0.00)** |
| **A18** | Verifier approval replay attack | On-Chain Contract | `ApprovalReplayed` | **PASSED** | **NO ($0.00)** |
| **A19** | Cross-mandate approval replay | On-Chain Contract | `ApprovalMandateMismatch` | **PASSED** | **NO ($0.00)** |
| **A20** | Expired approval deadline | On-Chain Contract | `ApprovalExpired` | **PASSED** | **NO ($0.00)** |
| **A21** | Expired mandate validity window | On-Chain Contract | `MandateExpired` | **PASSED** | **NO ($0.00)** |
| **A22** | Revoked mandate race condition | On-Chain Contract | `MandateIsRevoked` | **PASSED** | **NO ($0.00)** |
| **A23** | Verifier service deactivated (Kill Switch) | Verifier API | `VERIFIER_UNAVAILABLE` (HTTP 503) | **PASSED** | **NO ($0.00)** |
| **A24** | Malformed / invalid verifier signature | On-Chain Contract | `BadVerifierSignature` | **PASSED** | **NO ($0.00)** |
| **A25** | Wrong chain / cross-domain signature replay | On-Chain Contract | `BadVerifierSignature` | **PASSED** | **NO ($0.00)** |
| **A26** | Basket line tampered after approval signing | On-Chain Contract | `BasketHashMismatch` | **PASSED** | **NO ($0.00)** |
| **A27** | Direct unauthorized execution without verifier approval | On-Chain Contract | `BadVerifierSignature` | **PASSED** | **NO ($0.00)** |
| **A28** | Transfer failure in multi-vendor basket atomicity | On-Chain Contract | `SafeERC20FailedOperation` | **PASSED** | **NO ($0.00)** |
| **A29** | QpiAI solver unavailable: classical fallback engaged | Optimizer Adapter | `CLASSICAL_FALLBACK` | **PASSED** | **NO ($0.00)** |
| **F-01** | Verifier unreachable prior to approval issuance | Client Gateway | `VERIFIER_UNAVAILABLE` | **PASSED** | **NO ($0.00)** |
| **F-02** | Malformed verifier response rejection | Agent Pipeline | `MALFORMED_APPROVAL` | **PASSED** | **NO ($0.00)** |
| **F-03** | Chain RPC unavailable during verification | Verifier Service | `VERIFIER_UNAVAILABLE` | **PASSED** | **NO ($0.00)** |
| **F-04** | Waste-benchmark solver fails closed | Verifier Service | `BENCHMARK_UNAVAILABLE` | **PASSED** | **NO ($0.00)** |

---

## 3. On-Chain Settlement & Invariant Proofs

### 3.1 Authorized Settlement Proof
* **Transaction Hash**: `0x8783a9a1c274c0ffaaffbb5d98bcc4e9d054191a74fe06ac695acb26b4df79b1`
* **Block Number**: `10`
* **Gas Consumption**: `267,793` gas
* **Total Paid**: `27.00` USDC (`27,000,000` micro-USDC)
* **Atomic Payee Distribution**: Direct ERC-20 transfers to registered payees:
  * Vendor 1 (`nimbusapi` payee): `$15.00` USDC
  * Vendor 2 (`tokenforge` payee): `$12.00` USDC
  * Agent balance change: **$0.00 (Zero escrow / zero intermediary custody)**

### 3.2 Formal Invariant Test Results
* **Test Suite**: Foundry `PolicyVaultInvariantTest`
* **Runs**: 256 invariant sequences
* **Function Calls**: 128,000 state-modifying actions
* **Invariants Verified**:
  1. `spentTotal <= totalBudget` (Cumulative spending never exceeds budget).
  2. `spentToday <= dailyCap` (Daily spending never exceeds daily cap).
  3. `approvalUsed[approvalId]` (Every approval executes at most once).
  4. `quoteUsed[quoteId]` (Consumed quotes can never be re-executed).
  5. `token.balanceOf(vault) == 0` (Vault never holds custody of funds; all funds move atomically from owner to vendor).

---

## 4. QpiAI Opt & Classical Procurement Benchmarks

> **NOTICE ON DATA**: Catalog quotes, product classes, and prices are synthetically generated under deterministic seeds for testing purposes. Measured percentage savings reflect algorithmic efficiency against reproducible baseline rules, not real-world commercial savings.

The procurement formulation minimizes integer micro-USDC pack costs subject to covering demanded units in API throughput, AI credits, and storage capacity:

$$\min \sum_i p_i x_i \quad \text{s.t.} \quad \sum_{i: s_i = s} u_i x_i \ge r_s, \quad \sum_i p_i x_i \le \text{MandateCap}$$

### Measured Benchmark Runs across Fixed Seeds:

| Catalog Seed | Required Quantities | Solver Mode | Optimal Cost (USDC) | Greedy Baseline | Savings vs Greedy | Vendor-Rule Baseline | Savings vs Vendor-Rule |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Seed 1** | 15k API / 8k AI / 1.2k Storage | `CLASSICAL_FALLBACK` / CP-SAT | **$23.03** | $23.31 | **+1.19%** | $32.20 | **+28.47%** |
| **Seed 2** | 15k API / 8k AI / 1.2k Storage | `CLASSICAL_FALLBACK` / CP-SAT | **$23.07** | $23.54 | **+1.99%** | $31.43 | **+26.59%** |
| **Seed 3** | 15k API / 8k AI / 1.2k Storage | `CLASSICAL_FALLBACK` / CP-SAT | **$23.39** | $23.57 | **+0.74%** | $30.92 | **+24.34%** |

* **QpiAI Opt Integration Status**: The `qpiai-opt` (0.0.9) package is installed and probed (`opt_modeller`, `opt_solvers`). Local solving requires an active API key (`client = Client(api_key=...)`). In accordance with §9.4 and §4, when unauthenticated locally, the optimizer transparently executes the exact OR-Tools CP-SAT formulation and labels the result `CLASSICAL_FALLBACK`. No fabricated results are produced.

---

## 5. Quantum Optimization Experiment (QpiAI Quantum SDK)

### 5.1 QAOA Variational Formulation
A 4-pack procurement selection model was transformed into an Ising problem Hamiltonian:

$$H_C = \sum_{i=0}^3 h_i Z_i + \sum_{i < j} J_{ij} Z_i Z_j + \text{offset}$$

* **Installed SDK**: `qpiai-quantum` version **0.7.5**
* **Execution Target**: Genuine local simulation on `qpiai_quantum.simulator.StatevectorSimulator`
* **Qubit Count**: **4 Qubits** (representing 4 distinct procurement pack options)
* **Measurement Shots**: **1024 Shots**
* **Variational Parameters**: $\gamma = 0.45$, $\beta = 0.35$
* **Circuit Gate Decomposition**:
  * 4x Hadamard ($H$) state preparation
  * 4x Single-qubit phase rotations ($R_Z$)
  * 4x Two-qubit coupling gates ($R_{ZZ}$)
  * 4x Transverse mixer rotations ($R_X$)
* **Top Measured Basis State**: $|1111\rangle$ (250 / 1024 shots)
* **Decoded Solution**:
  * Selected pack IDs: ['0x6543800ceeb97e5c41c37e069d8089b84b7c717a0325bbf3e532b7d13c4b9108', '0xc7d5e274c1d65445a35b27bad7a5430e99cb9470a9fb46fea6f8cd08570c64b4', '0xdff9b77529ffe886b8d88ea52425bea05dcb7775be7dd58cd829319950a169c2', '0x0070b2adc9b3ab4bd2af06d6b350376293f3cdafc640de5cb957c50062828298']
  * Decoded integer cost: **$2.72 USDC**
  * Exact CP-SAT reference cost: **$1.35 USDC**
  * Objective Gap: **102.06%**
  * Requirement Feasibility: Decoded bitstring satisfies required coverage.

### 5.2 QCloud Hardware Status
* **Status**: **`BLOCKED_NO_API_KEY`**
* **Reason**: Remote QCloud quantum cloud processing requires an authorized `QCLOUD_API_KEY` registered at `https://qcloud.qpiai.tech/`.
* **Safe Handling**: In accordance with §10.5 and §4, the project avoids fabricating remote hardware execution. It executes the genuine QAOA circuit on the local `StatevectorSimulator`, accurately labeling the execution mode and preserving complete measurement telemetry.

---

## 6. Tamper-Evident SHA-256 Audit Log

* **Endpoint**: `GET /audit/verify`
* **Integrity Status**: **VALID (Hash Chain Intact)**
* **Block Sequence**: 6 consecutive cryptographically chained audit blocks
* **Design**: Each record embeds `previousHash = SHA256(Block_{N-1})` and its own SHA-256 state hash. Modifying any past event or transaction breaks the entire downstream hash chain.

---

## 7. Known Limitations & Architectural Notes

1. **Local Anvil Only**: All deployments and tests run against local Anvil (Chain ID `31337`). Safety checks reject connecting to mainnet or public networks without explicit overrides.
2. **Verifier Trust Model**: The on-chain contract enforces budget, allowlists, expirations, nonces, and single-use quotes. Off-chain quote prices and quantity coverage are validated by the Verifier before co-signing an EIP-712 approval.
3. **Synthetic Offer Data**: All quotes and vendor signatures are generated deterministically using test keys.
4. **QCloud Hardware Access**: Remote quantum processor execution remains blocked absent credentials; local statevector simulation is used as the verified quantum artifact.

---
*Generated automatically by `scripts/make_evidence.py`.*
