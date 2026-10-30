import React, { useState, useEffect } from 'react';
import { 
  api, 
  type RefillStatusResponse, 
  type RefillPackage, 
  type X402ClientPayResponse
} from '../api';
import { 
  Bot, 
  Send, 
  Sparkles, 
  AlertTriangle, 
  XCircle, 
  RefreshCw, 
  ShieldCheck, 
  CreditCard, 
  Zap,
  CheckCircle2,
  X,
  ArrowRight,
  Database,
  Sliders,
  Layers
} from 'lucide-react';

const VENDOR_RATES: Record<string, { serviceName: string; unitLabel: string; rate: number; serviceType: string; vendorName: string }> = {
  tokenforge: { serviceName: "AI Inference Credits", unitLabel: "tokens", rate: 1.50, serviceType: "AI_CREDITS", vendorName: "TokenForge" },
  nimbusapi: { serviceName: "API Throughput Calls", unitLabel: "calls", rate: 0.85, serviceType: "API_CALLS", vendorName: "NimbusAPI" },
  vaultstore: { serviceName: "Storage Units", unitLabel: "GB-mo", rate: 0.60, serviceType: "STORAGE", vendorName: "VaultStore" },
  budgetbyte: { serviceName: "Economy Multi-Service", unitLabel: "units", rate: 1.40, serviceType: "MULTI_SERVICE", vendorName: "BudgetByte" },
};

interface AutoRefillViewProps {
  activeMandateId?: string;
  onRefreshOverview?: () => void;
}

export const AutoRefillView: React.FC<AutoRefillViewProps> = ({ activeMandateId, onRefreshOverview }) => {
  const [status, setStatus] = useState<RefillStatusResponse | null>(null);
  const [packages, setPackages] = useState<RefillPackage[]>([]);
  const [selectedPkgId, setSelectedPkgId] = useState<string>('pack-base-5');
  const [selectedServiceFilter, setSelectedServiceFilter] = useState<string>('ALL');
  const [customSpendDollars, setCustomSpendDollars] = useState<number>(5.0);
  const [customVendor, setCustomVendor] = useState<string>('tokenforge');
  const [showFlexibleBuilder, setShowFlexibleBuilder] = useState<boolean>(false);
  const [inputPrompt, setInputPrompt] = useState<string>('');
  const [loadingChat, setLoadingChat] = useState<boolean>(false);
  const [loadingPay, setLoadingPay] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [payResult, setPayResult] = useState<X402ClientPayResponse | null>(null);

  // Pop-up Notification & Confirmation States
  const [showLowBalanceModal, setShowLowBalanceModal] = useState<boolean>(false);
  const [showSuccessModal, setShowSuccessModal] = useState<boolean>(false);
  const [hasDismissedModal, setHasDismissedModal] = useState<boolean>(false);

  const fetchStatus = async () => {
    try {
      const data = await api.getRefillStatus();
      setStatus(data);
      if (data.isLowBalance && !hasDismissedModal && !showSuccessModal && !loadingPay) {
        setShowLowBalanceModal(true);
      } else if (!data.isLowBalance) {
        setHasDismissedModal(false);
      }
    } catch (err: any) {
      console.error('Failed to fetch refill status:', err);
    }
  };

  const fetchPackages = async () => {
    try {
      const data = await api.getRefillPackages();
      setPackages(data.packages);
    } catch (err: any) {
      console.error('Failed to fetch refill packages:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchPackages();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [hasDismissedModal, showSuccessModal, loadingPay]);

  const handleSendPrompt = async (promptToSend?: string) => {
    const text = promptToSend || inputPrompt;
    if (!text.trim()) return;
    
    // Check if balance is already zero
    if ((status?.remainingUnits ?? 0) <= 0) {
      setHasDismissedModal(false);
      setShowLowBalanceModal(true);
      return;
    }

    setLoadingChat(true);
    setActionError(null);
    try {
      await api.sendChatMessage(text);
      setInputPrompt('');
      const updated = await api.getRefillStatus();
      setStatus(updated);
      if (updated.isLowBalance) {
        setHasDismissedModal(false);
        setShowLowBalanceModal(true);
      }
    } catch (err: any) {
      setActionError(err.message || 'Chat prompt failed');
    } finally {
      setLoadingChat(false);
    }
  };

  const handleFastConsume = async (units: number, reason: string) => {
    setActionError(null);
    try {
      await api.consumeRefillUnits(units, reason);
      const updated = await api.getRefillStatus();
      setStatus(updated);
      if (updated.isLowBalance) {
        setHasDismissedModal(false);
        setShowLowBalanceModal(true);
      }
    } catch (err: any) {
      setActionError(err.message || 'Consumption failed');
    }
  };

  const handleTriggerLowBalance = async () => {
    if (!status) return;
    const remainingUnits = status.remainingUnits;
    const target = Math.floor(status.totalAllowance * 0.12); // drop to 12% (<15%)
    const toConsume = Math.max(0, remainingUnits - target);
    if (toConsume > 0) {
      await api.consumeRefillUnits(toConsume, 'Simulate peak inference workload');
    }
    const updated = await api.getRefillStatus();
    setStatus(updated);
    setHasDismissedModal(false);
    setShowLowBalanceModal(true);
  };

  const handleResetAllowance = async () => {
    try {
      await api.resetRefillAllowance(5000);
      setPayResult(null);
      setActionError(null);
      setShowLowBalanceModal(false);
      setShowSuccessModal(false);
      setHasDismissedModal(false);
      await fetchStatus();
    } catch (err: any) {
      setActionError(err.message || 'Reset failed');
    }
  };

  const handleExecutePayment = async (forceFail: boolean = false) => {
    setLoadingPay(true);
    setActionError(null);
    try {
      // If user explicitly chose a tier exceeding current cap, align policy cap to allow the purchase
      const chosen = packages.find(p => p.packageId === selectedPkgId);
      if (chosen && chosen.isAllowedVendor && chosen.priceMicroUsdc > (status?.policy.maxSpendPerRefill || 0)) {
        await api.updateRefillPolicy({
          maxSpendPerRefill: chosen.priceMicroUsdc,
          maxDailySpend: Math.max(status?.policy.maxDailySpend || 50000000, chosen.priceMicroUsdc * 2),
        });
      }
      const res = await api.executeX402Pay(selectedPkgId, activeMandateId, forceFail);
      setPayResult(res);
      if (res.success) {
        setShowLowBalanceModal(false);
        setHasDismissedModal(true);
        setShowSuccessModal(true);
        onRefreshOverview?.();
      } else {
        setActionError(res.error || 'Payment settlement rejected by policy engine');
      }
      const updated = await api.getRefillStatus();
      setStatus(updated);
    } catch (err: any) {
      setActionError(err.message || 'Payment execution failed');
    } finally {
      setLoadingPay(false);
    }
  };

  const handleApplyFlexiblePackage = async (vendor: string, spendMicros: number) => {
    setActionError(null);
    try {
      const res = await api.calculateFlexiblePackage(vendor, spendMicros);
      if (res && res.package) {
        const pkg = res.package;
        setPackages(prev => {
          const exists = prev.find(p => p.packageId === pkg.packageId);
          if (exists) return prev;
          return [pkg, ...prev];
        });
        setSelectedPkgId(pkg.packageId);
      }
    } catch (err: any) {
      setActionError(err.message || 'Flexible package calculation failed');
    }
  };

  const handleTogglePolicy = async () => {
    if (!status) return;
    try {
      await api.updateRefillPolicy({
        enabled: !status.policy.enabled,
        revoked: false,
      });
      await fetchStatus();
    } catch (err: any) {
      setActionError(err.message || 'Policy update failed');
    }
  };

  const handleRevokePolicy = async () => {
    try {
      await api.updateRefillPolicy({
        enabled: false,
        revoked: true,
      });
      await fetchStatus();
    } catch (err: any) {
      setActionError(err.message || 'Revocation failed');
    }
  };

  const remaining = status?.remainingUnits ?? 5000;
  const total = status?.totalAllowance ?? 5000;
  const pct = status?.percentageRemaining ?? 100;
  const isLow = status?.isLowBalance ?? false;

  const gaugeColor = pct > 50 ? 'var(--color-green, #10b981)' : pct > 15 ? 'var(--color-yellow, #f59e0b)' : 'var(--color-red, #ef4444)';

  return (
    <div className="view-container">
      {/* Disclaimer and Protocol Banner */}
      <div className="card" style={{ borderColor: 'rgba(56, 189, 248, 0.4)', background: 'rgba(15, 23, 42, 0.85)', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Bot size={20} color="#38bdf8" />
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f8fafc' }}>
                Simulated AI Assistant & Autonomous x402 Auto-Refill
              </h3>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
              <strong>Notice:</strong> Simulated AI token usage for demonstration only. Payments use the <strong>x402 Protocol V2</strong> with deterministic policy guards.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span className="badge badge-cyan" style={{ fontSize: '0.75rem' }}>x402 Protocol V2</span>
            <span className="badge badge-cyan" style={{ fontSize: '0.75rem' }}>Scheme: exact</span>
            <span className="badge badge-green" style={{ fontSize: '0.75rem' }}>{status?.x402Config.network || 'eip155:84532'}</span>
          </div>
        </div>
      </div>

      {/* Top Metric Cards & Fast-Forward Bar */}
      <div className="metrics-grid" style={{ marginBottom: '1.25rem' }}>
        {/* Metric 1: Remaining Tokens */}
        <div className="metric-card">
          <div className="metric-header">
            <span>Simulated Token Balance</span>
            <Sparkles size={16} color={gaugeColor} />
          </div>
          <div className="metric-value" style={{ color: gaugeColor }}>
            {remaining.toLocaleString()} <span style={{ fontSize: '0.85rem', color: '#64748b' }}>/ {total.toLocaleString()}</span>
          </div>
          <div style={{ width: '100%', height: '6px', background: '#334155', borderRadius: '3px', marginTop: '8px', overflow: 'hidden' }}>
            <div style={{ width: `${Math.min(100, Math.max(0, pct))}%`, height: '100%', background: gaugeColor, transition: 'width 0.4s ease' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '0.75rem', color: '#94a3b8' }}>
            <span>{pct}% remaining</span>
            <span>Threshold: {status?.thresholdPct || 15}%</span>
          </div>
        </div>

        {/* Metric 2: Auto-Refill Policy Status */}
        <div className="metric-card">
          <div className="metric-header">
            <span>Auto-Refill Policy</span>
            <ShieldCheck size={16} color={status?.policy.enabled ? '#10b981' : '#f59e0b'} />
          </div>
          <div className="metric-value" style={{ fontSize: '1.2rem' }}>
            {status?.policy.revoked ? (
              <span style={{ color: '#ef4444' }}>REVOKED</span>
            ) : status?.policy.enabled ? (
              <span style={{ color: '#10b981' }}>ACTIVE</span>
            ) : (
              <span style={{ color: '#94a3b8' }}>MANUAL ONLY</span>
            )}
          </div>
          <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '4px' }}>
            Cap: ${(status?.policy.maxSpendPerRefill ? status.policy.maxSpendPerRefill / 1e6 : 5).toFixed(2)} / refill | Provider: {status?.policy.approvedVendor || 'TokenForge'}
          </div>
          <div style={{ marginTop: '8px', display: 'flex', gap: '6px' }}>
            <button className="btn btn-secondary btn-sm" onClick={handleTogglePolicy} style={{ fontSize: '0.72rem', padding: '4px 8px' }}>
              {status?.policy.enabled ? 'Pause Policy' : 'Enable Policy'}
            </button>
            {status?.policy.enabled && (
              <button className="btn btn-danger btn-sm" onClick={handleRevokePolicy} style={{ fontSize: '0.72rem', padding: '4px 8px' }}>
                Revoke Authority
              </button>
            )}
          </div>
        </div>

        {/* Metric 3: Presenter Controls */}
        <div className="metric-card">
          <div className="metric-header">
            <span>Presenter Fast-Forward</span>
            <Zap size={16} color="#38bdf8" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginTop: '6px' }}>
            <button className="btn btn-secondary btn-sm" onClick={() => handleFastConsume(500, 'Simulate user prompt')} style={{ fontSize: '0.72rem' }}>
              -500 Tokens
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => handleFastConsume(1000, 'Heavy query batch')} style={{ fontSize: '0.72rem' }}>
              -1,000 Tokens
            </button>
            <button className="btn btn-warning btn-sm" onClick={handleTriggerLowBalance} style={{ fontSize: '0.72rem' }}>
              Trigger Threshold
            </button>
            <button className="btn btn-secondary btn-sm" onClick={handleResetAllowance} style={{ fontSize: '0.72rem' }}>
              Reset (5k)
            </button>
          </div>
        </div>
      </div>

      {/* Low Balance Warning / Top-Up Action Banner */}
      {isLow && (
        <div className="card" style={{ borderColor: 'rgba(239, 68, 68, 0.6)', background: 'rgba(239, 68, 68, 0.08)', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <AlertTriangle size={24} color="#ef4444" />
              <div>
                <strong style={{ color: '#f8fafc', fontSize: '0.95rem' }}>Low Simulated Token Balance ({pct}%)</strong>
                <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: '#cbd5e1' }}>
                  Remaining balance ({remaining.toLocaleString()} units) is below the {status?.thresholdPct || 15}% threshold. AgentVault recommends a policy-approved refill.
                </p>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                className="btn btn-primary" 
                onClick={() => {
                  setHasDismissedModal(false);
                  setShowLowBalanceModal(true);
                }}
                disabled={loadingPay}
                style={{ background: '#0284c7', borderColor: '#38bdf8' }}
              >
                <CreditCard size={15} />
                Open Top-Up Dialog (x402)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area: Chat, Packages, and Stepper */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.25rem' }}>
        
        {/* Left Column: Interactive Simulated AI Chat */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #334155', paddingBottom: '10px', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Bot size={18} color="#38bdf8" />
              <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc' }}>Simulated AI Chat Panel</h4>
            </div>
            <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Deterministic Token Consumption</span>
          </div>

          {/* Quick Prompt Chips */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px' }}>
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={() => handleSendPrompt("Optimize my cloud procurement")}
              disabled={loadingChat}
              style={{ fontSize: '0.72rem', padding: '3px 8px' }}
            >
              ⚡ Optimize Procurement (~255 tokens)
            </button>
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={() => handleSendPrompt("Review PolicyVault spending limits")}
              disabled={loadingChat}
              style={{ fontSize: '0.72rem', padding: '3px 8px' }}
            >
              🛡️ Check Policy Caps (~240 tokens)
            </button>
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={() => handleSendPrompt("Simulate heavy model reasoning")}
              disabled={loadingChat}
              style={{ fontSize: '0.72rem', padding: '3px 8px' }}
            >
              🔥 Heavy Prompt (~240 tokens)
            </button>
          </div>

          {/* Chat Messages Log */}
          <div style={{ height: '240px', overflowY: 'auto', background: '#090d16', borderRadius: '6px', padding: '10px', border: '1px solid #1e293b', marginBottom: '10px' }}>
            {status?.recentMessages && status.recentMessages.length > 0 ? (
              status.recentMessages.map((msg, i) => (
                <div key={msg.id || i} style={{ marginBottom: '10px' }}>
                  <div style={{ fontSize: '0.78rem', color: '#38bdf8', fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}>
                    <span>You</span>
                    <span style={{ color: '#64748b', fontSize: '0.7rem' }}>-{msg.tokensConsumed} tokens</span>
                  </div>
                  <div style={{ background: '#1e293b', padding: '6px 10px', borderRadius: '4px', fontSize: '0.8rem', color: '#e2e8f0', marginTop: '2px' }}>
                    {msg.prompt}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#10b981', fontWeight: 600, marginTop: '4px' }}>
                    AgentVault Assistant
                  </div>
                  <div style={{ background: '#0f172a', padding: '6px 10px', borderRadius: '4px', fontSize: '0.78rem', color: '#94a3b8', borderLeft: '2px solid #10b981', marginTop: '2px', whiteSpace: 'pre-wrap' }}>
                    {msg.response}
                  </div>
                </div>
              ))
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', fontSize: '0.82rem' }}>
                <Bot size={32} style={{ marginBottom: '8px', opacity: 0.5 }} />
                <span>No simulated queries yet. Click a preset prompt above or type below.</span>
              </div>
            )}
          </div>

          {/* Prompt Input Box */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <input 
              type="text"
              className="input-field"
              placeholder={remaining <= 0 ? "Allowance exhausted — click top-up to continue" : "Enter prompt to simulate token usage..."}
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendPrompt()}
              disabled={loadingChat}
              style={{ flex: 1, fontSize: '0.82rem', padding: '8px 12px' }}
            />
            <button 
              className="btn btn-primary"
              onClick={() => handleSendPrompt()}
              disabled={loadingChat || !inputPrompt.trim()}
              style={{ padding: '8px 14px' }}
            >
              {loadingChat ? <RefreshCw className="spin" size={15} /> : <Send size={15} />}
            </button>
          </div>
        </div>

        {/* Right Column: x402 Refill Packages & Live Stepper */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #334155', paddingBottom: '10px', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CreditCard size={18} color="#10b981" />
              <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc' }}>x402 Refill Packages</h4>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className="badge badge-cyan" style={{ fontSize: '0.68rem' }}>
                Cap: ${( (status?.policy.maxSpendPerRefill || 5000000) / 1e6 ).toFixed(2)}
              </span>
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>QpiAI Evaluated</span>
            </div>
          </div>

          {/* Service Provider Filter Tabs */}
          <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '6px', marginBottom: '10px' }}>
            {[
              { id: 'ALL', label: 'All Services', icon: Layers },
              { id: 'AI_CREDITS', label: 'AI Credits', icon: Bot },
              { id: 'API_CALLS', label: 'API Calls', icon: Zap },
              { id: 'STORAGE', label: 'Storage', icon: Database },
              { id: 'MULTI_SERVICE', label: 'Economy', icon: Sparkles },
            ].map(tab => {
              const isActive = selectedServiceFilter === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setSelectedServiceFilter(tab.id)}
                  style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    border: `1px solid ${isActive ? '#38bdf8' : '#334155'}`,
                    background: isActive ? 'rgba(56, 189, 248, 0.15)' : '#0f172a',
                    color: isActive ? '#38bdf8' : '#94a3b8',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    whiteSpace: 'nowrap',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Icon size={12} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Flexible Cap-Sized Builder Toggle Button */}
          <div style={{ marginBottom: '10px' }}>
            <button
              onClick={() => setShowFlexibleBuilder(!showFlexibleBuilder)}
              style={{
                width: '100%',
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px dashed #38bdf8',
                background: showFlexibleBuilder ? 'rgba(56, 189, 248, 0.12)' : 'rgba(15, 23, 42, 0.6)',
                color: '#38bdf8',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Sliders size={13} />
                <span>Custom Flexible Top-Up (Sized to Cap)</span>
              </div>
              <span style={{ fontSize: '0.7rem' }}>{showFlexibleBuilder ? '▲ Hide' : '▼ Customize'}</span>
            </button>

            {/* Flexible Custom Top-Up Builder Form */}
            {showFlexibleBuilder && (
              <div style={{
                background: '#090d16',
                border: '1px solid #1e293b',
                borderRadius: '6px',
                padding: '10px',
                marginTop: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div>
                    <label style={{ fontSize: '0.7rem', color: '#94a3b8', display: 'block', marginBottom: '2px' }}>Provider Service:</label>
                    <select
                      value={customVendor}
                      onChange={(e) => setCustomVendor(e.target.value)}
                      style={{
                        width: '100%',
                        background: '#0f172a',
                        border: '1px solid #334155',
                        borderRadius: '4px',
                        color: '#f8fafc',
                        fontSize: '0.75rem',
                        padding: '4px 6px'
                      }}
                    >
                      <option value="tokenforge">TokenForge (AI Credits @ 1.5 µUSDC)</option>
                      <option value="nimbusapi">NimbusAPI (API Calls @ 0.85 µUSDC)</option>
                      <option value="vaultstore">VaultStore (Storage @ 0.60 µUSDC)</option>
                      <option value="budgetbyte">BudgetByte (Economy @ 1.40 µUSDC)</option>
                    </select>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                      <label style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Spend ($ USDC):</label>
                      <button
                        onClick={() => setCustomSpendDollars((status?.policy.maxSpendPerRefill || 5000000) / 1e6)}
                        style={{ background: 'transparent', border: 'none', color: '#e85c3f', fontSize: '0.65rem', cursor: 'pointer', textDecoration: 'underline', fontWeight: 600 }}
                      >
                        Max Cap (${((status?.policy.maxSpendPerRefill || 5000000)/1e6).toFixed(2)})
                      </button>
                    </div>
                    <input
                      type="number"
                      min={0.5}
                      max={(status?.policy.maxSpendPerRefill || 5000000) / 1e6}
                      step={0.5}
                      value={customSpendDollars}
                      onChange={(e) => setCustomSpendDollars(Math.max(0.1, parseFloat(e.target.value) || 0))}
                      style={{
                        width: '100%',
                        background: '#ffffff',
                        border: '1px solid #dcd7ce',
                        borderRadius: '4px',
                        color: '#1a1816',
                        fontSize: '0.75rem',
                        padding: '4px 6px'
                      }}
                    />
                    {/* Quick preset buttons: $5, $10, $20, $50 */}
                    <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
                      {[5, 10, 20, 50].map((amt) => {
                        const maxCap = (status?.policy.maxSpendPerRefill || 5000000) / 1e6;
                        const isDisabled = amt > maxCap;
                        return (
                          <button
                            key={amt}
                            onClick={() => setCustomSpendDollars(amt)}
                            disabled={isDisabled}
                            style={{
                              flex: 1,
                              padding: '2px 0',
                              fontSize: '0.65rem',
                              borderRadius: '3px',
                              border: customSpendDollars === amt ? '1px solid #e85c3f' : '1px solid #e2ddd5',
                              background: customSpendDollars === amt ? 'rgba(232, 92, 63, 0.12)' : '#f6f5f2',
                              color: isDisabled ? '#a8a29e' : customSpendDollars === amt ? '#e85c3f' : '#4a443e',
                              cursor: isDisabled ? 'not-allowed' : 'pointer',
                              fontWeight: customSpendDollars === amt ? 700 : 500
                            }}
                          >
                            ${amt}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Calculation preview */}
                {(() => {
                  const info = VENDOR_RATES[customVendor] || VENDOR_RATES.tokenforge;
                  const maxCap = status?.policy.maxSpendPerRefill || 5000000;
                  const customSpendMicros = Math.round(customSpendDollars * 1e6);
                  const isExceeded = customSpendMicros > maxCap;
                  const units = Math.max(1, Math.floor(customSpendMicros / info.rate));
                  const costUsdc = customSpendDollars;
                  return (
                    <div style={{
                      background: isExceeded ? 'rgba(239, 68, 68, 0.08)' : 'rgba(22, 163, 74, 0.08)',
                      border: `1px solid ${isExceeded ? '#ef4444' : '#16a34a'}`,
                      borderRadius: '4px',
                      padding: '6px 8px',
                      fontSize: '0.7rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <div>
                        <span style={{ color: '#1a1816', fontWeight: 600 }}>{units.toLocaleString()} {info.unitLabel}</span>
                        <span style={{ color: '#78716c' }}> @ ${costUsdc.toFixed(2)} USDC</span>
                      </div>
                      <button
                        onClick={() => handleApplyFlexiblePackage(customVendor, customSpendMicros)}
                        disabled={isExceeded}
                        style={{
                          background: isExceeded ? '#a8a29e' : '#e85c3f',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '4px',
                          padding: '3px 8px',
                          fontSize: '0.68rem',
                          fontWeight: 600,
                          cursor: isExceeded ? 'not-allowed' : 'pointer'
                        }}
                      >
                        {isExceeded ? 'Exceeds Cap!' : 'Apply Top-Up'}
                      </button>
                    </div>
                  );
                })()}
              </div>
            )}
          </div>

          {/* Package Selection */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
            {packages
              .filter(pkg => pkg.packageId !== 'pack-custom-213' && (selectedServiceFilter === 'ALL' || pkg.serviceType === selectedServiceFilter))
              .map((pkg) => {
                const isSelected = selectedPkgId === pkg.packageId;
                return (
                  <div 
                    key={pkg.packageId}
                    onClick={() => setSelectedPkgId(pkg.packageId)}
                    style={{
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: `1px solid ${isSelected ? '#e85c3f' : '#334155'}`,
                      background: isSelected ? 'rgba(232, 92, 63, 0.12)' : '#0f172a',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>{pkg.name}</span>
                        {pkg.isCapFlexible && <span className="badge badge-yellow" style={{ fontSize: '0.65rem' }}>Cap-Matched</span>}
                        {pkg.isRecommended && <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>Recommended</span>}
                        {!pkg.isAllowedVendor && <span className="badge badge-red" style={{ fontSize: '0.65rem' }}>Unapproved</span>}
                        {pkg.serviceName && <span className="badge badge-cyan" style={{ fontSize: '0.62rem' }}>{pkg.serviceName}</span>}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
                        {pkg.units.toLocaleString()} {pkg.unitLabel || 'credits'} | Provider: {pkg.vendorName.split(' ')[0]}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#e85c3f' }}>
                        ${pkg.priceUsdc.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '0.68rem', color: '#64748b' }}>USDC</div>
                    </div>
                  </div>
                );
              })}
          </div>

          {/* Actions */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '14px' }}>
            <button 
              className="btn btn-primary"
              onClick={() => handleExecutePayment(false)}
              disabled={loadingPay}
              style={{ fontSize: '0.78rem', padding: '8px' }}
            >
              {loadingPay ? <RefreshCw className="spin" size={14} /> : <CreditCard size={14} />}
              Execute x402 Refill
            </button>
            <button 
              className="btn btn-secondary"
              onClick={() => handleExecutePayment(true)}
              disabled={loadingPay}
              style={{ fontSize: '0.78rem', padding: '8px', borderColor: '#ef4444', color: '#fca5a5' }}
              title="Test rejection of tampered payment"
            >
              Test Tampered Fail
            </button>
          </div>

          {/* Action Error Banner */}
          {actionError && (
            <div style={{ padding: '8px 10px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', borderRadius: '4px', fontSize: '0.75rem', color: '#fca5a5', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <XCircle size={14} color="#ef4444" />
                <strong>{actionError}</strong>
              </div>
            </div>
          )}

          {/* Live 6-Step Visual Stepper */}
          {payResult && (
            <div style={{ background: '#090d16', border: '1px solid #1e293b', borderRadius: '6px', padding: '10px' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#f8fafc', marginBottom: '8px', display: 'flex', justifyContent: 'space-between' }}>
                <span>x402 V2 Protocol Trace</span>
                <span style={{ color: payResult.success ? '#10b981' : '#ef4444' }}>
                  {payResult.success ? 'SETTLED' : 'REJECTED'}
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {payResult.statesTrace.map((st) => {
                  const isFail = st.state === 'PAYMENT_FAILED';
                  return (
                    <div key={st.step} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '0.72rem' }}>
                      <div style={{ minWidth: '16px', height: '16px', borderRadius: '50%', background: isFail ? '#ef4444' : '#10b981', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.65rem', fontWeight: 700, marginTop: '1px' }}>
                        {st.step}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, color: isFail ? '#fca5a5' : '#e2e8f0' }}>{st.state}</div>
                        <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>{st.description}</div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {payResult.success && payResult.settlement && (
                <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #1e293b', fontSize: '0.7rem', color: '#94a3b8' }}>
                  <div><strong>TxHash:</strong> <code style={{ color: '#38bdf8' }}>{payResult.settlement.txHash}</code></div>
                  <div><strong>Network:</strong> {payResult.settlement.network} | <strong>Amount:</strong> ${(parseInt(payResult.settlement.amount)/1e6).toFixed(2)} USDC</div>
                  <div style={{ color: '#10b981', marginTop: '4px' }}>✓ Credited {payResult.creditRecord?.unitsGranted?.toLocaleString()} tokens to simulated allowance.</div>
                </div>
              )}
            </div>
          )}

        </div>

      </div>

      {/* 1. Low Balance Warning & Top-Up Modal (Interactive Pop-Up) */}
      {showLowBalanceModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(5, 8, 16, 0.85)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
        }}>
          <div style={{
            background: '#0d1322',
            border: '1px solid rgba(239, 68, 68, 0.5)',
            borderRadius: '16px',
            width: '100%',
            maxWidth: '560px',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(239, 68, 68, 0.15)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}>
            {/* Header */}
            <div style={{
              padding: '18px 24px',
              borderBottom: '1px solid #1e293b',
              background: 'rgba(239, 68, 68, 0.1)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  background: 'rgba(239, 68, 68, 0.2)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  padding: '8px',
                  borderRadius: '10px',
                  display: 'flex'
                }}>
                  <AlertTriangle size={22} color="#ef4444" />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f8fafc', fontWeight: 700 }}>
                      Fund Balance Too Low!
                    </h3>
                    <span className="badge badge-red" style={{ fontSize: '0.65rem' }}>CRITICAL ALERT</span>
                  </div>
                  <p style={{ margin: '2px 0 0', fontSize: '0.78rem', color: '#fda4af' }}>
                    Simulated AI token usage has crossed the low balance threshold
                  </p>
                </div>
              </div>
              <button 
                onClick={() => {
                  setShowLowBalanceModal(false);
                  setHasDismissedModal(true);
                }}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Body */}
            <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Balance gauge box */}
              <div style={{ background: '#090d16', border: '1px solid #1e293b', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '6px' }}>
                  <span style={{ color: '#94a3b8' }}>Current Remaining Balance:</span>
                  <strong style={{ color: '#ef4444' }}>{remaining.toLocaleString()} / {total.toLocaleString()} units ({pct}%)</strong>
                </div>
                <div style={{ width: '100%', height: '8px', background: '#334155', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, Math.max(0, pct))}%`, height: '100%', background: '#ef4444' }} />
                </div>
                <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '6px' }}>
                  Threshold is set to {status?.thresholdPct || 15}%. Further agent turns may fail without a top-up.
                </div>
              </div>

              {/* Package Recommendation */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>
                    Select Top-Up Package (x402 Protocol V2):
                  </label>
                  <span style={{ fontSize: '0.7rem', color: '#38bdf8' }}>
                    Cap: ${((status?.policy.maxSpendPerRefill || 5000000)/1e6).toFixed(2)} USDC
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '240px', overflowY: 'auto' }}>
                  {packages.filter(p => p.isAllowedVendor && p.packageId !== 'pack-custom-213').map(pkg => {
                    const isSel = selectedPkgId === pkg.packageId;
                    return (
                      <div 
                        key={pkg.packageId}
                        onClick={() => setSelectedPkgId(pkg.packageId)}
                        style={{
                          padding: '10px 14px',
                          borderRadius: '8px',
                          border: `1px solid ${isSel ? '#e85c3f' : '#1e293b'}`,
                          background: isSel ? 'rgba(232, 92, 63, 0.12)' : '#090d16',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                            <strong style={{ fontSize: '0.85rem', color: '#f8fafc' }}>{pkg.name}</strong>
                            {pkg.isCapFlexible && <span className="badge badge-yellow" style={{ fontSize: '0.62rem' }}>Cap-Matched</span>}
                            {pkg.isRecommended && <span className="badge badge-green" style={{ fontSize: '0.62rem' }}>Recommended</span>}
                            {pkg.serviceName && <span className="badge badge-cyan" style={{ fontSize: '0.62rem' }}>{pkg.serviceName}</span>}
                          </div>
                          <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
                            +{pkg.units.toLocaleString()} {pkg.unitLabel || 'credits'} | Provider: {pkg.vendorName.split(' ')[0]}
                          </span>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#e85c3f' }}>
                            ${pkg.priceUsdc.toFixed(2)}
                          </span>
                          <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>USDC</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Question prompt */}
              <div style={{ background: 'rgba(2, 132, 199, 0.08)', border: '1px solid rgba(56, 189, 248, 0.2)', padding: '12px 14px', borderRadius: '8px', fontSize: '0.8rem', color: '#bae6fd' }}>
                💡 <strong>Credits too low, wanna top up?</strong> Clicking <em>Yes, Initiate Automated Payment</em> will execute an autonomous machine-to-machine payment via x402 V2, settling immediately on-chain and replenishing your credits.
              </div>

              {/* Error Message if payment failed */}
              {actionError && (
                <div style={{
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid #ef4444',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  color: '#fca5a5',
                  fontSize: '0.8rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <AlertTriangle size={18} color="#ef4444" style={{ flexShrink: 0 }} />
                  <span><strong>Payment Error:</strong> {actionError}</span>
                </div>
              )}

              {/* Buttons */}
              <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowLowBalanceModal(false);
                    setHasDismissedModal(true);
                  }}
                  disabled={loadingPay}
                  style={{ flex: 1, padding: '10px', fontSize: '0.82rem' }}
                >
                  Not Now / Dismiss
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => handleExecutePayment(false)}
                  disabled={loadingPay}
                  style={{ 
                    flex: 1.5, 
                    padding: '10px', 
                    fontSize: '0.85rem', 
                    background: '#0284c7', 
                    borderColor: '#38bdf8',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px'
                  }}
                >
                  {loadingPay ? (
                    <>
                      <RefreshCw className="spin" size={16} />
                      Processing x402 Payment...
                    </>
                  ) : (
                    <>
                      <CreditCard size={16} />
                      Yes, Initiate Automated Payment
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. Top-Up Confirmed Success Modal (Confirmation Pop-Up) */}
      {showSuccessModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(5, 8, 16, 0.85)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
        }}>
          <div style={{
            background: '#0d1322',
            border: '1px solid rgba(16, 185, 129, 0.5)',
            borderRadius: '16px',
            width: '100%',
            maxWidth: '540px',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(16, 185, 129, 0.15)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}>
            {/* Header */}
            <div style={{
              padding: '18px 24px',
              borderBottom: '1px solid #1e293b',
              background: 'rgba(16, 185, 129, 0.1)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  background: 'rgba(16, 185, 129, 0.2)',
                  border: '1px solid rgba(16, 185, 129, 0.4)',
                  padding: '8px',
                  borderRadius: '10px',
                  display: 'flex'
                }}>
                  <CheckCircle2 size={22} color="#10b981" />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#f8fafc', fontWeight: 700 }}>
                      Top-Up Confirmed & Settled!
                    </h3>
                    <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>x402 V2 SUCCESS</span>
                  </div>
                  <p style={{ margin: '2px 0 0', fontSize: '0.78rem', color: '#6ee7b7' }}>
                    Automated payment confirmed on-chain and credits replenished
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setShowSuccessModal(false)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Body */}
            <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Credit Increment Highlight */}
              <div style={{ background: '#090d16', border: '1px solid #1e293b', borderRadius: '10px', padding: '16px', textAlign: 'center' }}>
                <span style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Simulated Credits Increased By
                </span>
                <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#10b981', margin: '4px 0' }}>
                  +{payResult?.creditRecord?.unitsGranted?.toLocaleString() || '2,000'} Units
                </div>
                <div style={{ fontSize: '0.85rem', color: '#e2e8f0' }}>
                  New Balance: <strong style={{ color: '#38bdf8' }}>{remaining.toLocaleString()} units ({pct}%)</strong>
                </div>
              </div>

              {/* Transaction Receipt Details */}
              <div style={{ background: '#090d16', border: '1px solid #1e293b', borderRadius: '10px', padding: '14px', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Payment Protocol:</span>
                  <span style={{ color: '#f8fafc', fontWeight: 600 }}>x402 V2 (exact scheme)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Settled Amount:</span>
                  <span style={{ color: '#38bdf8', fontWeight: 600 }}>${(parseInt(payResult?.settlement?.amount || '2000000') / 1e6).toFixed(2)} USDC</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Recipient Vendor:</span>
                  <span style={{ color: '#f8fafc' }}>TokenForge Ltd ({payResult?.settlement?.payee?.slice(0, 8)}...)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#94a3b8' }}>Network:</span>
                  <span style={{ color: '#f8fafc' }}>{payResult?.settlement?.network || 'eip155:31337'}</span>
                </div>
                <div style={{ borderTop: '1px solid #1e293b', paddingTop: '8px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ color: '#94a3b8' }}>Transaction Hash:</span>
                  <code style={{ fontSize: '0.72rem', color: '#38bdf8', wordBreak: 'break-all' }}>
                    {payResult?.settlement?.txHash || '0x4f128e...'}
                  </code>
                </div>
              </div>

              {/* Close / Continue button */}
              <button
                className="btn btn-primary"
                onClick={() => setShowSuccessModal(false)}
                style={{
                  width: '100%',
                  padding: '12px',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  background: '#10b981',
                  borderColor: '#34d399',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  marginTop: '4px'
                }}
              >
                <span>Continue Chatting with Agent</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
