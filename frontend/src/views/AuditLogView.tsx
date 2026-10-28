import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { Link2, CheckCircle2, ShieldCheck, RefreshCw, ChevronDown, ChevronRight, Hash } from 'lucide-react';

export const AuditLogView: React.FC = () => {
  const [entries, setEntries] = useState<any[]>([]);
  const [verification, setVerification] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const fetchLog = async () => {
    setLoading(true);
    try {
      const data = await api.getAuditEntries();
      setEntries(data.entries || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const verifyChain = async () => {
    setLoading(true);
    try {
      const v = await api.verifyAuditChain();
      setVerification(v);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLog();
    verifyChain();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Link2 style={{ color: 'var(--accent-teal)' }} size={24} />
            Tamper-Evident SHA-256 Hash-Chained Audit Log
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Cryptographically linked immutable timeline of mandates, optimizations, approvals, and on-chain settlements (§8.9 & §13.3)
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-sm" onClick={fetchLog} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'glow-animation' : ''} />
            Refresh Log
          </button>
          <button className="btn btn-primary btn-sm" onClick={verifyChain} disabled={loading}>
            <ShieldCheck size={14} />
            Verify Chain Integrity
          </button>
        </div>
      </div>

      {/* Verification Result Banner */}
      {verification && (
        <div style={{ 
          padding: '14px 18px', 
          borderRadius: '10px', 
          background: verification.valid ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
          border: `1px solid ${verification.valid ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle2 size={22} style={{ color: verification.valid ? 'var(--accent-emerald)' : 'var(--accent-rose)' }} />
            <div>
              <strong style={{ fontSize: '0.92rem' }}>
                {verification.valid ? 'Audit Chain Cryptographically Valid' : 'Integrity Violation Detected'}
              </strong>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {verification.detail} • Total Blocks: {verification.totalBlocks}
              </div>
            </div>
          </div>
          <span className={`badge ${verification.valid ? 'badge-green' : 'badge-red'}`}>
            {verification.valid ? 'Tamper-Evident: INTACT' : 'TAMPERED'}
          </span>
        </div>
      )}

      {/* Hash Chained Timeline */}
      <div className="glass-card">
        <div className="card-title">
          <Hash size={18} style={{ color: 'var(--accent-cyan)' }} />
          Sequential Block History
        </div>
        <div className="card-subtitle">
          Each block contains `hash = SHA256(index | timestamp | eventType | prevHash | canonical_json(payload))`
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {entries.map((entry: any) => {
            const isExpanded = expandedIndex === entry.index;
            return (
              <div 
                key={entry.index}
                style={{ 
                  background: 'rgba(14, 19, 31, 0.65)', 
                  border: '1px solid var(--border-subtle)', 
                  borderRadius: '10px', 
                  padding: '14px 18px' 
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className="badge badge-cyan" style={{ fontSize: '0.75rem' }}>Block #{entry.index}</span>
                    <strong style={{ fontSize: '0.9rem' }}>{entry.eventType}</strong>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    {new Date(entry.timestamp * 1000).toLocaleString()}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '8px', fontSize: '0.75rem' }}>
                  <div>
                    <span style={{ color: 'var(--text-dim)' }}>Prev Hash: </span>
                    <span className="hash-tag">{entry.prevHash.slice(0, 20)}...</span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-dim)' }}>Block Hash: </span>
                    <span className="hash-tag" style={{ color: '#a7f3d0' }}>{entry.hash.slice(0, 20)}...</span>
                  </div>
                </div>

                {/* Expandable Payload */}
                <div style={{ marginTop: '8px' }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.72rem', padding: '3px 8px' }}
                    onClick={() => setExpandedIndex(isExpanded ? null : entry.index)}
                  >
                    {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    {isExpanded ? 'Hide Payload' : 'Inspect Event Data'}
                  </button>

                  {isExpanded && (
                    <pre style={{ 
                      marginTop: '8px', 
                      padding: '10px', 
                      background: '#04060a', 
                      borderRadius: '6px', 
                      fontSize: '0.72rem', 
                      color: '#7dd3fc', 
                      overflowX: 'auto' 
                    }}>
                      {JSON.stringify(entry.payload, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
