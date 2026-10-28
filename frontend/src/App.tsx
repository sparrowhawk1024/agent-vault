import React, { useState, useEffect } from 'react';
import { api, type SystemHealth } from './api';
import { MandateView } from './views/MandateView';
import { AgentRunView } from './views/AgentRunView';
import { PaymentsView } from './views/PaymentsView';
import { SecurityConsoleView } from './views/SecurityConsoleView';
import { QpiAIEvidenceView } from './views/QpiAIEvidenceView';
import { AuditLogView } from './views/AuditLogView';
import { 
  Shield, 
  Cpu, 
  CreditCard, 
  ShieldAlert, 
  Atom, 
  Link2 
} from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'mandate' | 'agent' | 'payments' | 'security' | 'qpiai' | 'audit'>('mandate');
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [activeMandateId, setActiveMandateId] = useState<string>('');

  const fetchHealth = async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
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

        {/* Live System Status Badges */}
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
      </header>

      {/* Main Viewport */}
      <main className="main-viewport">
        {activeTab === 'mandate' && (
          <MandateView 
            activeMandateId={activeMandateId} 
            setActiveMandateId={setActiveMandateId} 
          />
        )}

        {activeTab === 'agent' && (
          <AgentRunView 
            activeMandateId={activeMandateId} 
          />
        )}

        {activeTab === 'payments' && (
          <PaymentsView />
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
    </div>
  );
};

export default App;
