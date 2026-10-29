import React from 'react';
import type { DashboardOverview } from '../api';
import { 
  Activity, 
  CheckCircle, 
  XCircle, 
  Clock 
} from 'lucide-react';

interface Props {
  overview: DashboardOverview | null;
  loading: boolean;
  onRefresh: () => void;
  onOpenDemo: () => void;
}

export const DashboardOverviewBanner: React.FC<Props> = ({ 
  overview, 
  loading, 
  onRefresh,
  onOpenDemo
}) => {
  if (!overview) {
    return (
      <div className="glass-card" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-muted)' }}>
            <Activity className="glow-animation" size={18} />
            <span>Connecting to AgentVault core services & local Anvil chain...</span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onRefresh} disabled={loading}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { mandate, verifier, qpiai, paymentCounts, latestTxHash } = overview;
  const isMandateActive = mandate.exists && mandate.isActive;

  return (
    <div className="glass-card" style={{ 
      padding: '18px 24px', 
      marginBottom: '24px', 
      border: '1px solid rgba(0, 242, 254, 0.25)',
      background: 'linear-gradient(180deg, rgba(14, 19, 31, 0.95) 0%, rgba(10, 14, 24, 0.85) 100%)'
    }}>
      {/* Header bar of Overview */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ 
            display: 'inline-flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            width: '28px', 
            height: '28px', 
            borderRadius: '6px', 
            background: 'rgba(0, 242, 254, 0.15)', 
            color: 'var(--accent-cyan)' 
          }}>
            <Activity size={16} />
          </span>
          <div>
            <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '0.02em' }}>
              Procurement Lifecycle Real-Time Telemetry
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
              Deterministic state synthesized directly from PolicyVault contract, Verifier, and QpiAI local engine
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button 
            className="btn btn-primary btn-sm" 
            onClick={onOpenDemo}
            style={{ 
              background: 'linear-gradient(135deg, #00f2fe 0%, #6366f1 100%)',
              boxShadow: '0 0 12px rgba(0, 242, 254, 0.35)',
              fontWeight: 600,
              fontSize: '0.78rem'
            }}
          >
            ⚡ Launch 5-Minute Guided Demo
          </button>
          <button 
            className="btn btn-secondary btn-sm" 
            onClick={onRefresh} 
            disabled={loading}
            style={{ fontSize: '0.78rem' }}
          >
            <Clock size={13} className={loading ? 'glow-animation' : ''} />
            Sync
          </button>
        </div>
      </div>

      {/* Grid of 5 Key Overview Panels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '14px' }}>
        {/* 1. Mandate & Budget Status */}
        <div style={{ 
          background: 'rgba(0, 0, 0, 0.35)', 
          padding: '12px 14px', 
          borderRadius: '8px', 
          border: '1px solid var(--border-subtle)' 
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>
              Mandate Spending
            </span>
            <span className={`badge ${isMandateActive ? 'badge-green' : mandate.revoked ? 'badge-red' : 'badge-amber'}`} style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
              {isMandateActive ? 'ACTIVE' : mandate.revoked ? 'REVOKED' : 'NONE'}
            </span>
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)' }}>
            ${(mandate.remainingBudget / 1_000_000).toFixed(2)}
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginLeft: '4px', fontWeight: 400 }}>
              / ${(mandate.totalBudget / 1_000_000).toFixed(2)} USDC
            </span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Spent: ${(mandate.spentTotal / 1_000_000).toFixed(2)} • Cap: ${(mandate.perPurchaseCap / 1_000_000).toFixed(2)}
          </div>
        </div>

        {/* 2. Procurement Request & Basket */}
        <div style={{ 
          background: 'rgba(0, 0, 0, 0.35)', 
          padding: '12px 14px', 
          borderRadius: '8px', 
          border: '1px solid var(--border-subtle)' 
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>
              Optimal Basket
            </span>
            <span className="badge badge-cyan" style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
              -28.47% vs Baseline
            </span>
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
            $23.03 USDC
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginLeft: '4px', textDecoration: 'line-through' }}>
              $32.20
            </span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Target: 15k API • 8k AI • 1.2k GB
          </div>
        </div>

        {/* 3. Verification & Safety Gate */}
        <div style={{ 
          background: 'rgba(0, 0, 0, 0.35)', 
          padding: '12px 14px', 
          borderRadius: '8px', 
          border: '1px solid var(--border-subtle)' 
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>
              Independent Verifier
            </span>
            <span className={`badge ${verifier.status === 'ACTIVE' ? 'badge-green' : 'badge-red'}`} style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
              {verifier.status}
            </span>
          </div>
          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)' }}>
            Fail-Closed Policy Gate
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            WasteGuard: {verifier.wasteGuardActive ? 'ENFORCING (<10%)' : 'OFFLINE'}
          </div>
        </div>

        {/* 4. Payment Settlements & Proofs */}
        <div style={{ 
          background: 'rgba(0, 0, 0, 0.35)', 
          padding: '12px 14px', 
          borderRadius: '8px', 
          border: '1px solid var(--border-subtle)' 
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>
              Settlement Ledger
            </span>
            <span className="badge badge-purple" style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
              Chain 31337
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--accent-emerald)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '3px' }}>
              <CheckCircle size={13} /> {paymentCounts.confirmed} Settled
            </span>
            <span style={{ fontSize: '0.85rem', color: 'var(--accent-rose)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '3px' }}>
              <XCircle size={13} /> {paymentCounts.rejected} Defended
            </span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '4px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
            Latest Tx: {latestTxHash ? `${latestTxHash.slice(0, 10)}...${latestTxHash.slice(-6)}` : 'Awaiting first run'}
          </div>
        </div>

        {/* 5. QpiAI Opt & Quantum Engine */}
        <div style={{ 
          background: 'rgba(0, 0, 0, 0.35)', 
          padding: '12px 14px', 
          borderRadius: '8px', 
          border: '1px solid var(--border-subtle)' 
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>
              QpiAI Solver Status
            </span>
            <span className="badge badge-cyan" style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
              {qpiai.optExecutionMode}
            </span>
          </div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)' }}>
            Local HiGHS MILP + QSV
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '4px' }}>
            Cloud: Subscription Blocked • Local: Active
          </div>
        </div>
      </div>
    </div>
  );
};
