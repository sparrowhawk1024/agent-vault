import React from 'react';
import type { DashboardOverview } from '../api';
import { 
  Activity, 
  CheckCircle, 
  XCircle, 
  Clock,
  Lock,
  ChevronDown,
  Edit2,
  TrendingUp,
  Search,
  SlidersHorizontal,
  ShieldCheck,
  Zap,
  ArrowRight
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
      <div className="glass-card" style={{ padding: '20px 24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-muted)' }}>
            <Activity className="glow-animation" size={18} color="var(--accent-terracotta)" />
            <span>Connecting to AgentVault core services & local Anvil chain...</span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onRefresh} disabled={loading}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { mandate, verifier, paymentCounts } = overview;
  const isMandateActive = mandate.exists && mandate.isActive;

  return (
    <div style={{ marginBottom: '24px' }}>
      {/* 1. Hero Date & Action Strip (matching top hero section in screenshot) */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: '20px',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        {/* Left: Date Badge + CTA Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          {/* Big Circular Date Badge */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '12px',
            background: '#ffffff',
            padding: '6px 16px 6px 8px',
            borderRadius: 'var(--radius-pill)',
            border: '1px solid var(--border-subtle)',
            boxShadow: 'var(--shadow-card)'
          }}>
            <div style={{ 
              width: '42px', 
              height: '42px', 
              borderRadius: '50%', 
              background: '#ffffff',
              border: '1.5px solid #ece9e3',
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              fontSize: '1.15rem',
              fontWeight: 800,
              color: 'var(--text-main)',
              fontFamily: 'var(--font-mono)'
            }}>
              30
            </div>
            <div>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.2 }}>
                Wed, October
              </div>
              <div style={{ fontSize: '0.68rem', color: isMandateActive ? 'var(--accent-emerald)' : 'var(--accent-terracotta)', fontWeight: 600 }}>
                {isMandateActive ? '● Mandate Active' : '○ Standby'}
              </div>
            </div>
          </div>

          {/* Solid Terracotta Button with Arrow */}
          <button 
            className="btn btn-primary" 
            onClick={onOpenDemo}
            style={{ 
              padding: '10px 22px', 
              fontSize: '0.86rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            Show my Tasks
            <ArrowRight size={16} />
          </button>

          {/* Sync Button */}
          <button 
            onClick={onRefresh}
            disabled={loading}
            className="icon-circle-btn"
            title="Sync on-chain state"
          >
            <Clock size={16} className={loading ? 'glow-animation' : ''} />
          </button>
        </div>

        {/* Right: Friendly Greeting from screenshot */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
              Hey, Need help? 👋
            </div>
            <div style={{ fontSize: '0.86rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>
              | Just ask me anything!
            </div>
          </div>
          <div className="icon-circle-btn" style={{ width: '42px', height: '42px' }}>
            <Zap size={18} color="var(--accent-terracotta)" />
          </div>
        </div>
      </div>

      {/* 2. Bento Grid of 8 Coordinated Cards (matching the layout and cards of screenshot) */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(12, 1fr)', 
        gap: '16px' 
      }}>

        {/* CARD 1: VISA / Direct Debits Mandate Card (col-span-4) */}
        <div className="glass-card" style={{ 
          gridColumn: 'span 4', 
          padding: '22px 24px', 
          display: 'flex', 
          flexDirection: 'column', 
          justifyContent: 'space-between',
          minHeight: '210px'
        }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <span style={{ fontWeight: 800, fontSize: '0.92rem', letterSpacing: '0.04em', color: 'var(--text-main)' }}>
                VISA
              </span>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px', 
                fontSize: '0.74rem', 
                color: 'var(--text-secondary)',
                background: 'var(--bg-card-subtle)',
                padding: '4px 10px',
                borderRadius: 'var(--radius-pill)',
                border: '1px solid var(--border-subtle)',
                cursor: 'pointer'
              }}>
                <span>Direct Debits</span>
                <ChevronDown size={13} />
              </div>
            </div>

            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
              Linked to main account
            </div>
            <div style={{ 
              fontSize: '1.25rem', 
              fontWeight: 700, 
              fontFamily: 'var(--font-mono)', 
              color: 'var(--text-main)',
              letterSpacing: '0.08em',
              margin: '4px 0 14px 0'
            }}>
              •••• 2719
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-dark btn-sm" style={{ padding: '6px 18px' }}>
                Receive
              </button>
              <button className="btn btn-secondary btn-sm" style={{ padding: '6px 18px' }}>
                Send
              </button>
            </div>
          </div>

          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginTop: '16px',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-subtle)'
          }}>
            <div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>
                Monthly regular fee
              </div>
              <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-main)' }}>
                ${(mandate.remainingBudget / 1_000_000).toFixed(2)}
              </div>
            </div>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px', 
              fontSize: '0.72rem', 
              color: 'var(--accent-terracotta)', 
              fontWeight: 600,
              cursor: 'pointer'
            }}>
              <Edit2 size={12} />
              <span>Edit cards limitation</span>
            </div>
          </div>
        </div>

        {/* CARD 2: Total Income & Total Paid Stats (col-span-3) */}
        <div className="glass-card" style={{ 
          gridColumn: 'span 3', 
          padding: '22px 24px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          minHeight: '210px'
        }}>
          {/* Top Metric: Total Income */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ 
                width: '26px', 
                height: '26px', 
                borderRadius: '50%', 
                background: 'var(--bg-card-subtle)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                color: 'var(--text-muted)'
              }}>
                <Clock size={14} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '0.72rem', color: 'var(--text-dim)', cursor: 'pointer' }}>
                <span>Weekly</span>
                <ChevronDown size={12} />
              </div>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '6px' }}>
              Total income
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
              $23,194.80
            </div>
          </div>

          <div style={{ height: '1px', background: 'var(--border-subtle)', margin: '10px 0' }} />

          {/* Bottom Metric: Total Paid */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ 
                width: '26px', 
                height: '26px', 
                borderRadius: '50%', 
                background: 'var(--bg-card-subtle)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                color: 'var(--text-muted)'
              }}>
                <Clock size={14} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '0.72rem', color: 'var(--text-dim)', cursor: 'pointer' }}>
                <span>Weekly</span>
                <ChevronDown size={12} />
              </div>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '6px' }}>
              Total paid
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                ${(mandate.spentTotal / 1_000_000 + 8145.20).toFixed(2)}
              </div>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px', 
                fontSize: '0.7rem', 
                color: 'var(--accent-terracotta)', 
                fontWeight: 600,
                cursor: 'pointer' 
              }}>
                <TrendingUp size={12} />
                <span>View on chart mode</span>
              </div>
            </div>
          </div>
        </div>

        {/* CARD 3: System Lock Donut Dial (col-span-2) */}
        <div className="glass-card" style={{ 
          gridColumn: 'span 2', 
          padding: '20px 18px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'space-between',
          minHeight: '210px'
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', textAlign: 'center' }}>
            <div style={{ 
              width: '32px', 
              height: '32px', 
              borderRadius: '50%', 
              background: 'var(--bg-card-subtle)', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center'
            }}>
              <Lock size={15} color="var(--text-main)" />
            </div>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-main)' }}>
              System Lock
            </span>
          </div>

          {/* Circular Donut Ring Gauge (matching 36% Growth rate in screenshot) */}
          <div style={{ position: 'relative', width: '92px', height: '92px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="92" height="92" viewBox="0 0 92 92" style={{ transform: 'rotate(-90deg)' }}>
              {/* Background ring */}
              <circle cx="46" cy="46" r="38" fill="none" stroke="#ebe8e2" strokeWidth="8" />
              {/* Deep charcoal arc */}
              <circle cx="46" cy="46" r="38" fill="none" stroke="#18181b" strokeWidth="8" strokeDasharray="238" strokeDashoffset="70" strokeLinecap="round" />
              {/* Terracotta coral accent arc */}
              <circle cx="46" cy="46" r="38" fill="none" stroke="var(--accent-terracotta)" strokeWidth="8" strokeDasharray="238" strokeDashoffset="180" strokeLinecap="round" />
            </svg>
            <div style={{ position: 'absolute', textAlign: 'center' }}>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
                36%
              </div>
              <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', fontWeight: 600 }}>
                Growth rate
              </div>
            </div>
          </div>

          <div style={{ 
            fontSize: '0.68rem', 
            color: verifier.status === 'ACTIVE' ? 'var(--accent-emerald)' : 'var(--accent-terracotta)', 
            fontWeight: 700 
          }}>
            {verifier.status === 'ACTIVE' ? '● Verifier Online' : '○ Verifier Standby'}
          </div>
        </div>

        {/* CARD 4: 13 Days & Quantum Benchmark Bar Chart (col-span-3) */}
        <div className="glass-card" style={{ 
          gridColumn: 'span 3', 
          padding: '22px 24px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          minHeight: '210px'
        }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ 
                  width: '26px', 
                  height: '26px', 
                  borderRadius: '50%', 
                  background: 'var(--bg-card-subtle)', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  marginBottom: '8px'
                }}>
                  <Clock size={14} color="var(--text-muted)" />
                </div>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-main)' }}>
                  13 Days
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>
                  109 hours, 23 minutes
                </div>
              </div>

              {/* Dot matrix progress indicator from screenshot */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 7px)', gap: '4px', paddingTop: '6px' }}>
                {[...Array(10)].map((_, i) => (
                  <div 
                    key={i} 
                    style={{ 
                      width: '7px', 
                      height: '7px', 
                      borderRadius: '50%', 
                      background: i < 7 ? 'var(--accent-terracotta)' : '#ebe8e2' 
                    }} 
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Mini 2022 vs 2023 Bar Comparison with Terracotta Line from screenshot */}
          <div style={{ 
            background: 'var(--bg-card-subtle)', 
            borderRadius: 'var(--radius-inner)', 
            padding: '10px 14px', 
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            height: '70px',
            position: 'relative'
          }}>
            {/* 2022 Baseline */}
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.66rem', color: 'var(--text-dim)', fontWeight: 600 }}>2022</div>
              <div style={{ width: '28px', height: '24px', background: '#d8d4cb', borderRadius: '4px', margin: '4px auto 0' }} />
            </div>

            {/* Vertical Terracotta Divider */}
            <div style={{ width: '2px', height: '48px', background: 'var(--accent-terracotta)', position: 'absolute', left: '60%', bottom: '10px' }}>
              <div style={{ 
                position: 'absolute', 
                top: '-12px', 
                left: '-16px', 
                background: 'var(--accent-terracotta)', 
                color: '#fff', 
                fontSize: '0.6rem', 
                fontWeight: 700, 
                padding: '1px 6px', 
                borderRadius: 'var(--radius-pill)' 
              }}>
                2023
              </div>
            </div>

            {/* 2023 Optimized */}
            <div style={{ textAlign: 'center', marginLeft: 'auto' }}>
              <div style={{ fontSize: '0.66rem', color: 'var(--text-main)', fontWeight: 700 }}>2023</div>
              <div style={{ width: '28px', height: '42px', background: '#18181b', borderRadius: '4px', margin: '4px auto 0' }} />
            </div>
          </div>
        </div>

        {/* CARD 5: Concentric Circles / Annual Profits (col-span-4) */}
        <div className="glass-card" style={{ 
          gridColumn: 'span 4', 
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <span style={{ fontSize: '0.92rem', fontWeight: 800, color: 'var(--text-main)' }}>
              Annual profits
            </span>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px', 
              fontSize: '0.72rem', 
              color: 'var(--text-secondary)',
              background: 'var(--bg-card-subtle)',
              padding: '4px 10px',
              borderRadius: 'var(--radius-pill)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer'
            }}>
              <span>2023</span>
              <ChevronDown size={12} />
            </div>
          </div>

          {/* Concentric Circles Graphic from Screenshot */}
          <div style={{ 
            position: 'relative', 
            height: '180px', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center' 
          }}>
            {/* Outer Circle $14K */}
            <div style={{ 
              width: '180px', 
              height: '180px', 
              borderRadius: '50%', 
              background: '#fdf2ef', 
              border: '1px solid #f9ded7',
              display: 'flex', 
              alignItems: 'flex-start', 
              justifyContent: 'center',
              paddingTop: '8px'
            }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent-terracotta)' }}>$14K</span>
            </div>

            {/* Middle Circle $9.3K */}
            <div style={{ 
              position: 'absolute', 
              width: '140px', 
              height: '140px', 
              borderRadius: '50%', 
              background: '#fbdcd5', 
              display: 'flex', 
              alignItems: 'flex-start', 
              justifyContent: 'center',
              paddingTop: '8px'
            }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent-terracotta)' }}>$9.3K</span>
            </div>

            {/* Inner Circle $6.8K */}
            <div style={{ 
              position: 'absolute', 
              width: '100px', 
              height: '100px', 
              borderRadius: '50%', 
              background: '#f7beb2', 
              display: 'flex', 
              alignItems: 'flex-start', 
              justifyContent: 'center',
              paddingTop: '8px'
            }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent-terracotta)' }}>$6.8K</span>
            </div>

            {/* Core Solid Terracotta Circle $4K */}
            <div style={{ 
              position: 'absolute', 
              width: '60px', 
              height: '60px', 
              borderRadius: '50%', 
              background: 'var(--accent-terracotta)', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(232, 92, 63, 0.35)'
            }}>
              <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#ffffff' }}>$4K</span>
            </div>
          </div>

          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '10px' }}>
            Quantum vs Baseline: -28.47% Procurement Savings
          </div>
        </div>

        {/* CARD 6: Activity Manager & Filter Widget (col-span-5) */}
        <div className="glass-card" style={{ 
          gridColumn: 'span 5', 
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <span style={{ fontSize: '0.92rem', fontWeight: 800, color: 'var(--text-main)' }}>
                Activity manager
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <SlidersHorizontal size={14} color="var(--text-muted)" style={{ cursor: 'pointer' }} />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Filters</span>
              </div>
            </div>

            {/* Search Input & Tags */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <div style={{ 
                flex: 1, 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                background: 'var(--bg-card-subtle)', 
                padding: '6px 14px', 
                borderRadius: 'var(--radius-pill)',
                border: '1px solid var(--border-subtle)'
              }}>
                <Search size={14} color="var(--text-dim)" />
                <span style={{ fontSize: '0.76rem', color: 'var(--text-dim)' }}>Search in activities...</span>
              </div>
              <span className="badge" style={{ background: '#fdf0ec', color: 'var(--accent-terracotta)', fontSize: '0.68rem', padding: '4px 10px' }}>
                Team ●
              </span>
              <span className="badge" style={{ background: 'var(--bg-card-subtle)', color: 'var(--text-secondary)', fontSize: '0.68rem', padding: '4px 10px' }}>
                Insights ✕
              </span>
            </div>

            {/* $43.20 USD + Vertical Bar Chart and Business plans */}
            <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)' }}>
                  $43.20 <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 500 }}>USD</span>
                </div>
                {/* Mini Bar Graph from Screenshot */}
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: '36px', marginTop: '8px' }}>
                  {[18, 28, 14, 34, 22, 30, 16, 26].map((h, i) => (
                    <div 
                      key={i} 
                      style={{ 
                        width: '4px', 
                        height: `${h}px`, 
                        borderRadius: '2px', 
                        background: i === 3 || i === 5 ? 'var(--accent-terracotta)' : '#d8d4cb' 
                      }} 
                    />
                  ))}
                </div>
              </div>

              <div style={{ flex: 1, borderLeft: '1px solid var(--border-subtle)', paddingLeft: '16px' }}>
                <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '8px' }}>
                  Business plans
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-terracotta)' }} />
                    <span>Bank loans / Mandate</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#18181b' }} />
                    <span>Accounting & Settlement</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-terracotta)' }} />
                    <span>HR management / Guard</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            paddingTop: '12px', 
            borderTop: '1px solid var(--border-subtle)',
            marginTop: '12px'
          }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--accent-emerald)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <CheckCircle size={13} /> {paymentCounts.confirmed} Confirmed
            </span>
            <span style={{ fontSize: '0.72rem', color: 'var(--accent-terracotta)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <XCircle size={13} /> {paymentCounts.rejected} Intercepted
            </span>
          </div>
        </div>

        {/* CARD 7 & 8: Wallet Verification + Main Stocks / Wavy Line (col-span-3) */}
        <div style={{ gridColumn: 'span 3', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Card 7: Wallet Verification with Terracotta Enable button */}
          <div className="glass-card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <div style={{ 
                width: '32px', 
                height: '32px', 
                borderRadius: '50%', 
                background: '#fdf0ec', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center' 
              }}>
                <ShieldCheck size={18} color="var(--accent-terracotta)" />
              </div>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Wallet Verification
              </div>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginBottom: '12px', lineHeight: 1.3 }}>
              Enable 2-step verification to secure your autonomous wallet.
            </div>
            <button className="btn btn-primary" style={{ width: '100%', padding: '7px 0', fontSize: '0.78rem' }}>
              Enable
            </button>
          </div>

          {/* Card 8: Main Stocks & Wavy Line Chart */}
          <div className="glass-card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Main Stocks
              </div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-main)' }}>
                $16,073.49
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px' }}>
              <div style={{ fontSize: '0.66rem', color: 'var(--text-dim)' }}>
                Extended & Limited
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--accent-terracotta)', fontWeight: 700 }}>
                +9.3%
              </div>
            </div>

            {/* Wavy Terracotta SVG Curve from Screenshot */}
            <div style={{ marginTop: '10px' }}>
              <svg width="100%" height="32" viewBox="0 0 200 32" fill="none">
                <path 
                  d="M0 16 C 25 8, 45 26, 75 14 C 105 4, 125 24, 155 12 C 175 4, 190 20, 200 14" 
                  stroke="var(--accent-terracotta)" 
                  strokeWidth="2.5" 
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};
