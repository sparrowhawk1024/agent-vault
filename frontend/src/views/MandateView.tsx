import React, { useState, useEffect } from 'react';
import { api, type MandateResponse } from '../api';
import { Shield, AlertTriangle, RefreshCw, Lock, ArrowRight, User } from 'lucide-react';

interface Props {
  activeMandateId: string;
  setActiveMandateId: (id: string) => void;
}

export const MandateView: React.FC<Props> = ({ activeMandateId, setActiveMandateId }) => {
  const [mandate, setMandate] = useState<MandateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // Form states for new mandate creation
  const [budgetUSDC, setBudgetUSDC] = useState(50);
  const [perPurchaseUSDC, setPerPurchaseUSDC] = useState(20);
  const [dailyCapUSDC, setDailyCapUSDC] = useState(30);

  const fetchMandate = async (id: string) => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMandate(id);
      setMandate(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch mandate');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeMandateId) {
      fetchMandate(activeMandateId);
    }
  }, [activeMandateId]);

  const handleCreateAndDeploy = async () => {
    setLoading(true);
    setActionMsg(null);
    setError(null);
    try {
      // 1. Prepare
      const prep = await api.prepareMandate({
        totalBudget: budgetUSDC * 1_000_000,
        perPurchaseCap: perPurchaseUSDC * 1_000_000,
        dailyCap: dailyCapUSDC * 1_000_000,
        nonce: Math.floor(Math.random() * 10000) + 1,
      });

      // 2. Sign (dev key demo)
      const signRes = await api.signMandateDev(prep.mandate);

      // 3. Create on-chain
      const createRes = await api.createMandate(prep.mandate, signRes.signature);
      
      setActiveMandateId(createRes.mandateId);
      setActionMsg(`Mandate successfully deployed on-chain! Tx: ${createRes.txHash.slice(0, 18)}...`);
      await fetchMandate(createRes.mandateId);
    } catch (err: any) {
      setError(err.message || 'Creation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async () => {
    if (!activeMandateId) return;
    setLoading(true);
    try {
      const res = await api.revokeMandate(activeMandateId);
      setActionMsg(`Mandate ${res.mandateId.slice(0, 12)}... REVOKED on-chain! Tx: ${res.txHash.slice(0, 18)}...`);
      await fetchMandate(activeMandateId);
    } catch (err: any) {
      setError(err.message || 'Revocation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield style={{ color: 'var(--accent-cyan)' }} size={24} />
            Mandate Policy & Spending Limits
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            EIP-712 cryptographic spending authority bound on-chain to PolicyVault
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => fetchMandate(activeMandateId)} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'glow-animation' : ''} />
            Refresh
          </button>
          {mandate?.isActive && (
            <button className="btn btn-danger btn-sm" onClick={handleRevoke} disabled={loading}>
              <AlertTriangle size={14} />
              Revoke Mandate
            </button>
          )}
        </div>
      </div>

      {actionMsg && (
        <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '12px 16px', borderRadius: '8px', color: '#6ee7b7', fontSize: '0.85rem' }}>
          {actionMsg}
        </div>
      )}

      {error && (
        <div style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', padding: '12px 16px', borderRadius: '8px', color: '#fda4af', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      {/* Metrics Row */}
      {mandate && (
        <div className="metrics-row">
          <div className="metric-box">
            <span className="metric-label">Status</span>
            <div style={{ marginTop: '4px' }}>
              {mandate.details.revoked ? (
                <span className="badge badge-red">Revoked On-Chain</span>
              ) : mandate.isActive ? (
                <span className="badge badge-green">Active & Authorized</span>
              ) : (
                <span className="badge badge-amber">Inactive</span>
              )}
            </div>
            <span className="metric-meta">Nonce: {mandate.details.nonce}</span>
          </div>

          <div className="metric-box">
            <span className="metric-label">Total Budget</span>
            <span className="metric-value">{(mandate.details.totalBudget / 1_000_000).toFixed(2)} USDC</span>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${Math.min(100, (mandate.details.spentTotal / mandate.details.totalBudget) * 100)}%` }} 
              />
            </div>
            <span className="metric-meta">Spent: {(mandate.details.spentTotal / 1_000_000).toFixed(2)} USDC (Remaining: {(mandate.remainingTotalBudget / 1_000_000).toFixed(2)})</span>
          </div>

          <div className="metric-box">
            <span className="metric-label">Per-Purchase Cap</span>
            <span className="metric-value">{(mandate.details.perPurchaseCap / 1_000_000).toFixed(2)} USDC</span>
            <span className="metric-meta">Maximum single transaction limit</span>
          </div>

          <div className="metric-box">
            <span className="metric-label">Daily UTC Cap</span>
            <span className="metric-value">{(mandate.details.dailyCap / 1_000_000).toFixed(2)} USDC</span>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${Math.min(100, (mandate.details.spentToday / mandate.details.dailyCap) * 100)}%`, background: 'linear-gradient(90deg, #a855f7, #00f2fe)' }} 
              />
            </div>
            <span className="metric-meta">Spent Today: {(mandate.details.spentToday / 1_000_000).toFixed(2)} USDC</span>
          </div>
        </div>
      )}

      {/* Grid: Mandate Details + New Mandate Form */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '20px' }}>
        {/* Active Mandate Info */}
        <div className="glass-card">
          <div className="card-title">
            <Lock size={18} style={{ color: 'var(--accent-teal)' }} />
            Active Mandate Telemetry
          </div>
          <div className="card-subtitle">On-chain state queried from PolicyVault smart contract</div>

          {mandate ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Mandate ID (Hash Digest)</span>
                <div className="hash-tag" style={{ wordBreak: 'break-all', marginTop: '2px', padding: '6px' }}>{activeMandateId}</div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Creator (Owner)</span>
                  <div className="hash-tag" style={{ marginTop: '2px' }}>{mandate.details.creator.slice(0, 10)}...{mandate.details.creator.slice(-8)}</div>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Authorized Agent</span>
                  <div className="hash-tag" style={{ marginTop: '2px' }}>{mandate.details.agent.slice(0, 10)}...{mandate.details.agent.slice(-8)}</div>
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Validity Window</span>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  From: {new Date(mandate.details.validFrom * 1000).toLocaleString()}<br />
                  Until: {new Date(mandate.details.expiry * 1000).toLocaleString()}
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Allowed Categories & Vendors</span>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                  <span className="badge badge-cyan">API Calls</span>
                  <span className="badge badge-purple">AI Inference</span>
                  <span className="badge badge-green">Storage</span>
                  <span className="badge badge-amber">4 Verified Vendors</span>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No active mandate loaded. Enter or deploy a mandate below.
            </div>
          )}
        </div>

        {/* Deploy New Mandate */}
        <div className="glass-card">
          <div className="card-title">
            <User size={18} style={{ color: 'var(--accent-cyan)' }} />
            Configure & Deploy Mandate
          </div>
          <div className="card-subtitle">Authorize autonomous spending parameters with owner EIP-712 signature</div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                Total Mandate Budget (USDC)
              </label>
              <input 
                type="number" 
                className="form-input" 
                value={budgetUSDC} 
                onChange={(e) => setBudgetUSDC(Number(e.target.value))} 
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                  Per-Purchase Cap (USDC)
                </label>
                <input 
                  type="number" 
                  className="form-input" 
                  value={perPurchaseUSDC} 
                  onChange={(e) => setPerPurchaseUSDC(Number(e.target.value))} 
                />
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                  Daily Spending Cap (USDC)
                </label>
                <input 
                  type="number" 
                  className="form-input" 
                  value={dailyCapUSDC} 
                  onChange={(e) => setDailyCapUSDC(Number(e.target.value))} 
                />
              </div>
            </div>

            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                Existing Mandate ID Lookup
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input 
                  type="text" 
                  className="form-input" 
                  placeholder="0x..." 
                  value={activeMandateId}
                  onChange={(e) => setActiveMandateId(e.target.value)}
                />
                <button className="btn btn-secondary btn-sm" onClick={() => fetchMandate(activeMandateId)}>
                  Load
                </button>
              </div>
            </div>

            <button 
              className="btn btn-primary" 
              style={{ marginTop: '8px' }} 
              onClick={handleCreateAndDeploy}
              disabled={loading}
            >
              Sign & Deploy New Mandate On-Chain
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
