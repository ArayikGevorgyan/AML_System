import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { MdSecurity, MdLock, MdPerson, MdArrowBack } from 'react-icons/md';
import { useAuth } from '../context/AuthContext';
import './Login.css';

export default function Login() {
  const [form, setForm] = useState({ username: 'admin', password: 'Admin@123' });
  const [error, setError] = useState('');
  const { login, loading } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const result = await login(form.username, form.password);
    if (result.success) navigate('/dashboard');
    else setError(result.error);
  };

  return (
    <div className="login-page">
      <div className="login-bg">
        <div className="login-bg-circle c1" />
        <div className="login-bg-circle c2" />
        <div className="login-bg-circle c3" />
      </div>

      <button onClick={() => navigate('/home')} className="login-back-btn">
        <MdArrowBack size={16} /> Back to Home
      </button>

      <div className="login-card">
        <div className="login-logo">
          <div className="login-logo-icon"><MdSecurity size={32} /></div>
          <div>
            <h1 className="login-brand">AML Monitor</h1>
            <p className="login-subtitle">Transaction Monitoring System</p>
          </div>
        </div>

        <div className="login-divider" />

        <h2 className="login-title">Secure Login</h2>
        <p className="login-desc">Sign in with your compliance credentials</p>

        {error && <div className="login-error">⚠ {error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <MdPerson className="login-field-icon" size={16} />
            <input
              className="login-input"
              type="text"
              placeholder="Username"
              value={form.username}
              onChange={e => setForm({ ...form, username: e.target.value })}
              required
            />
          </div>
          <div className="login-field">
            <MdLock className="login-field-icon" size={16} />
            <input
              className="login-input"
              type="password"
              placeholder="Password"
              value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
              required
            />
          </div>
          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>


        <div className="login-credentials">
          <p className="login-cred-title">Demo Accounts</p>
          <div className="login-cred-grid">
            <div onClick={() => setForm({ username: 'admin', password: 'Admin@123' })}>
              <span>admin</span><span>Admin@123</span><span className="cred-role">Admin</span>
            </div>
            <div onClick={() => setForm({ username: 'ArayikAnalyst', password: 'Analyst@123' })}>
              <span>ArayikAnalyst</span><span>Analyst@123</span><span className="cred-role">Analyst</span>
            </div>
            <div onClick={() => setForm({ username: 'ArayikSupervisor', password: 'Super@123' })}>
              <span>ArayikSupervisor</span><span>Super@123</span><span className="cred-role">Supervisor</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
