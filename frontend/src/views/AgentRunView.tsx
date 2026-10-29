import React, { useState, useEffect } from 'react';
import { api, type Requirement, type BenchmarkReport } from '../api';
import { Cpu, Zap, AlertOctagon, CheckCircle2, XCircle, ArrowRight, TrendingDown, Layers } from 'lucide-react';

interface Props {
  activeMandateId: string;
  onRefreshOverview?: () => void;
}

export const AgentRunView: React.FC<Props> = ({ activeMandateId, onRefreshOverview }) => {
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [selectedReqId, setSelectedReqId] = useState<string>('req-seed-01');
  const [agentMode, setAgentMode] = useState<'honest' | 'gullible'>('honest');
  const [attackType, setAttackType] = useState<string>('A01_PROMPT_INJECTION_REDIRECT');
  const [solverType, setSolverType] = useState<string>('qpiai');
  const [runSeed, setRunSeed] = useState<number>(1);
  
  const [benchmark, setBenchmark] = useState<BenchmarkReport | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getRequirements().then(setRequirements).catch(console.error);
  }, []);

  const runBenchmark = async () => {
    if (!selectedReqId) return;
    try {
      const bench = await api.optimize(selectedReqId, 1, activeMandateId);
      setBenchmark(bench);
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    if (selectedReqId) {
      runBenchmark();
    }
  }, [selectedReqId, activeMandateId]);

  const handleExecutePipeline = async (forceNewSeed: boolean = false) => {
    setRunning(true);
    setError(null);
    setResult(null);
    const targetSeed = forceNewSeed ? Math.floor(Date.now() / 1000) : runSeed;
    if (forceNewSeed) {
      setRunSeed(targetSeed);
    }
    try {
      const res = await api.runAgent({
        requirementId: selectedReqId,
        mandateId: activeMandateId,
        mode: agentMode,
        attackType: agentMode === 'gullible' ? attackType : undefined,
        solver: solverType,
        seed: targetSeed,
      });
      setResult(res);
      if (res.executed) {
        onRefreshOverview?.();
      }
    } catch (err: any) {
      setError(err.message || 'Pipeline execution failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu style={{ color: 'var(--accent-cyan)' }} size={24} />
            Autonomous Agent Procurement Engine
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            QpiAI Opt solver pipeline with independent Verifier gate and on-chain settlement
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <span className="badge badge-cyan">Port 8000 (Agent)</span>
          <span className="badge badge-purple">Port 8001 (Verifier)</span>
          <span className="badge badge-green">Chain ID 31337</span>
        </div>
      </div>

      {/* Control Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        {/* Requirement Selection */}
        <div className="glass-card" style={{ padding: '18px 20px' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
            1. Trusted Requirement
          </label>
          <select 
            className="form-select" 
            value={selectedReqId} 
            onChange={(e) => setSelectedReqId(e.target.value)}
          >
            {requirements.map((r) => (
              <option key={r.requirementId} value={r.requirementId}>
                {r.requirementId} — {r.description.slice(0, 40)}...
              </option>
            ))}
          </select>
          <div style={{ marginTop: '10px', fontSize: '0.78rem', color: 'var(--text-dim)', display: 'flex', gap: '10px' }}>
            <span>API: 30k calls</span>
            <span>•</span>
            <span>AI: 10k credits</span>
            <span>•</span>
            <span>Storage: 500 GB</span>
          </div>
        </div>

        {/* Agent Persona Mode Toggle */}
        <div className="glass-card" style={{ padding: '18px 20px' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
            2. Agent Behavioral Mode
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              className={`btn btn-sm ${agentMode === 'honest' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
              onClick={() => setAgentMode('honest')}
            >
              <Zap size={14} />
              Honest Autonomous Agent
            </button>
            <button 
              className={`btn btn-sm ${agentMode === 'gullible' ? 'btn-danger' : 'btn-secondary'}`}
              style={{ flex: 1 }}
              onClick={() => setAgentMode('gullible')}
            >
              <AlertOctagon size={14} />
              Gullible Attacker Agent
            </button>
          </div>
          {agentMode === 'gullible' && (
            <select 
              className="form-select" 
              style={{ marginTop: '10px', fontSize: '0.78rem' }}
              value={attackType}
              onChange={(e) => setAttackType(e.target.value)}
            >
              <option value="A01_PROMPT_INJECTION_REDIRECT">A01: Prompt Injection to Redirect Payment Address</option>
              <option value="A02_BUDGET_ESCALATION">A02: Malicious Budget Escalation Instruction</option>
              <option value="A03_UNAUTHORIZED_VENDOR">A03: Unauthorized Vendor Selection (ShadyDeals)</option>
              <option value="A05_TAMPERED_PRICE">A05: Tampered Quote Pack Price</option>
              <option value="A08_TAMPERED_QUANTITY">A08: Tampered Line Quantity / Units</option>
              <option value="A09_DUPLICATE_QUOTE">A09: Duplicate Quote Replay Within Basket</option>
            </select>
          )}
        </div>

        {/* Solver Selector */}
        <div className="glass-card" style={{ padding: '18px 20px' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
            3. Optimizer Engine Selection
          </label>
          <select 
            className="form-select" 
            value={solverType} 
            onChange={(e) => setSolverType(e.target.value)}
            disabled={agentMode === 'gullible'}
          >
            <option value="qpiai">QpiAI Opt MILP (Sponsor Engine)</option>
            <option value="ortools">OR-Tools CP-SAT (Classical Reference)</option>
            <option value="greedy">Greedy Unit-Price Heuristic</option>
            <option value="vendor_rule">Vendor-Lock Baseline</option>
          </select>
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
            <button 
              className="btn btn-primary" 
              style={{ flex: 1 }}
              onClick={() => handleExecutePipeline(true)}
              disabled={running}
              title="Generate fresh live quotes and execute atomic on-chain settlement"
            >
              {running ? 'Executing Pipeline...' : 'Run Live Order (Fresh Quotes)'}
              <ArrowRight size={15} />
            </button>
            <button 
              className="btn btn-secondary" 
              style={{ padding: '8px 12px', fontSize: '0.78rem' }}
              onClick={() => handleExecutePipeline(false)}
              disabled={running}
              title="Run with Seed 1 benchmark baseline"
            >
              Seed 1
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', padding: '14px 18px', borderRadius: '10px', color: '#fda4af', fontSize: '0.88rem' }}>
          {error}
        </div>
      )}

      {/* Execution Outcome Banner */}
      {result && (
        <div className="glass-card" style={{ 
          borderLeft: `5px solid ${result.approved ? 'var(--accent-emerald)' : 'var(--accent-rose)'}`,
          background: result.approved ? 'rgba(16, 185, 129, 0.08)' : 'rgba(244, 63, 94, 0.08)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {result.approved ? (
                <CheckCircle2 size={28} style={{ color: 'var(--accent-emerald)' }} />
              ) : (
                <XCircle size={28} style={{ color: 'var(--accent-rose)' }} />
              )}
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>
                  {result.approved ? 'Approved by Verifier & Settled On-Chain' : 'Rejected by Verifier — Security Boundary Enforced'}
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
                  Reason Code: <span className="hash-tag" style={{ color: result.approved ? '#6ee7b7' : '#fda4af' }}>{result.decision?.reasonCode}</span> • Detail: {result.decision?.detail || 'All checks passed'}
                </p>
                {!result.approved && (
                  <div style={{ marginTop: '8px' }}>
                    <button
                      className="btn btn-sm btn-primary"
                      onClick={async () => {
                        try {
                          await api.bootstrapMandate();
                          onRefreshOverview?.();
                          await handleExecutePipeline(true);
                        } catch (e: any) {
                          setError(e.message);
                        }
                      }}
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    >
                      Deploy Fresh $100 Mandate & Retry
                    </button>
                  </div>
                )}
              </div>
            </div>
            <div>
              {result.executed ? (
                <span className="badge badge-green">Tx Confirmed: {result.txHash.slice(0, 12)}...</span>
              ) : (
                <span className="badge badge-red">Zero Funds Moved</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Multi-Solver Benchmark Cards */}
      {benchmark && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <TrendingDown size={18} style={{ color: 'var(--accent-emerald)' }} />
              Procurement Solver Benchmarks vs Baselines (Seed 1)
            </h3>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Optimal Savings: <strong style={{ color: 'var(--accent-emerald)' }}>{benchmark.summary.savingsVsVendorRulePct}%</strong> vs Vendor-Rule
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px' }}>
            {Object.entries(benchmark.solvers).map(([key, s]) => (
              <div 
                key={key} 
                className="metric-box" 
                style={{ 
                  border: key === 'qpiai' ? '1px solid rgba(0, 242, 254, 0.4)' : '1px solid var(--border-subtle)',
                  background: key === 'qpiai' ? 'rgba(0, 242, 254, 0.05)' : undefined
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span className="metric-label">{s.solverName}</span>
                  <span className={`badge ${key === 'qpiai' ? 'badge-cyan' : key === 'ortools' ? 'badge-purple' : 'badge-amber'}`}>
                    {s.executionMode}
                  </span>
                </div>
                <span className="metric-value">{(s.totalCost / 1_000_000).toFixed(2)} USDC</span>
                <span className="metric-meta" style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px' }}>
                  <span>{s.lineCount} pack lines</span>
                  <span>{s.timingMs} ms</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Candidate Basket Lines Table */}
      {result?.proofBundle?.lines && (
        <div className="glass-card">
          <div className="card-title">
            <Layers size={18} style={{ color: 'var(--accent-teal)' }} />
            Selected Vendor Offers (Proposed Candidate Basket)
          </div>
          <div className="card-subtitle">Each line maps to a cryptographic quote signed by an allowlisted vendor</div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Quote ID</th>
                  <th>Vendor</th>
                  <th>Category</th>
                  <th>SKU</th>
                  <th>Units</th>
                  <th>Pack Amount (USDC)</th>
                </tr>
              </thead>
              <tbody>
                {result.proofBundle.lines.map((l: any, i: number) => (
                  <tr key={i}>
                    <td><span className="hash-tag">{l.quoteId.slice(0, 14)}...</span></td>
                    <td><strong>{l.vendorId}</strong></td>
                    <td>{l.categoryId.slice(0, 10)}...</td>
                    <td><span className="hash-tag">{l.skuId.slice(0, 10)}...</span></td>
                    <td>{l.units.toLocaleString()}</td>
                    <td><strong>{(l.amount / 1_000_000).toFixed(2)} USDC</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
