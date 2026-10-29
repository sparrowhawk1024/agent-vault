import React from 'react';
import { X, Lock, Cpu, Database, AlertTriangle, Info } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const ArchitecturePolicyModal: React.FC<Props> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(4, 6, 12, 0.85)',
      backdropFilter: 'blur(10px)',
      zIndex: 100,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
    }}>
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid rgba(0, 242, 254, 0.3)',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '860px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.7)',
        overflow: 'hidden'
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg-card-subtle)'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="badge badge-purple" style={{ fontSize: '0.75rem' }}>SYSTEM DISCLOSURE</span>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-main)' }}>
                AgentVault Architecture, Security Policy & Limitations (§Phase 4 & 5)
              </h3>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Cryptographic boundaries, on-chain economics, fail-closed defenses, and execution models
            </p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '20px', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
          
          {/* Section 1: Procurement Economics & Savings */}
          <div className="glass-card" style={{ padding: '16px' }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Cpu size={16} /> 1. Procurement Optimization & Economic Savings
            </h4>
            <p>
              Autonomous procurement uses integer linear programming (MILP) over combinatorial bundle offers. Across frozen Seed 1 benchmark inputs, AgentVault achieves an authentic <strong>28.47% cost reduction</strong> ($23.03 USDC optimal cost vs $32.20 USDC Vendor-Lock baseline and $24.16 USDC Greedy heuristic), while guaranteeing 100% requirement coverage without quantity deficit.
            </p>
          </div>

          {/* Section 2: On-Chain vs Off-Chain Data Privacy Boundaries */}
          <div className="glass-card" style={{ padding: '16px' }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-teal)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Database size={16} /> 2. On-Chain vs Off-Chain Privacy Boundaries
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginTop: '8px' }}>
              <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px 14px', borderRadius: '8px' }}>
                <strong style={{ color: 'var(--accent-purple)', display: 'block', marginBottom: '4px' }}>On-Chain (Publicly Verifiable):</strong>
                <ul style={{ paddingLeft: '16px', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <li>EIP-712 Mandate struct hashes & owner signatures</li>
                  <li>Verifier approval digests & verifier signatures</li>
                  <li>Canonical 32-byte basket hashes (`keccak256(quotes)`)</li>
                  <li>Atomic token transfer receipts & payee wallet credits</li>
                  <li>Spent accounting totals & cumulative daily caps</li>
                </ul>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px 14px', borderRadius: '8px' }}>
                <strong style={{ color: 'var(--accent-emerald)', display: 'block', marginBottom: '4px' }}>Off-Chain (Confidential & Private):</strong>
                <ul style={{ paddingLeft: '16px', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <li>Proprietary organizational requirement specs & quotas</li>
                  <li>Confidential vendor bid terms, pricing negotiations & text descriptions</li>
                  <li>Optimizer mathematical models, solver execution telemetry & logs</li>
                  <li>API keys, private keys & database credentials</li>
                  <li>Full raw Proof Bundle JSON records</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Section 3: Dual Cryptographic Signatures & Verification Protocol */}
          <div className="glass-card" style={{ padding: '16px' }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Lock size={16} /> 3. Dual Cryptographic Authorization & Non-Reversibility
            </h4>
            <p>
              Financial authority is strictly separated from LLM reasoning. The AI agent can propose, but cannot execute payments without two independent cryptographic gatekeepers:
            </p>
            <ol style={{ paddingLeft: '20px', marginTop: '6px', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li><strong>Owner EIP-712 Mandate</strong>: Binds max budget, per-purchase caps, daily caps, and allowlists on-chain.</li>
              <li><strong>Independent Verifier EIP-712 Approval</strong>: Deterministic verification service signs the basket hash only if all mandate rules, quote signatures, and WasteGuard constraints are met.</li>
            </ol>
            <p style={{ marginTop: '8px', fontSize: '0.78rem', color: 'var(--accent-amber)' }}>
              <strong>Non-Reversibility Notice:</strong> Once an authorized transaction settles on-chain, MockUSDC tokens move permanently to vendor wallets. Subsequent mandate revocation invalidates future spending attempts, but cannot retroactively reverse completed settlements.
            </p>
          </div>

          {/* Section 4: Token Monitor Tooling Distinction */}
          <div className="glass-card" style={{ padding: '16px', borderLeft: '4px solid var(--accent-indigo)' }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-indigo)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Info size={16} /> 4. Developer Token Monitor vs Procurement Metering (§Phase 4)
            </h4>
            <p>
              <strong>Important Architectural Distinction:</strong> The external "Token Monitor" utility in developer tooling monitors local AI coding-assistant token usage during development. It is <em>not</em> an AgentVault on-chain resource meter. AgentVault’s actual purchasing telemetry is measured through the trusted Requirement Store (`req-seed-01`) and canonical micro-USDC accounting.
            </p>
          </div>

          {/* Section 5: Current Limitations & QpiAI Hosted Execution */}
          <div className="glass-card" style={{ padding: '16px', borderLeft: '4px solid var(--accent-rose)' }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <AlertTriangle size={16} /> 5. Known Limitations & QpiAI Platform Execution Status
            </h4>
            <ul style={{ paddingLeft: '18px', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <li><strong>QpiAI Quantum QCloud</strong>: Authenticated successfully against live endpoints (<code>Auth.verify_api_key() == True</code>) and discovered 6 backends (<code>QpiAI-QSV-Simulator</code>, etc.). However, remote job dispatch is blocked by QCloud's active-subscription quota requirement (<code>HTTP 400</code>). Authentic quantum execution runs deterministically on local <code>QpiAI-QSV-Local</code> via <code>StatevectorSimulator</code>.</li>
              <li><strong>QpiAI Opt Platform</strong>: Local solving (`mode="local"`) via compiled HiGHS engine operates with optimal convergence. Hosted platform solving requires active organization storage quota for `.lp` file uploads.</li>
              <li><strong>Local Chain Deployment</strong>: Demonstrations execute on Anvil (chain ID 31337) with MockUSDC. This is a local testnet environment and does not involve real-money mainnet funds.</li>
            </ul>
          </div>
        </div>

        {/* Modal Footer */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'flex-end',
          background: 'var(--bg-card-subtle)'
        }}>
          <button className="btn btn-primary btn-sm" onClick={onClose}>
            Close Specification
          </button>
        </div>
      </div>
    </div>
  );
};
