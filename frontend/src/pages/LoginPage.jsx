import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/auth.js';

/* ─── Design tokens ─────────────────────────────────────────────────────── */
const INPT_BLUE     = '#003366';
const INPT_BLUE_LT  = '#004a99';
const ERROR_RED     = '#c0392b';
const BORDER_COLOR  = '#cbd5e0';
const BG_PAGE       = '#f0f4f8';
const BG_CARD       = '#ffffff';

/* ─── Inline style objects ───────────────────────────────────────────────── */
const styles = {
  page: {
    minHeight: '100vh',
    background: BG_PAGE,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
    padding: '1rem',
  },
  card: {
    background: BG_CARD,
    borderRadius: '12px',
    boxShadow: '0 4px 24px rgba(0,0,0,0.10)',
    padding: '2.5rem 2.25rem',
    width: '100%',
    maxWidth: '420px',
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: '1.75rem',
    gap: '0.75rem',
  },
  logoIcon: {
    width: '44px',
    height: '44px',
    borderRadius: '10px',
    background: INPT_BLUE,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    fontWeight: '700',
    fontSize: '1.15rem',
    letterSpacing: '-0.5px',
    flexShrink: 0,
  },
  logoText: {
    display: 'flex',
    flexDirection: 'column',
    lineHeight: 1.2,
  },
  logoTitle: {
    color: INPT_BLUE,
    fontWeight: '700',
    fontSize: '1.1rem',
  },
  logoSubtitle: {
    color: '#718096',
    fontSize: '0.78rem',
  },
  heading: {
    color: INPT_BLUE,
    fontWeight: '700',
    fontSize: '1.45rem',
    textAlign: 'center',
    marginBottom: '0.25rem',
    marginTop: 0,
  },
  subheading: {
    color: '#718096',
    fontSize: '0.875rem',
    textAlign: 'center',
    marginBottom: '1.75rem',
    marginTop: 0,
  },
  formGroup: {
    marginBottom: '1rem',
  },
  label: {
    display: 'block',
    color: '#2d3748',
    fontWeight: '600',
    fontSize: '0.85rem',
    marginBottom: '0.35rem',
  },
  input: {
    width: '100%',
    padding: '0.65rem 0.85rem',
    border: `1.5px solid ${BORDER_COLOR}`,
    borderRadius: '7px',
    fontSize: '0.95rem',
    color: '#1a202c',
    background: '#f7fafc',
    outline: 'none',
    boxSizing: 'border-box',
    transition: 'border-color 0.15s',
  },
  inputFocus: {
    borderColor: INPT_BLUE,
    background: '#fff',
  },
  inputError: {
    borderColor: ERROR_RED,
  },
  fieldHint: {
    fontSize: '0.75rem',
    color: '#a0aec0',
    marginTop: '0.25rem',
  },
  errorBox: {
    background: '#fdecea',
    border: `1px solid ${ERROR_RED}`,
    color: ERROR_RED,
    borderRadius: '7px',
    padding: '0.65rem 0.9rem',
    fontSize: '0.875rem',
    marginBottom: '1rem',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '0.5rem',
  },
  submitBtn: {
    width: '100%',
    padding: '0.75rem',
    background: INPT_BLUE,
    color: '#fff',
    border: 'none',
    borderRadius: '7px',
    fontWeight: '700',
    fontSize: '1rem',
    cursor: 'pointer',
    marginTop: '0.5rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.6rem',
    transition: 'background 0.15s',
  },
  submitBtnHover: {
    background: INPT_BLUE_LT,
  },
  submitBtnDisabled: {
    background: '#90a4c0',
    cursor: 'not-allowed',
  },
  spinner: {
    width: '18px',
    height: '18px',
    border: '2.5px solid rgba(255,255,255,0.4)',
    borderTopColor: '#fff',
    borderRadius: '50%',
    animation: 'spin 0.7s linear infinite',
    display: 'inline-block',
    flexShrink: 0,
  },
  footer: {
    textAlign: 'center',
    color: '#a0aec0',
    fontSize: '0.78rem',
    marginTop: '2rem',
  },
};

/* ─── Spin keyframe injected once ───────────────────────────────────────── */
if (typeof document !== 'undefined' && !document.getElementById('login-spin-style')) {
  const styleEl = document.createElement('style');
  styleEl.id = 'login-spin-style';
  styleEl.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
  document.head.appendChild(styleEl);
}

/* ─── Validation helpers ─────────────────────────────────────────────────── */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateEmail(val) {
  return EMAIL_RE.test(val);
}

function validatePassword(val) {
  return val.length >= 8;
}

/* ─── Component ──────────────────────────────────────────────────────────── */
export default function LoginPage() {
  const navigate = useNavigate();

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  // Hover / focus state for styling
  const [emailFocused,    setEmailFocused]    = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [btnHovered,      setBtnHovered]      = useState(false);

  // Client-side format hints (non-blocking — shown only as hints)
  const emailInvalid    = email.length > 0    && !validateEmail(email);
  const passwordShort   = password.length > 0 && !validatePassword(password);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    // Basic client-side gate: prevent submission if obviously wrong format
    if (!validateEmail(email) || !validatePassword(password)) {
      // Soft UX: just show a neutral message, don't reveal which field failed
      setError('Please enter a valid email and a password of at least 8 characters.');
      return;
    }

    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      // Anti-enumeration: never disclose whether the email exists or not.
      // Use a single generic message regardless of the server's actual error.
      const serverMsg = err?.response?.data?.message;
      if (serverMsg && typeof serverMsg === 'string' && serverMsg.length < 120) {
        // Accept a generic server message only if it doesn't reveal specifics
        const lower = serverMsg.toLowerCase();
        const isSafe =
          !lower.includes('email') &&
          !lower.includes('not found') &&
          !lower.includes('user') &&
          !lower.includes('account') &&
          !lower.includes('exist');
        setError(isSafe ? serverMsg : 'Invalid credentials. Please try again.');
      } else {
        setError('Invalid credentials. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  const isDisabled = loading;

  return (
    <div style={styles.page}>
      <div style={styles.card}>

        {/* Logo / Branding */}
        <div style={styles.logo}>
          <div style={styles.logoIcon}>CP</div>
          <div style={styles.logoText}>
            <span style={styles.logoTitle}>Cloud Platform</span>
            <span style={styles.logoSubtitle}>Institut National des Postes et Télécommunications</span>
          </div>
        </div>

        <h1 style={styles.heading}>Sign in</h1>
        <p style={styles.subheading}>Enter your INPT credentials to continue</p>

        {/* Error alert */}
        {error && (
          <div style={styles.errorBox} role="alert">
            <span aria-hidden="true">⚠</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          {/* Email field */}
          <div style={styles.formGroup}>
            <label htmlFor="email" style={styles.label}>Email address</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onFocus={() => setEmailFocused(true)}
              onBlur={() => setEmailFocused(false)}
              placeholder="you@inpt.ac.ma"
              disabled={loading}
              required
              aria-invalid={emailInvalid}
              style={{
                ...styles.input,
                ...(emailFocused  ? styles.inputFocus : {}),
                ...(emailInvalid  ? styles.inputError : {}),
              }}
            />
            {emailInvalid && (
              <p style={{ ...styles.fieldHint, color: ERROR_RED }}>
                Please enter a valid email address.
              </p>
            )}
          </div>

          {/* Password field */}
          <div style={styles.formGroup}>
            <label htmlFor="password" style={styles.label}>Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onFocus={() => setPasswordFocused(true)}
              onBlur={() => setPasswordFocused(false)}
              placeholder="••••••••"
              disabled={loading}
              required
              aria-invalid={passwordShort}
              style={{
                ...styles.input,
                ...(passwordFocused ? styles.inputFocus : {}),
                ...(passwordShort   ? styles.inputError : {}),
              }}
            />
            {passwordShort && (
              <p style={{ ...styles.fieldHint, color: ERROR_RED }}>
                Password must be at least 8 characters.
              </p>
            )}
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={isDisabled}
            onMouseEnter={() => setBtnHovered(true)}
            onMouseLeave={() => setBtnHovered(false)}
            style={{
              ...styles.submitBtn,
              ...(isDisabled  ? styles.submitBtnDisabled : {}),
              ...(!isDisabled && btnHovered ? styles.submitBtnHover : {}),
            }}
          >
            {loading && <span style={styles.spinner} aria-hidden="true" />}
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>

      <p style={styles.footer}>
        © {new Date().getFullYear()} INPT — Cloud Infrastructure Platform
      </p>
    </div>
  );
}
