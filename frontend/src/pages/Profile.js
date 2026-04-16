import React, { useState } from 'react';

function getStrength(pwd) {
  if (!pwd) return null;
  let score = 0;
  if (pwd.length >= 8) score++;
  if (/[A-Z]/.test(pwd)) score++;
  if (/[0-9]/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;
  if (pwd.length >= 12) score++;
  if (score <= 1) return { label: 'Weak',   color: '#EF4444', width: '25%' };
  if (score <= 3) return { label: 'Medium', color: '#F59E0B', width: '60%' };
  return               { label: 'Strong', color: '#34D399', width: '100%' };
}

function PasswordStrength({ password }) {
  const s = getStrength(password);
  if (!s) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: s.width, background: s.color, borderRadius: 2, transition: 'width 0.3s, background 0.3s' }} />
      </div>
      <span style={{ fontSize: 11, marginTop: 3, display: 'block', color: s.color, fontWeight: 600 }}>{s.label} password</span>
    </div>
  );
}
import { useAuth } from '../context/AuthContext';
import { authAPI } from '../api/client';
import { MdPerson, MdLock, MdEmail, MdSave, MdPersonAdd } from 'react-icons/md';
import './Profile.css';

const ROLES = ['analyst', 'supervisor', 'admin'];

function CreateUserForm() {
  const [form, setForm] = useState({ username: '', email: '', full_name: '', role: 'analyst', password: '' });
  const [loading, setLoading] = useState(false);
  const [msg, setMsg]     = useState('');
  const [error, setError] = useState('');
  const set = f => e => setForm({ ...form, [f]: e.target.value });

  const handleCreate = async (e) => {
    e.preventDefault();
    setLoading(true); setMsg(''); setError('');
    try {
      await authAPI.createUser(form);
      setMsg(`Account for "${form.username}" created successfully.`);
      setForm({ username: '', email: '', full_name: '', role: 'analyst', password: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user.');
    } finally { setLoading(false); }
  };

  return (
    <form onSubmit={handleCreate} className="profile-form">
      <div style={{ marginBottom: 18, padding: '10px 14px', background: 'rgba(240,165,0,0.06)', border: '1px solid rgba(240,165,0,0.15)', borderLeft: '3px solid #F0A500', borderRadius: 7, fontSize: 13, color: 'var(--text-muted)' }}>
        Create a new account for a team member. They will receive their credentials and can change their password after first login.
      </div>
      {msg   && <div className="profile-msg success">{msg}</div>}
      {error && <div className="profile-msg error">{error}</div>}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div className="form-group">
          <label className="form-label">Full Name</label>
          <input className="form-input" required value={form.full_name} onChange={set('full_name')} placeholder="John Smith" />
        </div>
        <div className="form-group">
          <label className="form-label">Username</label>
          <input className="form-input" required value={form.username} onChange={set('username')} placeholder="jsmith" />
        </div>
        <div className="form-group">
          <label className="form-label">Email</label>
          <input className="form-input" type="email" required value={form.email} onChange={set('email')} placeholder="john@company.com" />
        </div>
        <div className="form-group">
          <label className="form-label">Role</label>
          <select className="form-select" value={form.role} onChange={set('role')}>
            {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
          </select>
        </div>
        <div className="form-group" style={{ gridColumn: '1 / -1' }}>
          <label className="form-label">Temporary Password</label>
          <input className="form-input" type="password" required value={form.password} onChange={set('password')} placeholder="Min 8 chars, uppercase, digit, special char" />
        </div>
      </div>
      <button type="submit" className="btn btn-primary" disabled={loading}>
        <MdPersonAdd size={16} /> {loading ? 'Creating...' : 'Create Account'}
      </button>
    </form>
  );
}

export default function Profile() {
  const { user, login } = useAuth();
  const [tab, setTab] = useState('info');
  const [name, setName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const showMsg = (m) => { setMsg(m); setError(''); setTimeout(() => setMsg(''), 4000); };
  const showErr = (e) => { setError(e); setMsg(''); setTimeout(() => setError(''), 5000); };

  const handleUpdateInfo = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await authAPI.updateProfile({ full_name: name, email });
      showMsg('Profile updated successfully!');
    } catch (err) {
      showErr(err.response?.data?.detail || 'Update failed');
    } finally { setLoading(false); }
  };

  const handleSendCode = async () => {
    setLoading(true);
    try {
      await authAPI.sendPasswordReset();
      setCodeSent(true);
      showMsg('Verification code sent to your email!');
    } catch (err) {
      showErr(err.response?.data?.detail || 'Failed to send code');
    } finally { setLoading(false); }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) { showErr('Passwords do not match'); return; }
    if (newPassword.length < 6) { showErr('Password must be at least 6 characters'); return; }
    setLoading(true);
    try {
      await authAPI.changePassword({ verification_code: code, new_password: newPassword });
      showMsg('Password changed successfully!');
      setCode(''); setNewPassword(''); setConfirmPassword(''); setCodeSent(false);
    } catch (err) {
      showErr(err.response?.data?.detail || 'Failed to change password');
    } finally { setLoading(false); }
  };

  return (
    <div className="profile-page">
      <h2 className="page-title">My Profile</h2>
      <div className="profile-container">
        <div className="profile-avatar-card card">
          <div className="profile-avatar-big">{user?.full_name?.[0] || 'U'}</div>
          <div className="profile-avatar-name">{user?.full_name}</div>
          <div className="profile-avatar-role">{user?.role}</div>
          <div className="profile-avatar-username">@{user?.username}</div>
        </div>
        <div className="profile-main card">
          <div className="profile-tabs">
            <button className={`profile-tab ${tab === 'info' ? 'active' : ''}`} onClick={() => setTab('info')}>
              <MdPerson size={16} /> Personal Info
            </button>
            <button className={`profile-tab ${tab === 'password' ? 'active' : ''}`} onClick={() => setTab('password')}>
              <MdLock size={16} /> Change Password
            </button>
            {user?.role === 'admin' && (
              <button className={`profile-tab ${tab === 'users' ? 'active' : ''}`} onClick={() => setTab('users')}>
                <MdPersonAdd size={16} /> Add User
              </button>
            )}
          </div>
          {tab !== 'users' && msg   && <div className="profile-msg success">{msg}</div>}
          {tab !== 'users' && error && <div className="profile-msg error">{error}</div>}
          {tab === 'info' && (
            <form onSubmit={handleUpdateInfo} className="profile-form">
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input className="form-input" value={name} onChange={e => setName(e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Email</label>
                <input className="form-input" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Username</label>
                <input className="form-input" value={user?.username || ''} disabled style={{opacity:0.6}} />
              </div>
              <div className="form-group">
                <label className="form-label">Role</label>
                <input className="form-input" value={user?.role || ''} disabled style={{opacity:0.6}} />
              </div>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                <MdSave size={16} /> {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </form>
          )}
          {tab === 'password' && (
            <div className="profile-form">
              {!codeSent ? (
                <div>
                  <p style={{color:'var(--text-subtle)', marginBottom:16, fontSize:13}}>
                    A verification code will be sent to <strong>{user?.email}</strong> before you can change your password.
                  </p>
                  <button className="btn btn-primary" onClick={handleSendCode} disabled={loading}>
                    <MdEmail size={16} /> {loading ? 'Sending...' : 'Send Verification Code'}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleChangePassword}>
                  <div className="form-group">
                    <label className="form-label">Verification Code</label>
                    <input className="form-input" value={code} onChange={e => setCode(e.target.value)} placeholder="Enter 6-digit code" required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">New Password</label>
                    <input className="form-input" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} required />
                    <PasswordStrength password={newPassword} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Confirm New Password</label>
                    <input className="form-input" type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required />
                  </div>
                  <div style={{display:'flex', gap:12}}>
                    <button type="submit" className="btn btn-primary" disabled={loading}>
                      <MdLock size={16} /> {loading ? 'Updating...' : 'Change Password'}
                    </button>
                    <button type="button" className="btn btn-secondary" onClick={() => setCodeSent(false)}>Resend Code</button>
                  </div>
                </form>
              )}
            </div>
          )}
          {tab === 'users' && user?.role === 'admin' && <CreateUserForm />}
        </div>
      </div>
    </div>
  );
}
