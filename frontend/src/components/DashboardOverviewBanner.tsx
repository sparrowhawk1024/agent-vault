import React from 'react';
import type { DashboardOverview } from '../api';
import { 
  Clock,
  Lock,
  ChevronDown,
  Edit2,
  TrendingUp,
  Search,
  SlidersHorizontal,
  Share2,
  Plus,
  X,
  ArrowRight,
  Smile,
  Meh,
  Frown,
  BarChart2,
  Activity
} from 'lucide-react';

interface Props {
  overview: DashboardOverview | null;
  loading: boolean;
  onRefresh: () => void;
  onOpenDemo: () => void;
  onNavigateTab: (tab: 'mandate' | 'agent' | 'payments' | 'autorefill' | 'security' | 'qpiai' | 'audit') => void;
}

export const DashboardOverviewBanner: React.FC<Props> = ({ 
  overview, 
  loading, 
  onRefresh,
  onOpenDemo,
  onNavigateTab
}) => {
  if (!overview) {
    return (
      <div className="glass-card" style={{ padding: '24px', textAlign: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', color: 'var(--text-muted)' }}>
          <Activity className="glow-animation" size={18} color="var(--accent-terracotta)" />
          <span>Connecting to AgentVault core services & local Anvil chain...</span>
        </div>
      </div>
    );
  }

  const { mandate, verifier } = overview;
  const isMandateActive = mandate.exists && mandate.isActive;

  return (
    <div style={{ width: '100%', maxWidth: '1260px', margin: '0 auto' }}>
      {/* 1. Hero Greeting & Date/Action Strip (Exact layout from screenshot) */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: '16px',
        flexWrap: 'wrap',
        gap: '14px'
      }}>
        {/* Left: Date Card + Terracotta Action Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Circular Date Pill */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '12px',
            background: '#ffffff',
            padding: '6px 16px 6px 6px',
            borderRadius: 'var(--radius-pill)',
            border: '1px solid var(--border-subtle)',
            boxShadow: 'var(--shadow-card)'
          }}>
            <div style={{ 
              width: '40px', 
              height: '40px', 
              borderRadius: '50%', 
              background: '#ffffff',
              border: '1.5px solid #ebe8e2',
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              fontSize: '1.15rem',
              fontWeight: 800,
              color: 'var(--text-main)',
              fontFamily: 'var(--font-mono)'
            }}>
              19
            </div>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.2 }}>
                Tue,
              </div>
              <div style={{ fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-muted)', lineHeight: 1.2 }}>
                December
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

          {/* Calendar / Sync Button */}
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
            <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
              Hey, Need help? 👋
            </div>
            <div style={{ fontSize: '0.92rem', color: 'var(--text-dim)', fontStyle: 'normal' }}>
              |Just ask me anything!
            </div>
          </div>
          <div className="icon-circle-btn" style={{ width: '42px', height: '42px' }}>
            <Activity size={18} color="var(--accent-terracotta)" />
          </div>
        </div>
      </div>

      {/* 2. Bento Grid: Perfectly Aligned 3-Column Matched-Height Layout */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'minmax(290px, 1.05fr) minmax(380px, 1.45fr) minmax(280px, 1.05fr)', 
        gridTemplateRows: '210px 290px',
        gap: '16px',
        alignItems: 'stretch',
        boxSizing: 'border-box'
      }}>

        {/* ================= ROW 1, COL 1: VISA / DIRECT DEBITS MANDATE CARD ================= */}
        <div style={{ display: 'flex', gap: '8px', gridRow: '1', gridColumn: '1', height: '100%', boxSizing: 'border-box' }}>
          {/* Vertical Floating Pill Toolbar on Left Edge */}
          <div style={{ 
            width: '38px', 
            background: '#ffffff', 
            borderRadius: 'var(--radius-pill)', 
            border: '1px solid var(--border-card)',
            boxShadow: 'var(--shadow-card)',
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'space-around',
            padding: '12px 0'
          }}>
            <button 
              onClick={() => onNavigateTab('mandate')} 
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              title="Create Mandate"
            >
              <Plus size={16} />
            </button>
            <button 
              onClick={() => onNavigateTab('audit')} 
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              title="Audit Logs"
            >
              <Share2 size={15} />
            </button>
          </div>

          {/* Main VISA Card */}
          <div className="glass-card" style={{ 
            flex: 1, 
            padding: '16px 18px', 
            display: 'flex', 
            flexDirection: 'column', 
            justifyContent: 'space-between',
            height: '100%',
            boxSizing: 'border-box'
          }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 800, fontSize: '0.95rem', letterSpacing: '0.04em', color: 'var(--text-main)' }}>
                  VISA
                </span>
                <div 
                  onClick={() => onNavigateTab('mandate')}
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '4px', 
                    fontSize: '0.7rem', 
                    color: 'var(--text-secondary)',
                    background: 'var(--bg-card-subtle)',
                    padding: '3px 8px',
                    borderRadius: 'var(--radius-pill)',
                    border: '1px solid var(--border-subtle)',
                    cursor: 'pointer'
                  }}
                >
                  <span>Direct Debits</span>
                  <ChevronDown size={11} />
                </div>
              </div>

              <div style={{ fontSize: '0.66rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                Linked to main account
              </div>
              <div style={{ 
                fontSize: '1.12rem', 
                fontWeight: 700, 
                fontFamily: 'var(--font-mono)', 
                color: 'var(--text-main)',
                letterSpacing: '0.06em',
                margin: '2px 0 8px 0'
              }}>
                •••• 2719
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button 
                  className="btn btn-dark btn-sm" 
                  onClick={() => onNavigateTab('autorefill')}
                  style={{ padding: '5px 16px', fontSize: '0.74rem' }}
                >
                  Receive
                </button>
                <button 
                  className="btn btn-secondary btn-sm" 
                  onClick={() => onNavigateTab('agent')}
                  style={{ padding: '5px 16px', fontSize: '0.74rem' }}
                >
                  Send
                </button>
              </div>
            </div>

            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              paddingTop: '6px',
              borderTop: '1px solid var(--border-subtle)'
            }}>
              <div>
                <div style={{ fontSize: '0.64rem', color: 'var(--text-dim)' }}>
                  Monthly regular fee
                </div>
                <div style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-main)' }}>
                  $25.00
                </div>
              </div>
              <div 
                onClick={() => onNavigateTab('mandate')}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '4px', 
                  fontSize: '0.67rem', 
                  color: 'var(--accent-terracotta)', 
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <Edit2 size={11} />
                <span>Edit cards limitation</span>
              </div>
            </div>
          </div>
        </div>

        {/* ================= ROW 1, COL 2: INCOME/PAID STATS + SYSTEM LOCK ================= */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '14px', gridRow: '1', gridColumn: '2', height: '100%', boxSizing: 'border-box' }}>
          
          {/* Card: Total Income & Total Paid */}
          <div className="glass-card" style={{ 
            padding: '16px 18px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            height: '100%',
            boxSizing: 'border-box'
          }}>
            {/* Income */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ 
                  width: '22px', 
                  height: '22px', 
                  borderRadius: '50%', 
                  background: 'var(--bg-card-subtle)', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  color: 'var(--text-muted)'
                }}>
                  <Clock size={12} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '0.67rem', color: 'var(--text-dim)', cursor: 'pointer' }}>
                  <span>Weekly</span>
                  <ChevronDown size={11} />
                </div>
              </div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                Total income
              </div>
              <div style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                $23,194.80
              </div>
            </div>

            <div style={{ height: '1px', background: 'var(--border-subtle)', margin: '3px 0' }} />

            {/* Paid */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ 
                  width: '22px', 
                  height: '22px', 
                  borderRadius: '50%', 
                  background: 'var(--bg-card-subtle)', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  color: 'var(--text-muted)'
                }}>
                  <Clock size={12} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '0.67rem', color: 'var(--text-dim)', cursor: 'pointer' }}>
                  <span>Weekly</span>
                  <ChevronDown size={11} />
                </div>
              </div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                Total paid
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                <div style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                  $8,145.20
                </div>
                <div 
                  onClick={() => onNavigateTab('payments')}
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '4px', 
                    fontSize: '0.66rem', 
                    color: 'var(--accent-terracotta)', 
                    fontWeight: 600,
                    cursor: 'pointer' 
                  }}
                >
                  <TrendingUp size={11} />
                  <span>View on chart mode</span>
                </div>
              </div>
            </div>
          </div>

          {/* Card: System Lock Circular Meter */}
          <div className="glass-card" style={{ 
            padding: '14px 12px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px' }}>
              <div style={{ 
                width: '26px', 
                height: '26px', 
                borderRadius: '50%', 
                background: 'var(--bg-card-subtle)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center'
              }}>
                <Lock size={13} color="var(--text-main)" />
              </div>
              <span style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-main)' }}>
                System Lock
              </span>
            </div>

            {/* Circular Donut Gauge */}
            <div style={{ position: 'relative', width: '80px', height: '80px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="80" height="80" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="32" fill="none" stroke="#ebe8e2" strokeWidth="7" />
                <circle cx="40" cy="40" r="32" fill="none" stroke="#18181b" strokeWidth="7" strokeDasharray="201" strokeDashoffset="60" strokeLinecap="round" transform="rotate(-90 40 40)" />
                <circle cx="40" cy="40" r="32" fill="none" stroke="var(--accent-terracotta)" strokeWidth="7" strokeDasharray="201" strokeDashoffset="150" strokeLinecap="round" transform="rotate(-90 40 40)" />
              </svg>
              <div style={{ position: 'absolute', textAlign: 'center' }}>
                <div style={{ fontSize: '0.9rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
                  36%
                </div>
                <div style={{ fontSize: '0.56rem', color: 'var(--text-dim)', fontWeight: 600 }}>
                  Growth rate
                </div>
              </div>
            </div>

            <div style={{ 
              fontSize: '0.62rem', 
              color: isMandateActive ? 'var(--accent-emerald)' : 'var(--accent-terracotta)', 
              fontWeight: 700 
            }}>
              {verifier.status === 'ACTIVE' ? '● Verifier Online' : '○ Standby'}
            </div>
          </div>

        </div>

        {/* ================= ROW 1, COL 3: 13 DAYS + 2022/2023 CHART ================= */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '14px', gridRow: '1', gridColumn: '3', height: '100%', boxSizing: 'border-box' }}>
          
          {/* Card: 13 Days */}
          <div className="glass-card" style={{ 
            padding: '14px 12px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            height: '100%',
            boxSizing: 'border-box'
          }}>
            <div>
              <div style={{ 
                width: '22px', 
                height: '22px', 
                borderRadius: '50%', 
                background: 'var(--bg-card-subtle)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                marginBottom: '2px'
              }}>
                <Clock size={12} color="var(--text-muted)" />
              </div>
              <div style={{ fontSize: '1.12rem', fontWeight: 800, color: 'var(--text-main)' }}>
                13 Days
              </div>
              <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)' }}>
                109 hours, 23 minutes
              </div>
            </div>

            {/* 10-Dot Matrix Indicator */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 7px)', gap: '4px', paddingTop: '4px' }}>
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

          {/* Card: 2022 vs 2023 Mini Comparison Bar Chart */}
          <div className="glass-card" style={{ 
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            position: 'relative',
            height: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <div style={{ 
                width: '20px', 
                height: '20px', 
                borderRadius: '50%', 
                background: 'var(--bg-card-subtle)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center'
              }}>
                <BarChart2 size={11} color="var(--text-muted)" />
              </div>
            </div>

            {/* Visual Bars with Red Marker */}
            <div style={{ 
              display: 'flex', 
              alignItems: 'flex-end', 
              justifyContent: 'space-around', 
              height: '80px', 
              position: 'relative',
              paddingBottom: '2px'
            }}>
              {/* 2022 Bar */}
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)', fontWeight: 600 }}>2022</div>
                <div style={{ width: '20px', height: '24px', background: '#d8d4cb', borderRadius: '3px', margin: '2px auto 0' }} />
              </div>

              {/* Vertical Red Accent Divider with 2023 Pill */}
              <div style={{ 
                width: '2px', 
                height: '52px', 
                background: 'var(--accent-terracotta)', 
                position: 'absolute', 
                left: '62%', 
                bottom: '2px' 
              }}>
                <div style={{ 
                  position: 'absolute', 
                  top: '-12px', 
                  left: '-13px', 
                  background: 'var(--accent-terracotta)', 
                  color: '#ffffff', 
                  fontSize: '0.56rem', 
                  fontWeight: 700, 
                  padding: '1px 5px', 
                  borderRadius: 'var(--radius-pill)' 
                }}>
                  2023
                </div>
              </div>

              {/* 2023 Bar */}
              <div style={{ textAlign: 'center' }}>
                <div style={{ width: '20px', height: '46px', background: '#18181b', borderRadius: '3px', margin: '2px auto 0' }} />
              </div>
            </div>
          </div>

        </div>

        {/* ================= ROW 2, COL 1: CONCENTRIC CIRCLES / ANNUAL PROFITS ================= */}
        <div className="glass-card" style={{ 
          gridRow: '2', 
          gridColumn: '1', 
          padding: '18px 20px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          height: '100%',
          boxSizing: 'border-box'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.88rem', fontWeight: 800, color: 'var(--text-main)' }}>
              Annual profits
            </span>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px', 
              fontSize: '0.68rem', 
              color: 'var(--text-secondary)',
              background: 'var(--bg-card-subtle)',
              padding: '2px 8px',
              borderRadius: 'var(--radius-pill)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer'
            }}>
              <span>2023</span>
              <ChevronDown size={11} />
            </div>
          </div>

          {/* Exact Concentric Sunrise Arcs SVG with Center Red Circle */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg viewBox="0 0 200 170" width="100%" height="165">
              {/* Outer Layer $14K */}
              <circle cx="100" cy="115" r="72" fill="#fdf0ec" />
              {/* Medium Layer $9.3K */}
              <circle cx="100" cy="125" r="54" fill="#fbdcd5" />
              {/* Inner Layer $6.8K */}
              <circle cx="100" cy="135" r="38" fill="#f7b7a8" />
              {/* Core Solid Red Circle $4K */}
              <circle cx="100" cy="148" r="20" fill="#e85c3f" />

              {/* Text labels positioned cleanly above each rim */}
              <text x="100" y="58" textAnchor="middle" fontSize="11" fontWeight="700" fill="#e85c3f">$14K</text>
              <text x="100" y="86" textAnchor="middle" fontSize="11" fontWeight="700" fill="#e85c3f">$9.3K</text>
              <text x="100" y="112" textAnchor="middle" fontSize="11" fontWeight="700" fill="#e85c3f">$6.8K</text>
              <text x="100" y="152" textAnchor="middle" fontSize="10" fontWeight="800" fill="#ffffff">$4K</text>
            </svg>
          </div>

          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textAlign: 'center' }}>
            Baseline vs QpiAI: -28.47% Procurement Costs
          </div>
        </div>

        {/* ================= ROW 2, COL 2: ACTIVITY MANAGER (WITH WALLET VERIFICATION) ================= */}
        <div className="glass-card" style={{ 
          gridRow: '2', 
          gridColumn: '2', 
          padding: '18px 20px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          height: '100%',
          boxSizing: 'border-box'
        }}>
          <div>
            {/* Header: Activity manager + Filters */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 800, color: 'var(--text-main)' }}>
                Activity manager
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                <SlidersHorizontal size={13} color="var(--text-muted)" />
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Filters</span>
              </div>
            </div>

            {/* Search Bar + Filter Tags */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <div style={{ 
                flex: 1, 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                background: 'var(--bg-card-subtle)', 
                padding: '5px 12px', 
                borderRadius: 'var(--radius-pill)',
                border: '1px solid var(--border-subtle)'
              }}>
                <Search size={13} color="var(--text-dim)" />
                <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>Search in activities...</span>
              </div>
              <span className="badge" style={{ background: '#fdf0ec', color: 'var(--accent-terracotta)', fontSize: '0.64rem', padding: '3px 8px' }}>
                Team ●
              </span>
              <span className="badge" style={{ background: 'var(--bg-card-subtle)', color: 'var(--text-secondary)', fontSize: '0.64rem', padding: '3px 8px' }}>
                Insights ✕
              </span>
              <span className="badge" style={{ background: 'var(--bg-card-subtle)', color: 'var(--text-secondary)', fontSize: '0.64rem', padding: '3px 8px' }}>
                Today ✕
              </span>
            </div>

            {/* 3 Columns: $43.20 + Business plans + Wallet Verification */}
            <div style={{ display: 'grid', gridTemplateColumns: '115px 1fr 1fr', gap: '14px', alignItems: 'center' }}>
              
              {/* Col A: $43.20 USD + Mini Bars */}
              <div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
                  $43.20 <span style={{ fontSize: '0.64rem', color: 'var(--text-dim)', fontWeight: 500 }}>USD</span>
                </div>
                {/* 8 Mini Vertical Bars from Screenshot */}
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

              {/* Col B: Business plans with 3 dots */}
              <div style={{ borderLeft: '1px solid var(--border-subtle)', paddingLeft: '12px' }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                  Business plans
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.66rem', color: 'var(--text-secondary)' }}>
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-terracotta)' }} />
                    <span>Bank loans</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.66rem', color: 'var(--text-secondary)' }}>
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#18181b' }} />
                    <span>Accounting</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.66rem', color: 'var(--text-secondary)' }}>
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-terracotta)' }} />
                    <span>HR management</span>
                  </div>
                </div>
              </div>

              {/* Col C: Wallet Verification Sub-Card with Terracotta [ Enable ] Button */}
              <div style={{ 
                background: 'var(--bg-card-subtle)', 
                borderRadius: 'var(--radius-inner)', 
                padding: '10px 12px', 
                border: '1px solid var(--border-subtle)' 
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px' }}>
                  <div style={{ width: '16px', height: '16px', borderRadius: '50%', background: '#fdf0ec', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Activity size={10} color="var(--accent-terracotta)" />
                  </div>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-main)' }}>
                    Wallet Verification
                  </div>
                </div>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)', marginBottom: '6px', lineHeight: 1.2 }}>
                  Enable 2-step verification to secure your wallet.
                </div>
                <button 
                  className="btn btn-primary btn-sm" 
                  onClick={() => onNavigateTab('security')}
                  style={{ width: '100%', padding: '4px 0', fontSize: '0.72rem' }}
                >
                  Enable
                </button>
              </div>

            </div>
          </div>

          {/* Bottom Summary Bar */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            paddingTop: '6px', 
            borderTop: '1px solid var(--border-subtle)' 
          }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>
              ● {mandate.spentTotal > 0 ? `${(mandate.spentTotal / 1_000_000).toFixed(2)} USDC Disbursed` : 'Ledger Reconciled'}
            </span>
            <span style={{ fontSize: '0.68rem', color: 'var(--accent-terracotta)', fontWeight: 600 }}>
              Zero Unauthorized Disbursements
            </span>
          </div>
        </div>

        {/* ================= ROW 2, COL 3: MAIN STOCKS (WAVY) + REVIEW RATING ================= */}
        <div style={{ 
          gridRow: '2', 
          gridColumn: '3', 
          display: 'grid', 
          gridTemplateRows: '1fr 1fr', 
          gap: '12px',
          height: '100%',
          boxSizing: 'border-box'
        }}>
          
          {/* Main Stocks Card with Wavy Curve */}
          <div className="glass-card" style={{ 
            padding: '12px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            height: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ 
                width: '18px', 
                height: '18px', 
                borderRadius: '50%', 
                background: 'var(--bg-card-subtle)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center' 
              }}>
                <Activity size={10} color="var(--text-muted)" />
              </div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--text-main)' }}>
                $16,073.49
              </div>
            </div>

            {/* Wavy Red SVG Line */}
            <div style={{ margin: '2px 0' }}>
              <svg width="100%" height="26" viewBox="0 0 200 26" fill="none">
                <path 
                  d="M0 13 C 25 5, 45 22, 75 11 C 105 2, 125 20, 155 9 C 175 3, 190 17, 200 11" 
                  stroke="var(--accent-terracotta)" 
                  strokeWidth="2.2" 
                  strokeLinecap="round"
                />
              </svg>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.1 }}>
                  Main Stocks
                </div>
                <div style={{ fontSize: '0.58rem', color: 'var(--text-dim)' }}>
                  Extended & Limited
                </div>
              </div>
              <div style={{ 
                fontSize: '0.66rem', 
                color: 'var(--accent-terracotta)', 
                fontWeight: 700,
                background: '#fdf0ec',
                padding: '1px 6px',
                borderRadius: 'var(--radius-pill)'
              }}>
                +9.3%
              </div>
            </div>
          </div>

          {/* Review Rating Card */}
          <div className="glass-card" style={{ 
            padding: '10px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            height: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '3px' }}>
                <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#18181b' }} />
                <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#d8d4cb' }} />
                <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#d8d4cb' }} />
              </div>
              <X size={11} color="var(--text-dim)" style={{ cursor: 'pointer' }} />
            </div>

            <div>
              <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)' }}>
                Review rating
              </div>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.2 }}>
                How is your business management going?
              </div>
            </div>

            {/* 5 Smiley Reaction Buttons from Screenshot */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '2px' }}>
              {[
                <Frown key="1" size={12} />,
                <Frown key="2" size={12} />,
                <Meh key="3" size={12} />,
                <Smile key="4" size={12} />,
                <Smile key="5" size={12} />
              ].map((icon, idx) => (
                <div 
                  key={idx} 
                  style={{ 
                    width: '24px', 
                    height: '18px', 
                    borderRadius: 'var(--radius-pill)', 
                    background: 'var(--bg-card-subtle)', 
                    border: '1px solid var(--border-subtle)',
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    color: 'var(--text-muted)',
                    cursor: 'pointer'
                  }}
                >
                  {icon}
                </div>
              ))}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};
