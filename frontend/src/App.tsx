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
  Bot,
  Menu,
  Search,
  Mic,
  Plus
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
      {/* Top Navbar matching the Reference Design (Hamburger, № Badge, Profile, Search, Mic) */}
      <header className="top-nav">
        {/* Brand Section: Hamburger + № Circular Logo + Title */}
        <div className="brand-section">
          <div className="menu-pill-btn" title="Toggle Navigation Menu">
            <Menu size={18} />
          </div>

          <div className="brand-logo" title="AgentVault Autonomous Policy Vault">
            №
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="brand-title">Financial Dashboard</span>
              <span className="brand-badge">WEB3-05</span>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', letterSpacing: '0.02em', marginTop: '-2px' }}>
              AgentVault Policy-Bound Autonomous Procurement
            </div>
          </div>
        </div>

        {/* 7 View Navigation Pill Tabs */}
        <nav className="nav-tabs">
          <button 
            className={`nav-tab ${activeTab === 'mandate' ? 'active' : ''}`}
            onClick={() => setActiveTab('mandate')}
          >
            <Shield size={14} />
            Mandate
          </button>

          <button 
            className={`nav-tab ${activeTab === 'agent' ? 'active' : ''}`}
            onClick={() => setActiveTab('agent')}
          >
            <Cpu size={14} />
            Agent Run
          </button>

          <button 
            className={`nav-tab ${activeTab === 'payments' ? 'active' : ''}`}
            onClick={() => setActiveTab('payments')}
          >
            <CreditCard size={14} />
            Payments & Proofs
          </button>

          <button 
            className={`nav-tab ${activeTab === 'autorefill' ? 'active' : ''}`}
            onClick={() => setActiveTab('autorefill')}
          >
            <Bot size={14} />
            Auto-Refill (x402)
          </button>

          <button 
            className={`nav-tab ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => setActiveTab('security')}
          >
            <ShieldAlert size={14} />
            Security Console
          </button>

          <button 
            className={`nav-tab ${activeTab === 'qpiai' ? 'active' : ''}`}
            onClick={() => setActiveTab('qpiai')}
          >
            <Atom size={14} />
            QpiAI Evidence
          </button>

          <button 
            className={`nav-tab ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            <Link2 size={14} />
            Audit Log
          </button>
        </nav>

        {/* Right Actions: Profile Pill, Search Bar, Circular Mic */}
        <div className="header-actions">
          {/* Profile Pill matching screenshot */}
          <div className="profile-pill">
            <div className="icon-circle-btn" style={{ width: '24px', height: '24px', marginRight: '-2px' }}>
              <Plus size={12} />
            </div>
            <div className="avatar-circle">
              DT
            </div>
            <div style={{ lineHeight: 1.1 }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Dwayne Tatum
              </div>
              <div style={{ fontSize: '0.64rem', color: 'var(--text-dim)' }}>
                CEO Assistant
              </div>
            </div>
          </div>

          {/* Search Pill Bar matching screenshot */}
          <div className="search-pill-bar" onClick={() => setShowPolicyModal(true)}>
            <Search size={14} color="var(--text-dim)" />
            <span>Start searching here...</span>
          </div>

          {/* Circular Mic Button matching screenshot */}
          <div className="icon-circle-btn" onClick={() => setShowPolicyModal(true)} title="Architecture & Policy Documentation">
            <Mic size={15} />
          </div>

          {/* Status Indicators Pill */}
          <div className="status-pill">
            <span className={`status-dot ${health?.chain?.connected ? 'dot-green' : 'dot-red'}`} />
            <span>{health?.chain?.connected ? '31337' : 'Offline'}</span>
          </div>
        </div>
      </header>

      {/* Main Viewport */}
      <main className="main-viewport">
        {/* Real-Time Unified Dashboard Overview Bento Grid Banner */}
        <DashboardOverviewBanner
          overview={overview}
          loading={loadingOverview}
          onRefresh={fetchOverview}
          onOpenDemo={() => setShowDemoModal(true)}
        />

        {/* Active Tab View */}
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

      {/* Guided Walkthrough Modal */}
      <GuidedDemoModal
        isOpen={showDemoModal}
        onClose={() => setShowDemoModal(false)}
        onNavigateTab={(t) => setActiveTab(t)}
        activeMandateId={activeMandateId}
        setActiveMandateId={setActiveMandateId}
        onRefreshOverview={fetchOverview}
      />

      {/* Architecture, Privacy & Limitations Modal */}
      <ArchitecturePolicyModal
        isOpen={showPolicyModal}
        onClose={() => setShowPolicyModal(false)}
      />
    </div>
  );
};

export default App;
