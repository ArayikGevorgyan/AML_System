import React, { useState, useEffect } from 'react';
import { MdAdd, MdToggleOn, MdToggleOff } from 'react-icons/md';
import { rulesAPI } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './Rules.css';

const CATEGORIES = ['large_transaction','structuring','frequency','velocity','high_risk_country','rapid_movement','round_amount','pep_transaction','micro_transaction'];

export default function Rules() {
  const { user } = useAuth();
  const canManage = user?.role === 'admin' || user?.role === 'supervisor';
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', category: 'large_transaction', threshold_amount: '', threshold_count: '', time_window_hours: '', severity: 'medium' });
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    rulesAPI.list().then(r => setRules(r.data)).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const toggle = async (id) => {
    await rulesAPI.toggle(id);
    load();
  };

  const createRule = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form };
      if (payload.threshold_amount) payload.threshold_amount = parseFloat(payload.threshold_amount);
      if (payload.threshold_count) payload.threshold_count = parseInt(payload.threshold_count);
      if (payload.time_window_hours) payload.time_window_hours = parseInt(payload.time_window_hours);
      await rulesAPI.create(payload);
      setShowCreate(false);
      setForm({ name: '', description: '', category: 'large_transaction', threshold_amount: '', threshold_count: '', time_window_hours: '', severity: 'medium' });
      load();
    } finally { setSaving(false); }
  };

  const catIcon = { large_transaction:'💰', structuring:'🧩', frequency:'🔁', velocity:'⚡', high_risk_country:'🌍', rapid_movement:'⏩', round_amount:'🔵', pep_transaction:'👤', micro_transaction:'🔬' };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>AML Rules Engine</h1>
        {canManage && <button className="btn btn-primary" onClick={() => setShowCreate(true)}><MdAdd size={16} />New Rule</button>}
      </div>

      <div className="rules-info-banner">
        <strong>How it works:</strong> Every transaction is evaluated against all active rules in real-time. When a rule matches, an alert is automatically generated with a computed risk score. Rules are configurable and can be enabled/disabled without code changes.
      </div>

      {loading ? <div className="loading">Loading rules...</div> : (
        <div className="rules-grid">
          {rules.map(rule => (
            <div key={rule.id} className={`rule-card ${!rule.is_active ? 'inactive' : ''}`}>
              <div className="rule-card-header">
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <span className="rule-cat-icon">{catIcon[rule.category] || '📋'}</span>
                  <div>
                    <div className="rule-name">{rule.name}</div>
                    <div className="rule-category">{rule.category.replace(/_/g,' ')}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <span className={`badge badge-${rule.severity}`}>{rule.severity}</span>
                  {canManage && (
                    <button className="toggle-btn" onClick={() => toggle(rule.id)} title={rule.is_active ? 'Disable' : 'Enable'}>
                      {rule.is_active ? <MdToggleOn size={28} style={{ color: '#10B981' }} /> : <MdToggleOff size={28} style={{ color: '#64748B' }} />}
                    </button>
                  )}
                </div>
              </div>

              {rule.description && <p className="rule-description">{rule.description}</p>}

              <div className="rule-params">
                {rule.threshold_amount != null && (
                  <div className="rule-param"><span>Threshold</span><span>${Number(rule.threshold_amount).toLocaleString()}</span></div>
                )}
                {rule.threshold_count != null && (
                  <div className="rule-param"><span>Count</span><span>{rule.threshold_count} txns</span></div>
                )}
                {rule.time_window_hours != null && (
                  <div className="rule-param"><span>Window</span><span>{rule.time_window_hours}h</span></div>
                )}
              </div>

              <div className="rule-footer">
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  Created {new Date(rule.created_at).toLocaleDateString()}
                </span>
                <span style={{ fontSize: 12, fontWeight: 600, color: rule.is_active ? '#10B981' : '#64748B' }}>
                  {rule.is_active ? '● ACTIVE' : '○ DISABLED'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && canManage && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setShowCreate(false)}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Create AML Rule</span>
              <button className="modal-close" onClick={() => setShowCreate(false)}>×</button>
            </div>
            <form onSubmit={createRule}>
              <div className="modal-body">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label className="form-label">Rule Name *</label>
                    <input className="form-input" required value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label className="form-label">Description</label>
                    <input className="form-input" value={form.description} onChange={e => setForm({...form, description: e.target.value})} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Category *</label>
                    <select className="form-select" value={form.category} onChange={e => setForm({...form, category: e.target.value})}>
                      {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g,' ')}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Severity</label>
                    <select className="form-select" value={form.severity} onChange={e => setForm({...form, severity: e.target.value})}>
                      {['low','medium','high','critical'].map(s => <option key={s}>{s}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Amount Threshold ($)</label>
                    <input className="form-input" type="number" value={form.threshold_amount} onChange={e => setForm({...form, threshold_amount: e.target.value})} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Count Threshold</label>
                    <input className="form-input" type="number" value={form.threshold_count} onChange={e => setForm({...form, threshold_count: e.target.value})} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Time Window (hours)</label>
                    <input className="form-input" type="number" value={form.time_window_hours} onChange={e => setForm({...form, time_window_hours: e.target.value})} />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Creating...' : 'Create Rule'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
