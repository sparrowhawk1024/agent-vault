import React, { useState, useEffect } from 'react';
import { api, type ProofBundle } from '../api';
import { CreditCard, FileText, ChevronDown, ChevronRight, ShieldCheck } from 'lucide-react';

export const PaymentsView: React.FC = () => {
  const [proofs, setProofs] = useState<ProofBundle[]>([]);
  const [selectedProof, setSelectedProof] = useState<ProofBundle | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchProofs = async () => {
    try {
      const data = await api.getProofs();
      setProofs(data.reverse());
      if (data.length > 0 && !selectedProof) {
        setSelectedProof(data[0]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchProofs();
    const interval = setInterval(fetchProofs, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CreditCard style={{ color: 'var(--accent-cyan)' }} size={24} />
            On-Chain Payments & Purchase Proof Bundles
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Auditable transaction proofs linking off-chain requirements, verifier signatures, and on-chain settlements
          </p>
        </div>
        <span className="badge badge-cyan">{proofs.length} Proof Bundles Recorded</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '20px' }}>
        {/* Proof Bundles List */}
        <div className="glass-card">
          <div className="card-title">
            <FileText size={18} style={{ color: 'var(--accent-teal)' }} />
            Purchase Proof Records
          </div>
          <div className="card-subtitle">Select a bundle to inspect its full cryptographic trace</div>

          {proofs.length === 0 ? (
            <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)' }}>
              No purchase executions recorded yet. Run an agent procurement pipeline in View 2.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {proofs.map((p) => {
                const isSelected = selectedProof?.proofId === p.proofId;
                const isApproved = p.verifierDecision?.status === 'APPROVED';
                return (
                  <div
                    key={p.proofId}
                    onClick={() => setSelectedProof(p)}
                    style={{
                      padding: '14px 16px',
                      borderRadius: '10px',
                      background: isSelected ? 'rgba(0, 242, 254, 0.08)' : 'rgba(14, 19, 31, 0.6)',
                      border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span className="hash-tag">{p.proofId}</span>
                      <span className={`badge ${isApproved ? 'badge-green' : 'badge-red'}`}>
                        {isApproved ? 'Approved' : 'Rejected'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span>Amount: <strong>{(p.totalAmount / 1_000_000).toFixed(2)} USDC</strong></span>
                      <span style={{ color: 'var(--text-dim)', fontSize: '0.78rem' }}>
                        {new Date(p.timestamp * 1000).toLocaleTimeString()}
                      </span>
                    </div>
                    {p.onChainExecution?.txHash && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '4px' }}>
                        Tx: {p.onChainExecution.txHash.slice(0, 20)}...
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Selected Proof Bundle Details */}
        <div className="glass-card">
          <div className="card-title">
            <ShieldCheck size={18} style={{ color: 'var(--accent-emerald)' }} />
            Proof Bundle Inspector (§13.2)
          </div>
          <div className="card-subtitle">Complete cryptographic evidence trace for audit and reconciliation</div>

          {selectedProof ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Status Header */}
              <div style={{ 
                padding: '12px 16px', 
                borderRadius: '8px', 
                background: selectedProof.verifierDecision?.status === 'APPROVED' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
                border: `1px solid ${selectedProof.verifierDecision?.status === 'APPROVED' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 700 }}>
                    Verifier: {selectedProof.verifierDecision?.status} ({selectedProof.verifierDecision?.reasonCode})
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {selectedProof.verifierDecision?.detail || 'All constraints satisfied'}
                  </div>
                </div>
                <span className="badge badge-cyan">{selectedProof.telemetry.executionMode}</span>
              </div>

              {/* Hashes & IDs */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Requirement ID</span>
                  <div className="hash-tag" style={{ marginTop: '2px' }}>{selectedProof.requirementId}</div>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Mandate ID</span>
                  <div className="hash-tag" style={{ marginTop: '2px' }}>{selectedProof.mandateId.slice(0, 16)}...</div>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Canonical Basket Hash</span>
                  <div className="hash-tag" style={{ marginTop: '2px' }}>{selectedProof.basketHash.slice(0, 16)}...</div>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Approval ID</span>
                  <div className="hash-tag" style={{ marginTop: '2px' }}>
                    {selectedProof.approval?.approvalId ? `${selectedProof.approval.approvalId.slice(0, 16)}...` : 'None (Rejected)'}
                  </div>
                </div>
              </div>

              {/* Settlement Payees */}
              {selectedProof.onChainExecution?.payeeTransfers && selectedProof.onChainExecution.payeeTransfers.length > 0 && (
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>
                    Atomic Payee Settlements (Registered Wallets Only)
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {selectedProof.onChainExecution.payeeTransfers.map((t, idx) => (
                      <div key={idx} style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center', 
                        padding: '8px 12px', 
                        background: 'rgba(0,0,0,0.3)', 
                        borderRadius: '6px',
                        fontSize: '0.8rem'
                      }}>
                        <span><strong>{t.vendorId}</strong> ({t.payee.slice(0, 8)}...{t.payee.slice(-6)})</span>
                        <strong style={{ color: 'var(--accent-emerald)' }}>+{(t.amountMicroUSDC / 1_000_000).toFixed(2)} USDC</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Raw JSON Trace Accordion */}
              <div>
                <button 
                  className="btn btn-secondary btn-sm" 
                  style={{ width: '100%' }}
                  onClick={() => setExpandedId(expandedId ? null : selectedProof.proofId)}
                >
                  {expandedId ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  {expandedId ? 'Hide Raw Proof JSON' : 'View Full Cryptographic JSON Payload'}
                </button>
                {expandedId && (
                  <pre style={{ 
                    marginTop: '10px', 
                    padding: '12px', 
                    background: '#04060a', 
                    borderRadius: '8px', 
                    fontSize: '0.72rem', 
                    color: '#7dd3fc', 
                    overflowX: 'auto',
                    maxHeight: '300px'
                  }}>
                    {JSON.stringify(selectedProof, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>
              Select a proof record on the left to inspect its parameters.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
