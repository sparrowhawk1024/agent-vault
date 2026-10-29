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
  LayoutDashboard,
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
  const [activeTab, setActiveTab] = useState<'dashboard' | 'mandate' | 'agent' | 'payments' | 'autorefill' | 'security' | 'qpiai' | 'audit'>('dashboard');
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
          <div 
            className="menu-pill-btn" 
            onClick={() => setActiveTab('dashboard')} 
            title="Dashboard Overview"
          >
            <Menu size={17} />
          </div>

          <div 
            className="brand-logo" 
            onClick={() => setActiveTab('dashboard')} 
            style={{ cursor: 'pointer' }}
            title="AgentVault Policy Vault"
          >
            №
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="brand-title">Financial Dashboard</span>
              <span className="brand-badge">WEB3-05</span>
            </div>
            <div style={{ fontSize: '0.67rem', color: 'var(--text-dim)', letterSpacing: '0.01em', marginTop: '-2px' }}>
              CEO Assistant • Policy-Bound Autonomous Procurement
            </div>
          </div>
        </div>

        {/* View Navigation Pill Tabs */}
        <nav className="nav-tabs">
          <button 
            className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={14} />
            Dashboard
          </button>

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
            Payments
          </button>

          <button 
            className={`nav-tab ${activeTab === 'autorefill' ? 'active' : ''}`}
            onClick={() => setActiveTab('autorefill')}
          >
            <Bot size={14} />
            x402 Refill
          </button>

          <button 
            className={`nav-tab ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => setActiveTab('security')}
          >
            <ShieldAlert size={14} />
            Security
          </button>

          <button 
            className={`nav-tab ${activeTab === 'qpiai' ? 'active' : ''}`}
            onClick={() => setActiveTab('qpiai')}
          >
            <Atom size={14} />
            QpiAI
          </button>

          <button 
            className={`nav-tab ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            <Link2 size={14} />
            Audit
          </button>
        </nav>

        {/* Right Actions: Profile Pill, Search Bar, Circular Mic */}
        <div className="header-actions">
          {/* Profile Pill matching screenshot */}
          <div className="profile-pill">
            <div 
              className="icon-circle-btn" 
              onClick={() => setShowDemoModal(true)}
              style={{ width: '22px', height: '22px', marginRight: '-2px' }}
              title="Launch Guided Demo"
            >
              <Plus size={11} />
            </div>
            <div className="avatar-circle">
              DT
            </div>
            <div style={{ lineHeight: 1.1 }}>
              <div style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Dwayne Tatum
              </div>
              <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)' }}>
                CEO Assistant
              </div>
            </div>
          </div>

          {/* Search Pill Bar matching screenshot */}
          <div className="search-pill-bar" onClick={() => setShowPolicyModal(true)}>
            <Search size={13} color="var(--text-dim)" />
            <span>Start searching here...</span>
          </div>

          {/* Circular Mic Button matching screenshot */}
          <div 
            className="icon-circle-btn" 
            onClick={() => setShowPolicyModal(true)} 
            title="Policy & Architecture Documentation"
          >
            <Mic size={14} />
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
        {/* Main Bento Grid Dashboard View (When 'dashboard' is active) */}
        {activeTab === 'dashboard' && (
          <DashboardOverviewBanner
            overview={overview}
            loading={loadingOverview}
            onRefresh={fetchOverview}
            onOpenDemo={() => setShowDemoModal(true)}
            onNavigateTab={(t) => setActiveTab(t)}
          />
        )}

        {/* Dedicated Tab Views (Without any duplicate banner above them) */}
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
