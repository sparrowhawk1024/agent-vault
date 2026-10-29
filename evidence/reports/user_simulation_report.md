# AgentVault User Simulation Study: 10 Randomized Persona Runs

> **Evaluation Track**: WEB3-05 · Policy-Bound Autonomous Procurement and Machine-to-Machine Payments
> **Tested Surface**: Simulated AI Chat Interface, Low-Balance Detection Triggers, and Autonomous x402 V2 Settlement

## 1. Executive Summary

- **Total Simulated User Sessions**: 10
- **Total Chat Interactions**: 22 turns
- **Average Chat Turn Latency**: 16.18 ms
- **Low-Balance Alert Success Rate**: **100.0%** (10/10 sessions correctly triggered popup threshold)
- **x402 V2 Settlement Success Rate**: **100.0%** (10/10 settlements confirmed on-chain)
- **Average x402 Settlement Latency**: 77.06 ms
- **Total Micro-USDC Paid**: $26.30 USDC
- **Total Credits Replenished**: +17,500 units
- **Policy & Adversarial Defenses Verified**: 3/3 blocked (Spend Cap Exceeded, Unapproved Vendor ShadyDeals, Tampered Signature)

## 2. Session-by-Session Performance Matrix

| Session | Persona | Preferred Package | Trigger % | Settlement Status | Amount | Credits Added | New Balance | Duration |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **DevOps Cloud Engineer** | `pack-tf-2k` | 12.0% | [SETTLED] | $3.00 | +2,000 | 2,600 (37.1%) | 454.4 ms |
| 2 | **Smart Contract Auditor** | `pack-tf-2k` | 12.0% | [SETTLED] | $3.00 | +2,000 | 2,600 (37.1%) | 402.24 ms |
| 3 | **Budget-Conscious Web3 Developer** | `pack-bb-1k` | 12.0% | [SETTLED] | $1.40 | +1,000 | 1,600 (26.7%) | 335.25 ms |
| 4 | **High-Frequency Agent Pipeline** | `pack-tf-10k` | 12.0% | [SETTLED] | $3.00 | +2,000 | 2,600 (37.1%) | 505.06 ms |
| 5 | **Micro-App Operator** | `pack-tf-500` | 12.0% | [SETTLED] | $0.90 | +500 | 1,100 (20.0%) | 304.11 ms |
| 6 | **Adversarial Red Team Tester** | `pack-shady-5k` | 12.0% | [SETTLED] | $3.00 | +2,000 | 2,600 (37.1%) | 352.36 ms |
| 7 | **Security Signature Tester** | `pack-tf-2k` | 12.0% | [SETTLED] | $3.00 | +2,000 | 2,600 (37.1%) | 334.96 ms |
| 8 | **Enterprise Procurement Manager** | `pack-tf-2k` | 12.0% | [SETTLED] | $3.00 | +2,000 | 2,600 (37.1%) | 341.75 ms |
| 9 | **Quantum Hybrid Research Fellow** | `pack-tf-2k` | 12.0% | [SETTLED] | $3.00 | +2,000 | 2,600 (37.1%) | 297.5 ms |
| 10 | **Continuous Autonomous Agent** | `pack-tf-2k` | 12.0% | [SETTLED] | $3.00 | +2,000 | 2,600 (37.1%) | 368.51 ms |

## 3. Adversarial and Policy Containment Verification

1. **Session 4 (Per-Refill Spend Cap Exceeded)**:
   - High-throughput agent requested a $12.00 top-up (`pack-tf-10k`).
   - Policy engine intercepted the request before settlement: `Amount $12.00 exceeds max spend per refill limit ($5.00)`.
   - Session recovered cleanly by purchasing the largest compliant package (`pack-tf-2k` at $3.00).
2. **Session 6 (Unapproved Vendor ShadyDeals)**:
   - Attacker attempted to purchase unverified package `pack-shady-5k` from vendor `0x616d...`.
   - Policy engine intercepted the request before signing and rejected with `Unapproved vendor: shadydeals`.
   - Session recovered cleanly by purchasing approved bundle `pack-tf-2k`.
3. **Session 7 (Tampered Cryptographic Payment)**:
   - Adversary simulated invalid signature payload.
   - x402 facilitator and contract rejected invalid signature (`Payment Required`).
   - Session re-executed with legitimate key and confirmed atomic settlement on-chain.

## 4. Next Steps for Real-Life Kaggle / GitHub Datasets

- **Kaggle Cloud Pricing Datasets**: Ingest real multi-cloud pricing tables (AWS EC2 Spot, Google Compute Engine, Azure VM instances) to replace synthetic catalog quotes.
- **GitHub LLM Token Benchmarks**: Ingest open-source model inference latency and pricing logs (e.g. LMSYS Chatbot Arena, HuggingFace Inference Endpoints) to drive empirical token consumption curves.
- **Real-World Policy Bounds**: Calibrate dynamic per-purchase caps using historical enterprise department spending distributions.
