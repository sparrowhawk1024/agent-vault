import React, { useState, useEffect } from 'react';
import { api, type SystemHealth, type DashboardOverview } from './api';
import { MandateView } from './views/MandateView';
import { AgentRunView } from './views/AgentRunView';
import { PaymentsView } from './views/PaymentsView';
import { SecurityConsoleView } from './views/SecurityConsoleView';
import { QpiAIEvidenceView } from './views/QpiAIEvidenceView';
import { AuditLogView } from './views/AuditLogView';
import { AutoRefillView } from './views/AutoRefillView';
import { DashboardOverviewBanner } from './components/DashboardOverviewBanner';
import { GuidedDemoModal } from './components/GuidedDemoModal';
import { ArchitecturePolicyModal } from './components/ArchitecturePolicyModal';
import { 
  Shield, 
  Cpu, 
  CreditCard, 
  ShieldAlert, 
  Atom, 
  Link2,
  BookOpen,
  Bot
} from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'mandate' | 'agent' | 'payments' | 'autorefill' | 'security' | 'qpiai' | 'audit'>('mandate');
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [loadingOverview, setLoadingOverview] = useState<boolean>(false);
  const [activeMandateId, setActiveMandateId] = useState<string>('');
  const [showDemoModal, setShowDemoModal] = useState<boolean>(false);
  const [showPolicyModal, setShowPolicyModal] = useState<boolean>(false);

  const fetchOverview = async () => {
    setLoadingOverview(true);
    try {
      const data = await api.getOverview();
      setOverview(data);
      if (data.mandate?.mandateId && !activeMandateId) {
        setActiveMandateId(data.mandate.mandateId);
      }
    } catch (err) {
      console.error('Error fetching overview:', err);
    } finally {
      setLoadingOverview(false);
    }
  };

  const fetchHealth = async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);
    } catch (err) {
      console.error('Error fetching health:', err);
    }
  };

  useEffect(() => {
    fetchHealth();
    fetchOverview();
    const interval = setInterval(() => {
      fetchHealth();
      fetchOverview();
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-container">
      {/* Top Sticky Navigation */}
      <header className="top-nav">
        <div className="brand-section">
          <div className="brand-logo">
            AV
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="brand-title">AgentVault</span>
              <span className="brand-badge">WEB3-05</span>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', letterSpacing: '0.02em' }}>
              Policy-Bound Autonomous Procurement • QpiAI × Web3
            </div>
          </div>
        </div>

        {/* 6 View Navigation Tabs */}
        <nav className="nav-tabs">
          <button 
            className={`nav-tab ${activeTab === 'mandate' ? 'active' : ''}`}
            onClick={() => setActiveTab('mandate')}
          >
            <Shield size={16} />
            Mandate
          </button>

          <button 
            className={`nav-tab ${activeTab === 'agent' ? 'active' : ''}`}
            onClick={() => setActiveTab('agent')}
          >
            <Cpu size={16} />
            Agent Run
          </button>

          <button 
            className={`nav-tab ${activeTab === 'payments' ? 'active' : ''}`}
            onClick={() => setActiveTab('payments')}
          >
            <CreditCard size={16} />
            Payments & Proofs
          </button>

          <button 
            className={`nav-tab ${activeTab === 'autorefill' ? 'active' : ''}`}
            onClick={() => setActiveTab('autorefill')}
          >
            <Bot size={16} />
            Auto-Refill (x402)
          </button>

          <button 
            className={`nav-tab ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => setActiveTab('security')}
          >
            <ShieldAlert size={16} />
            Security Console
          </button>

          <button 
            className={`nav-tab ${activeTab === 'qpiai' ? 'active' : ''}`}
            onClick={() => setActiveTab('qpiai')}
          >
            <Atom size={16} />
            QpiAI Evidence
          </button>

          <button 
            className={`nav-tab ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            <Link2 size={16} />
            Audit Log
          </button>
        </nav>

        {/* Header Right Status & Policy Action */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setShowPolicyModal(true)}
            style={{ fontSize: '0.74rem', padding: '5px 10px' }}
          >
            <BookOpen size={13} />
            Architecture & Policy
          </button>

          <div className="header-status">
            <div className="status-pill">
              <span className={`status-dot ${health?.chain?.connected ? 'dot-green' : 'dot-red'}`} />
              <span>Anvil: {health?.chain?.connected ? '31337' : 'Offline'}</span>
            </div>

            <div className="status-pill">
              <span className={`status-dot ${health?.verifier?.status === 'ACTIVE' ? 'dot-green' : 'dot-red'}`} />
              <span>Verifier: {health?.verifier?.status || 'Unknown'}</span>
            </div>

            <div className="status-pill">
              <span className="status-dot dot-green" />
              <span>QpiAI: {health?.qpiai?.optExecutionMode || 'Live'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Viewport */}
      <main className="main-viewport">
        {/* Real-Time Unified Dashboard Overview Banner (Phase 2.A) */}
        <DashboardOverviewBanner
          overview={overview}
          loading={loadingOverview}
          onRefresh={fetchOverview}
          onOpenDemo={() => setShowDemoModal(true)}
        />

        {/* 6 Core Views */}
        {activeTab === 'mandate' && (
          <MandateView 
            activeMandateId={activeMandateId} 
            setActiveMandateId={setActiveMandateId} 
          />
        )}

        {activeTab === 'agent' && (
          <AgentRunView 
            activeMandateId={activeMandateId} 
            onRefreshOverview={fetchOverview}
          />
        )}

        {activeTab === 'payments' && (
          <PaymentsView />
        )}

        {activeTab === 'autorefill' && (
          <AutoRefillView 
            activeMandateId={activeMandateId} 
            onRefreshOverview={fetchOverview}
          />
        )}

        {activeTab === 'security' && (
          <SecurityConsoleView />
        )}

        {activeTab === 'qpiai' && (
          <QpiAIEvidenceView />
        )}

        {activeTab === 'audit' && (
          <AuditLogView />
        )}
      </main>

      {/* Guided Walkthrough Modal (Phase 3) */}
      <GuidedDemoModal
        isOpen={showDemoModal}
        onClose={() => setShowDemoModal(false)}
        onNavigateTab={(t) => setActiveTab(t)}
        activeMandateId={activeMandateId}
        setActiveMandateId={setActiveMandateId}
        onRefreshOverview={fetchOverview}
      />

      {/* Architecture, Privacy & Limitations Modal (Phase 4 & 5) */}
      <ArchitecturePolicyModal
        isOpen={showPolicyModal}
        onClose={() => setShowPolicyModal(false)}
      />
    </div>
  );
};

export default App;
