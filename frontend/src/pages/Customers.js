import React, { useState, useEffect, useCallback } from 'react';
import { MdAdd, MdRefresh, MdWarning, MdVerifiedUser, MdTrendingUp, MdTrendingDown, MdTrendingFlat, MdBlock, MdCheckCircle } from 'react-icons/md';
import { customersAPI, riskScoringAPI, blacklistAPI } from '../api/client';
import './Customers.css';

const LIST_META = {
  black:  { label: 'Blacklist',  icon: MdBlock,        color: '#EF4444', bg: 'rgba(239,68,68,0.12)'  },
  yellow: { label: 'Watchlist',  icon: MdWarning,      color: '#F59E0B', bg: 'rgba(245,158,11,0.12)' },
  white:  { label: 'Whitelist',  icon: MdCheckCircle,  color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
};

function AddToListModal({ customer, onClose }) {
  const [form, setForm] = useState({ list_type: 'black', severity: 'high', reason: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');
  const [success, setSuccess] = useState(false);

  const handleAdd = async () => {
    if (!form.reason.trim()) { setError('Reason is required.'); return; }
    setSaving(true); setError('');
    try {
      await blacklistAPI.create({
        entry_type: 'entity',
        value: customer.full_name,
        reason: form.reason,
        severity: form.severity,
        list_type: form.list_type,
      });
      setSuccess(true);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to add entry.');
    } finally { setSaving(false); }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 460 }}>
        <div className="modal-header">
          <div className="modal-title">Add to List — {customer.full_name}</div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {success ? (
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <MdCheckCircle size={40} style={{ color: '#10B981', marginBottom: 10 }} />
              <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {customer.full_name} added to {LIST_META[form.list_type].label}.
              </div>
            </div>
          ) : (
            <>
              <div style={{ marginBottom: 16, padding: '10px 14px', background: 'var(--bg-hover)', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, color: 'var(--text-muted)' }}>
                Entry type: <strong style={{ color: 'var(--text-primary)' }}>entity</strong> · Value: <strong style={{ color: 'var(--text-primary)' }}>{customer.full_name}</strong>
              </div>
              <div className="form-group">
                <label className="form-label">List</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {['black', 'yellow', 'white'].map(l => {
                    const m = LIST_META[l]; const Icon = m.icon;
                    return (
                      <button key={l} onClick={() => setForm({ ...form, list_type: l })} style={{
                        flex: 1, padding: '9px 0', borderRadius: 8,
                        border: `2px solid ${form.list_type === l ? m.color : 'var(--border)'}`,
                        background: form.list_type === l ? m.bg : 'var(--bg-card)',
                        color: form.list_type === l ? m.color : 'var(--text-muted)',
                        cursor: 'pointer', fontWeight: 700, fontSize: 12,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                      }}>
                        <Icon size={14} />{m.label}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Severity</label>
                <select className="form-select" value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })}>
                  {['low', 'medium', 'high', 'critical'].map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Reason *</label>
                <input className="form-input" placeholder="Why is this customer being listed?"
                  value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} />
              </div>
              {error && <div className="login-error" style={{ marginTop: 12 }}>⚠ {error}</div>}
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>{success ? 'Close' : 'Cancel'}</button>
          {!success && (
            <button className="btn btn-primary" onClick={handleAdd} disabled={saving}>
              {saving ? 'Adding...' : `Add to ${LIST_META[form.list_type].label}`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const RISK_LEVELS = ['low','medium','high','critical'];
const COUNTRIES = ['US','GB','DE','FR','RU','IR','KP','CN','SY','SD','BY','AE','SA','TR','MX','BR','NG','JP','IT','IL'];

function CreateCustomerModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    full_name: '', email: '', phone: '', nationality: 'US', country: 'US',
    risk_level: 'low', pep_status: false, occupation: '', annual_income: '',
    source_of_funds: 'employment', id_type: 'passport', id_number: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const { data } = await customersAPI.create({
        ...form,
        annual_income: form.annual_income ? parseFloat(form.annual_income) : null,
      });
      onCreated(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create customer');
    } finally { setLoading(false); }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 600 }}>
        <div className="modal-header">
          <span className="modal-title">New Customer</span>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={submit}>
          <div className="modal-body">
            {error && <div className="login-error" style={{ marginBottom: 16 }}>⚠ {error}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">Full Name *</label>
                <input className="form-input" required value={form.full_name}
                  onChange={e => setForm({...form, full_name: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Email</label>
                <input className="form-input" type="email" value={form.email}
                  onChange={e => setForm({...form, email: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Phone</label>
                <input className="form-input" value={form.phone}
                  onChange={e => setForm({...form, phone: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Nationality</label>
                <select className="form-select" value={form.nationality}
                  onChange={e => setForm({...form, nationality: e.target.value})}>
                  {COUNTRIES.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Country of Residence</label>
                <select className="form-select" value={form.country}
                  onChange={e => setForm({...form, country: e.target.value})}>
                  {COUNTRIES.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Risk Level</label>
                <select className="form-select" value={form.risk_level}
                  onChange={e => setForm({...form, risk_level: e.target.value})}>
                  {RISK_LEVELS.map(r => <option key={r}>{r}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Occupation</label>
                <input className="form-input" value={form.occupation}
                  onChange={e => setForm({...form, occupation: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Annual Income (USD)</label>
                <input className="form-input" type="number" value={form.annual_income}
                  onChange={e => setForm({...form, annual_income: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">ID Type</label>
                <select className="form-select" value={form.id_type}
                  onChange={e => setForm({...form, id_type: e.target.value})}>
                  {['passport','national_id','driving_license','other'].map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">ID Number</label>
                <input className="form-input" value={form.id_number}
                  onChange={e => setForm({...form, id_number: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Source of Funds</label>
                <select className="form-select" value={form.source_of_funds}
                  onChange={e => setForm({...form, source_of_funds: e.target.value})}>
                  {['employment','business','investment','inheritance','other','unknown'].map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">PEP Status</label>
                <select className="form-select" value={String(form.pep_status)}
                  onChange={e => setForm({...form, pep_status: e.target.value === 'true'})}>
                  <option value="false">Not a PEP</option>
                  <option value="true">Politically Exposed Person</option>
                </select>
              </div>
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Creating...' : 'Create Customer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PredictiveRiskModal({ customer, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    riskScoringAPI.predictRisk(customer.id)
      .then(r => setData(r.data))
      .catch(() => setError('Failed to load prediction.'))
      .finally(() => setLoading(false));
  }, [customer.id]);

  const trendIcon = (trend) => {
    if (trend === 'escalating' || trend === 'increasing') return <MdTrendingUp size={16} style={{ color: '#EF4444' }} />;
    if (trend === 'declining') return <MdTrendingDown size={16} style={{ color: '#10B981' }} />;
    return <MdTrendingFlat size={16} style={{ color: '#F59E0B' }} />;
  };

  const trendColor = { escalating: '#EF4444', increasing: '#F59E0B', stable: '#3B82F6', declining: '#10B981' };
  const bandColor = { low: '#10B981', medium: '#F59E0B', high: '#EF4444', critical: '#DC2626' };

  const pctBadge = (val) => {
    const color = val > 0 ? '#EF4444' : val < 0 ? '#10B981' : '#64748B';
    const sign = val > 0 ? '+' : '';
    return <span style={{ color, fontWeight: 600, fontSize: 12 }}>{sign}{val?.toFixed(1)}%</span>;
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 600 }}>
        <div className="modal-header">
          <div>
            <div className="modal-title">Predictive Risk — {customer.full_name}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>30-day behavioral trajectory forecast</div>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {loading && <div className="loading" style={{ padding: 40 }}>Analyzing behavioral patterns...</div>}
          {error && <div style={{ color: '#EF4444' }}>{error}</div>}
          {data && (
            <>
              {/* Prediction header */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
                <div style={{ background: 'var(--bg-hover)', borderRadius: 10, padding: '14px 16px', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Predicted Band</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: bandColor[data.predicted_risk_band] || '#64748B' }}>
                    {data.predicted_risk_band?.toUpperCase()}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-hover)', borderRadius: 10, padding: '14px 16px', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Velocity Score</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: data.velocity_score > 60 ? '#EF4444' : data.velocity_score > 30 ? '#F59E0B' : '#10B981' }}>
                    {data.velocity_score}/100
                  </div>
                </div>
                <div style={{ background: 'var(--bg-hover)', borderRadius: 10, padding: '14px 16px', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Trend</div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, fontSize: 14, fontWeight: 700, color: trendColor[data.trend] || '#64748B', textTransform: 'capitalize' }}>
                    {trendIcon(data.trend)} {data.trend}
                  </div>
                </div>
              </div>

              {/* AI Narrative */}
              <div style={{
                background: 'linear-gradient(135deg, rgba(152,193,217,0.08), rgba(92,154,183,0.05))',
                border: '1px solid rgba(152,193,217,0.2)',
                borderRadius: 10,
                padding: '14px 16px',
                marginBottom: 20,
                fontSize: 13,
                lineHeight: 1.65,
                color: 'var(--text-primary)',
              }}>
                <div style={{ fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
                  AI Prediction · Pattern match: {data.pattern_match_pct}% of similar profiles escalated
                </div>
                {data.narrative}
              </div>

              {/* Period comparison */}
              <div className="form-label" style={{ marginBottom: 10 }}>Activity Trend (month-over-month)</div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      {['Metric', 'Recent (0-30d)', 'Prior (30-60d)', 'Change'].map(h => (
                        <th key={h} style={{ padding: '8px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['Transactions', data.period_stats.recent_30d.txn_count, data.period_stats.prior_30_60d.txn_count, data.changes.transaction_count_change_pct],
                      ['Total Amount ($)', `$${(data.period_stats.recent_30d.txn_amount||0).toLocaleString()}`, `$${(data.period_stats.prior_30_60d.txn_amount||0).toLocaleString()}`, data.changes.transaction_amount_change_pct],
                      ['Flagged', data.period_stats.recent_30d.flagged_count, data.period_stats.prior_30_60d.flagged_count, data.changes.flagged_ratio_change_pct],
                      ['Alerts', data.period_stats.recent_30d.alert_count, data.period_stats.prior_30_60d.alert_count, data.changes.alert_count_change_pct],
                    ].map(([label, rec, prior, chg]) => (
                      <tr key={label} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '8px 10px', color: 'var(--text-muted)' }}>{label}</td>
                        <td style={{ padding: '8px 10px', fontWeight: 600 }}>{rec}</td>
                        <td style={{ padding: '8px 10px' }}>{prior}</td>
                        <td style={{ padding: '8px 10px' }}>{pctBadge(chg)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

export default function Customers() {
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [predictCustomer, setPredictCustomer] = useState(null);
  const [listTarget, setListTarget] = useState(null);
  const [filters, setFilters] = useState({ risk_level: '', pep_status: '', sanctions_flag: '', search: '', page: 1, page_size: 50 });

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    Object.entries(filters).forEach(([k,v]) => { if (v !== '') params[k] = v; });
    customersAPI.list(params).then(r => setData(r.data)).finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const riskBg = { low: '#10B981', medium: '#F59E0B', high: '#EF4444', critical: '#FCA5A5' };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Customers</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" onClick={load}><MdRefresh size={16} />Refresh</button>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}><MdAdd size={16} />Add Customer</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="filters-bar" style={{ margin: 0 }}>
          <div className="form-group filter-search" style={{ margin: 0 }}>
            <label className="form-label">Search</label>
            <input className="form-input" placeholder="Name, email, customer #..."
              value={filters.search} onChange={e => setFilters({...filters, search: e.target.value, page: 1})} />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Risk Level</label>
            <select className="form-select" value={filters.risk_level}
              onChange={e => setFilters({...filters, risk_level: e.target.value, page: 1})}>
              <option value="">All</option>
              {RISK_LEVELS.map(r => <option key={r}>{r}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">PEP</label>
            <select className="form-select" value={filters.pep_status}
              onChange={e => setFilters({...filters, pep_status: e.target.value, page: 1})}>
              <option value="">All</option>
              <option value="true">PEP Only</option>
              <option value="false">Non-PEP</option>
            </select>
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Sanctions</label>
            <select className="form-select" value={filters.sanctions_flag}
              onChange={e => setFilters({...filters, sanctions_flag: e.target.value, page: 1})}>
              <option value="">All</option>
              <option value="true">Flagged</option>
              <option value="false">Clear</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{data.total} customers</span>
        </div>
        {loading ? <div className="loading">Loading...</div> : (
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr><th>Customer #</th><th>Name</th><th>Country</th><th>Risk</th><th>PEP</th><th>Sanctions</th><th>Occupation</th><th>Source of Funds</th><th></th></tr>
              </thead>
              <tbody>
                {data.items?.map(c => (
                  <tr key={c.id}>
                    <td><span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--accent-blue)' }}>{c.customer_number}</span></td>
                    <td><strong>{c.full_name}</strong></td>
                    <td>{c.country || '—'}</td>
                    <td>
                      <span className={`badge badge-${c.risk_level}`}>{c.risk_level}</span>
                    </td>
                    <td>
                      {c.pep_status
                        ? <span style={{ color: '#F59E0B' }}><MdWarning size={16} title="PEP" /></span>
                        : <span style={{ color: '#64748B' }}>—</span>}
                    </td>
                    <td>
                      {c.sanctions_flag
                        ? <span style={{ color: '#EF4444', fontWeight: 600, fontSize: 11 }}>FLAGGED</span>
                        : <span style={{ color: '#10B981' }}><MdVerifiedUser size={16} /></span>}
                    </td>
                    <td>{c.occupation || '—'}</td>
                    <td>{c.source_of_funds || '—'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 10px', whiteSpace: 'nowrap' }}
                          onClick={e => { e.stopPropagation(); setPredictCustomer(c); }}>
                          <MdTrendingUp size={13} /> Predict Risk
                        </button>
                        <button className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 10px', whiteSpace: 'nowrap', color: '#EF4444', borderColor: 'rgba(239,68,68,0.3)' }}
                          onClick={e => { e.stopPropagation(); setListTarget(c); }}>
                          <MdBlock size={13} /> Add to List
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {data.items?.length === 0 && (
                  <tr><td colSpan={9}><div className="empty-state">No customers found.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" disabled={filters.page <= 1}
            onClick={() => setFilters({...filters, page: filters.page - 1})}>Previous</button>
          <span style={{ color: 'var(--text-muted)', fontSize: 13, alignSelf: 'center' }}>Page {filters.page}</span>
          <button className="btn btn-secondary" disabled={!data.items || data.items.length < filters.page_size}
            onClick={() => setFilters({...filters, page: filters.page + 1})}>Next</button>
        </div>
      </div>

      {showCreate && <CreateCustomerModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} />}
      {predictCustomer && <PredictiveRiskModal customer={predictCustomer} onClose={() => setPredictCustomer(null)} />}
      {listTarget && <AddToListModal customer={listTarget} onClose={() => setListTarget(null)} />}
    </div>
  );
}
