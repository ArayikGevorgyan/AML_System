import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { MdSecurity, MdLock, MdPerson, MdEmail, MdBadge, MdArrowBack, MdMarkEmailRead } from 'react-icons/md';
import { authAPI } from '../api/client';
import './Login.css';
import './Register.css';

const REQUIREMENTS = [
  { key: 'length',    label: 'At least 8 characters',      test: p => p.length >= 8 },
  { key: 'upper',     label: 'One uppercase letter (A–Z)',  test: p => /[A-Z]/.test(p) },
  { key: 'number',    label: 'One number (0–9)',            test: p => /[0-9]/.test(p) },
  { key: 'special',   label: 'One special character (!@#$%^&*)', test: p => /[^A-Za-z0-9]/.test(p) },
];

export function passwordIsStrong(pwd) {
  return REQUIREMENTS.every(r => r.test(pwd));
}

function PasswordStrength({ password }) {
  if (!password) return null;
  const met = REQUIREMENTS.filter(r => r.test(password)).length;
  const barColor = met <= 1 ? '#EF4444' : met <= 2 ? '#F59E0B' : met === 3 ? '#3B82F6' : '#34D399';
  const barWidth = `${(met / REQUIREMENTS.length) * 100}%`;
  const label = met <= 1 ? 'Weak' : met <= 2 ? 'Fair' : met === 3 ? 'Good' : 'Strong';

  return (
    <div style={{ marginTop: 8, paddingLeft: 2 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Password strength</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: barColor }}>{label}</span>
      </div>
      <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', marginBottom: 8 }}>
        <div style={{ height: '100%', width: barWidth, background: barColor, borderRadius: 2, transition: 'width 0.3s, background 0.3s' }} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {REQUIREMENTS.map(r => {
          const ok = r.test(password);
          return (
            <div key={r.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: ok ? '#34D399' : '#EF4444', fontWeight: 700, lineHeight: 1 }}>
                {ok ? '✓' : '✗'}
              </span>
              <span style={{ fontSize: 11, color: ok ? '#34D399' : 'var(--text-muted)' }}>{r.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const ROLES = [
  { value: 'analyst',    label: 'Analyst',    desc: 'Review alerts and manage cases' },
  { value: 'supervisor', label: 'Supervisor',  desc: 'Oversee analysts and approve SARs' },
  { value: 'admin',      label: 'Admin',       desc: 'Full system access and configuration' },
];

export default function Register() {
  const navigate = useNavigate();

  // step 1: email entry, step 2: code + details
  const [step, setStep]       = useState(1);
  const [email, setEmail]     = useState('');
  const [code, setCode]       = useState('');
  const [form, setForm]       = useState({ username: '', full_name: '', role: 'analyst', password: '', confirm_password: '' });
  const [error, setError]     = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resendMsg, setResendMsg] = useState('');

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  // ── Step 1: send verification code ──────────────────────────────────────────
  const handleSendCode = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authAPI.sendVerification(email.trim().toLowerCase());
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not send verification code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResendMsg('');
    setError('');
    try {
      await authAPI.sendVerification(email.trim().toLowerCase());
      setResendMsg('A new code has been sent to your inbox.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resend code.');
    }
  };

  // ── Step 2: complete registration ────────────────────────────────────────────
  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');

    if (form.password !== form.confirm_password) { setError('Passwords do not match.'); return; }
    if (!passwordIsStrong(form.password)) { setError('Password does not meet the requirements below.'); return; }
    if (code.length !== 6) { setError('Please enter the 6-digit verification code.'); return; }

    setLoading(true);
    try {
      await authAPI.register({
        username:          form.username,
        email:             email.trim().toLowerCase(),
        full_name:         form.full_name,
        password:          form.password,
        role:              form.role,
        verification_code: code,
      });
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // ── Success screen ───────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="login-page">
        <div className="login-bg">
          <div className="login-bg-circle c1" /><div className="login-bg-circle c2" /><div className="login-bg-circle c3" />
        </div>
        <div className="login-card reg-success-card">
          <div className="reg-success-icon">✓</div>
          <h2 className="reg-success-title">Account Created!</h2>
          <p className="reg-success-desc">
            Your <strong>{form.role}</strong> account for <strong>{form.username}</strong> has been created successfully.
          </p>
          <button className="login-btn" style={{ marginTop: 24 }} onClick={() => navigate('/login')}>
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-bg">
        <div className="login-bg-circle c1" /><div className="login-bg-circle c2" /><div className="login-bg-circle c3" />
      </div>

      <button onClick={() => navigate('/home')} className="login-back-btn">
        <MdArrowBack size={16} /> Back to Home
      </button>

      <div className="login-card reg-card">
        {/* Header */}
        <div className="login-logo">
          <div className="login-logo-icon"><MdSecurity size={32} /></div>
          <div>
            <h1 className="login-brand">AML Monitor</h1>
            <p className="login-subtitle">Transaction Monitoring System</p>
          </div>
        </div>

        <div className="login-divider" />

        {/* Step indicator */}
        <div className="reg-steps">
          <div className={`reg-step ${step >= 1 ? 'active' : ''} ${step > 1 ? 'done' : ''}`}>
            <div className="reg-step-circle">{step > 1 ? '✓' : '1'}</div>
            <span>Verify Email</span>
          </div>
          <div className="reg-step-line" />
          <div className={`reg-step ${step >= 2 ? 'active' : ''}`}>
            <div className="reg-step-circle">2</div>
            <span>Create Account</span>
          </div>
        </div>

        {error && <div className="login-error">⚠ {error}</div>}
        {resendMsg && <div className="reg-resend-msg">✓ {resendMsg}</div>}

        {/* ── STEP 1 ── */}
        {step === 1 && (
          <>
            <h2 className="login-title">Verify Your Email</h2>
            <p className="login-desc">Enter your email address to receive a verification code</p>

            <form onSubmit={handleSendCode} className="login-form">
              <div className="login-field">
                <MdEmail className="login-field-icon" size={16} />
                <input
                  className="login-input"
                  type="email"
                  placeholder="Email Address"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <button className="login-btn" type="submit" disabled={loading}>
                {loading ? 'Sending Code...' : 'Send Verification Code'}
              </button>
            </form>
          </>
        )}

        {/* ── STEP 2 ── */}
        {step === 2 && (
          <>
            <h2 className="login-title">Complete Registration</h2>
            <div className="reg-email-sent-banner">
              <MdMarkEmailRead size={20} />
              <span>Code sent to <strong>{email}</strong></span>
            </div>

            <form onSubmit={handleRegister} className="login-form">

              {/* Verification code */}
              <div className="reg-code-group">
                <label className="reg-code-label">Verification Code</label>
                <input
                  className="reg-code-input"
                  type="text"
                  placeholder="000000"
                  maxLength={6}
                  value={code}
                  onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
                  required
                  autoFocus
                />
                <button type="button" className="reg-resend-btn" onClick={handleResend}>
                  Resend code
                </button>
              </div>

              {/* Full Name */}
              <div className="login-field">
                <MdBadge className="login-field-icon" size={16} />
                <input className="login-input" type="text" placeholder="Full Name"
                  value={form.full_name} onChange={set('full_name')} required />
              </div>

              {/* Username */}
              <div className="login-field">
                <MdPerson className="login-field-icon" size={16} />
                <input className="login-input" type="text" placeholder="Username"
                  value={form.username} onChange={set('username')} required />
              </div>

              {/* Role selector */}
              <div className="reg-role-group">
                <p className="reg-role-label">Select Role</p>
                <div className="reg-role-options">
                  {ROLES.map(r => (
                    <label key={r.value} className={`reg-role-card ${form.role === r.value ? 'selected' : ''}`}>
                      <input type="radio" name="role" value={r.value}
                        checked={form.role === r.value} onChange={set('role')} />
                      <span className="reg-role-name">{r.label}</span>
                      <span className="reg-role-desc">{r.desc}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Password */}
              <div>
                <div className="login-field">
                  <MdLock className="login-field-icon" size={16} />
                  <input className="login-input" type="password" placeholder="Password"
                    value={form.password} onChange={set('password')} required />
                </div>
                <PasswordStrength password={form.password} />
              </div>

              {/* Confirm Password */}
              <div className="login-field">
                <MdLock className="login-field-icon" size={16} />
                <input className="login-input" type="password" placeholder="Confirm Password"
                  value={form.confirm_password} onChange={set('confirm_password')} required />
              </div>

              <button className="login-btn" type="submit" disabled={loading}>
                {loading ? 'Creating Account...' : 'Create Account'}
              </button>
            </form>

            <button className="reg-back-email-btn" onClick={() => { setStep(1); setError(''); setCode(''); }}>
              <MdArrowBack size={14} style={{ marginRight: 4 }} /> Use a different email
            </button>
          </>
        )}

        <div style={{ textAlign: 'center', marginTop: 12 }}>
          <Link to="/login" className="reg-back-link">
            <MdArrowBack size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            Back to Login
          </Link>
        </div>
      </div>
    </div>
  );
}
