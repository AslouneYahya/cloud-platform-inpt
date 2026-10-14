import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMe, logout } from '../api/auth.js';
import VmManager from '../components/VmManager.jsx';

/* ─── Design tokens ─────────────────────────────────────────────────────── */
const INPT_BLUE    = '#003366';
const INPT_BLUE_LT = '#004a99';
const BG_PAGE      = '#f0f4f8';
const BG_CARD      = '#ffffff';
const STATUS_COLORS = {
  active:   { bg: '#e6f4ea', color: '#1e7e34', dot: '#28a745' },
  inactive: { bg: '#fdecea', color: '#c0392b', dot: '#dc3545' },
  pending:  { bg: '#fff3cd', color: '#856404', dot: '#ffc107' },
  default:  { bg: '#e9ecef', color: '#495057', dot: '#6c757d' },
};

/* ─── Styles ─────────────────────────────────────────────────────────────── */
const styles = {
  page: {
    minHeight: '100vh',
    background: BG_PAGE,
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
  },
  navbar: {
    background: INPT_BLUE,
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 2rem',
    height: '60px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
  },
  navBrand: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.65rem',
    fontWeight: '700',
    fontSize: '1.05rem',
    letterSpacing: '-0.3px',
  },
  navBrandIcon: {
    width: '34px',
    height: '34px',
    borderRadius: '8px',
    background: 'rgba(255,255,255,0.18)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: '800',
    fontSize: '0.85rem',
  },
  navRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  navEmail: {
    fontSize: '0.85rem',
    color: 'rgba(255,255,255,0.80)',
  },
  logoutBtn: {
    background: 'rgba(255,255,255,0.15)',
    color: '#fff',
    border: '1.5px solid rgba(255,255,255,0.35)',
    borderRadius: '6px',
    padding: '0.35rem 0.85rem',
    fontWeight: '600',
    fontSize: '0.85rem',
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  main: {
    maxWidth: '860px',
    margin: '0 auto',
    padding: '2.5rem 1.25rem',
  },
  welcomeCard: {
    background: BG_CARD,
    borderRadius: '12px',
    boxShadow: '0 2px 16px rgba(0,0,0,0.08)',
    padding: '2rem 2.25rem',
    marginBottom: '1.5rem',
  },
  welcomeHeading: {
    color: INPT_BLUE,
    fontWeight: '700',
    fontSize: '1.5rem',
    margin: '0 0 0.25rem 0',
  },
  welcomeSub: {
    color: '#718096',
    fontSize: '0.9rem',
    margin: 0,
  },
  infoCard: {
    background: BG_CARD,
    borderRadius: '12px',
    boxShadow: '0 2px 16px rgba(0,0,0,0.08)',
    padding: '1.5rem 2.25rem',
  },
  infoCardTitle: {
    color: INPT_BLUE,
    fontWeight: '700',
    fontSize: '1rem',
    marginTop: 0,
    marginBottom: '1rem',
    paddingBottom: '0.65rem',
    borderBottom: '1.5px solid #e2e8f0',
  },
  infoRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.55rem 0',
    borderBottom: '1px solid #f0f4f8',
  },
  infoLabel: {
    color: '#718096',
    fontSize: '0.875rem',
    fontWeight: '500',
  },
  infoValue: {
    color: '#2d3748',
    fontSize: '0.875rem',
    fontWeight: '600',
    textAlign: 'right',
    maxWidth: '60%',
    wordBreak: 'break-all',
  },
  statusBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    borderRadius: '999px',
    padding: '0.2rem 0.7rem',
    fontSize: '0.8rem',
    fontWeight: '600',
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  // Loader / Skeleton
  loadingWrapper: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '60vh',
    gap: '1rem',
  },
  spinner: {
    width: '40px',
    height: '40px',
    border: `4px solid #e2e8f0`,
    borderTopColor: INPT_BLUE,
    borderRadius: '50%',
    animation: 'spin 0.75s linear infinite',
  },
  spinnerLabel: {
    color: '#718096',
    fontSize: '0.9rem',
  },
};

/* ─── Inject spinner keyframe once ──────────────────────────────────────── */
if (typeof document !== 'undefined' && !document.getElementById('dash-spin-style')) {
  const styleEl = document.createElement('style');
  styleEl.id = 'dash-spin-style';
  styleEl.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
  document.head.appendChild(styleEl);
}

/* ─── Status badge helper ────────────────────────────────────────────────── */
function StatusBadge({ status }) {
  const s = status ? status.toLowerCase() : 'default';
  const theme = STATUS_COLORS[s] || STATUS_COLORS.default;
  return (
    <span style={{ ...styles.statusBadge, background: theme.bg, color: theme.color }}>
      <span style={{ ...styles.statusDot, background: theme.dot }} />
      {status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown'}
    </span>
  );
}

/* ─── Component ──────────────────────────────────────────────────────────── */
export default function DashboardPage() {
  const navigate = useNavigate();

  const [user,         setUser]         = useState(null);
  const [pageLoading,  setPageLoading]  = useState(true);
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [btnHovered,   setBtnHovered]   = useState(false);

  /* On mount: verify session by fetching the current user profile */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await getMe();
        if (!cancelled) {
          const payload = res.data?.data || res.data;
          setUser(payload);
        }
      } catch (err) {
        if (cancelled) return;
        // 401 Unauthorized → session missing or expired; redirect to login
        if (err?.response?.status === 401) {
          navigate('/login', { replace: true });
        } else {
          // For other errors, still redirect to login as a safe fallback
          navigate('/login', { replace: true });
        }
      } finally {
        if (!cancelled) setPageLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [navigate]);

  async function handleLogout() {
    setLogoutLoading(true);
    try {
      await logout();
    } catch {
      // Even if the server-side logout fails, we clear local state
      // and redirect to prevent access to protected content.
    } finally {
      navigate('/login', { replace: true });
    }
  }

  /* ── Loading state ─────────────────────────────────────────────────────── */
  if (pageLoading) {
    return (
      <div style={styles.page}>
        <div style={styles.loadingWrapper}>
          <div style={styles.spinner} aria-hidden="true" />
          <span style={styles.spinnerLabel}>Loading your workspace…</span>
        </div>
      </div>
    );
  }

  /* ── Authenticated view ───────────────────────────────────────────────── */
  const displayName = user?.name || user?.email || 'User';
  const email       = user?.email || '—';
  const role        = user?.role  || '—';
  const status      = user?.status || user?.accountStatus || 'active';
  const createdAt   = user?.createdAt
    ? new Date(user.createdAt).toLocaleDateString('en-GB', {
        day: 'numeric', month: 'long', year: 'numeric',
      })
    : '—';

  return (
    <div style={styles.page}>
      {/* Navbar */}
      <nav style={styles.navbar} aria-label="Main navigation">
        <div style={styles.navBrand}>
          <div style={styles.navBrandIcon}>CP</div>
          Cloud Platform — INPT
        </div>
        <div style={styles.navRight}>
          <span style={styles.navEmail}>{email}</span>
          <button
            onClick={handleLogout}
            disabled={logoutLoading}
            onMouseEnter={() => setBtnHovered(true)}
            onMouseLeave={() => setBtnHovered(false)}
            style={{
              ...styles.logoutBtn,
              ...(btnHovered && !logoutLoading
                ? { background: 'rgba(255,255,255,0.28)' }
                : {}),
              ...(logoutLoading ? { opacity: 0.65, cursor: 'not-allowed' } : {}),
            }}
          >
            {logoutLoading ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </nav>

      {/* Main content */}
      <main style={styles.main}>
        {/* Welcome card */}
        <div style={styles.welcomeCard}>
          <h1 style={styles.welcomeHeading}>Welcome, {displayName} 👋</h1>
          <p style={styles.welcomeSub}>
            You are successfully authenticated to the INPT Cloud Platform.
          </p>
        </div>

        {/* Account info card */}
        <div style={styles.infoCard}>
          <h2 style={styles.infoCardTitle}>Account Details</h2>

          <div style={styles.infoRow}>
            <span style={styles.infoLabel}>Email address</span>
            <span style={styles.infoValue}>{email}</span>
          </div>

          {user?.name && (
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>Full name</span>
              <span style={styles.infoValue}>{user.name}</span>
            </div>
          )}

          <div style={styles.infoRow}>
            <span style={styles.infoLabel}>Role</span>
            <span style={styles.infoValue}>{role}</span>
          </div>

          <div style={styles.infoRow}>
            <span style={styles.infoLabel}>Account status</span>
            <span style={styles.infoValue}>
              <StatusBadge status={status} />
            </span>
          </div>

          {createdAt !== '—' && (
            <div style={{ ...styles.infoRow, borderBottom: 'none' }}>
              <span style={styles.infoLabel}>Member since</span>
              <span style={styles.infoValue}>{createdAt}</span>
            </div>
          )}
        </div>

        {/* US2: Virtual Machine Lifecycle & Monitoring Module */}
        <VmManager />
      </main>
    </div>
  );
}
