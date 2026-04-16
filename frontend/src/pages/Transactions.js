import React, { useState, useEffect, useCallback } from 'react';
import { MdAdd, MdRefresh, MdFlag, MdFilterList, MdDownload } from 'react-icons/md';
import { transactionsAPI, customersAPI } from '../api/client';

async function downloadCSV(path, filename) {
  const token = localStorage.getItem('aml_token');
  const res = await fetch(`http://localhost:8000/api/v1${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
import './Transactions.css';

const TXN_TYPES = ['transfer','deposit','withdrawal','wire','payment','cash'];
const COUNTRIES = ['US','GB','DE','FR','RU','IR','KP','CN','SY','SD','BY','AE','SA','TR','MX'];

function CreateTransactionModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    amount: '', currency: 'USD', transaction_type: 'transfer',
    from_customer_id: '', to_customer_id: '',
    originating_country: 'US', destination_country: 'US',
    description: '', channel: 'online',
  });
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    customersAPI.list({ page_size: 100 }).then(r => setCustomers(r.data.items || []));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const payload = {
        ...form,
        amount: parseFloat(form.amount),
        from_customer_id: form.from_customer_id ? parseInt(form.from_customer_id) : null,
        to_customer_id: form.to_customer_id ? parseInt(form.to_customer_id) : null,
      };
      const { data } = await transactionsAPI.create(payload);
      onCreated(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create transaction');
    } finally { setLoading(false); }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <span className="modal-title">New Transaction</span>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={submit}>
          <div className="modal-body">
            {error && <div className="login-error" style={{ marginBottom: 16 }}>⚠ {error}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="form-group">
                <label className="form-label">Amount *</label>
                <input className="form-input" type="number" step="0.01" required
                  value={form.amount} onChange={e => setForm({...form, amount: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Currency</label>
                <select className="form-select" value={form.currency}
                  onChange={e => setForm({...form, currency: e.target.value})}>
                  {['USD','EUR','GBP','JPY','AED'].map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Type *</label>
                <select className="form-select" required value={form.transaction_type}
                  onChange={e => setForm({...form, transaction_type: e.target.value})}>
                  {TXN_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Channel</label>
                <select className="form-select" value={form.channel}
                  onChange={e => setForm({...form, channel: e.target.value})}>
                  {['online','branch','mobile','atm'].map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">From Customer</label>
                <select className="form-select" value={form.from_customer_id}
                  onChange={e => setForm({...form, from_customer_id: e.target.value})}>
                  <option value="">— Select —</option>
                  {customers.map(c => <option key={c.id} value={c.id}>{c.full_name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">To Customer</label>
                <select className="form-select" value={form.to_customer_id}
                  onChange={e => setForm({...form, to_customer_id: e.target.value})}>
                  <option value="">— Select —</option>
                  {customers.map(c => <option key={c.id} value={c.id}>{c.full_name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Origin Country</label>
                <select className="form-select" value={form.originating_country}
                  onChange={e => setForm({...form, originating_country: e.target.value})}>
                  {COUNTRIES.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Destination Country</label>
                <select className="form-select" value={form.destination_country}
                  onChange={e => setForm({...form, destination_country: e.target.value})}>
                  {COUNTRIES.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <input className="form-input" value={form.description}
                onChange={e => setForm({...form, description: e.target.value})} />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Processing...' : 'Submit Transaction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Transactions() {
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [filters, setFilters] = useState({
    transaction_type: '', flagged: '', min_amount: '', max_amount: '',
    originating_country: '', page: 1, page_size: 50,
  });

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    Object.entries(filters).forEach(([k, v]) => { if (v !== '') params[k] = v; });
    transactionsAPI.list(params)
      .then(r => setData(r.data))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const riskColor = (score) => {
    if (score >= 80) return '#EF4444';
    if (score >= 60) return '#F59E0B';
    if (score >= 40) return '#3B82F6';
    return '#10B981';
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Transactions</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" onClick={() => downloadCSV('/export/transactions.csv', 'transactions.csv')}>
            <MdDownload size={16} /> Export CSV
          </button>
          <button className="btn btn-secondary" onClick={load}><MdRefresh size={16} />Refresh</button>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}><MdAdd size={16} />New Transaction</button>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="filters-bar" style={{ margin: 0 }}>
          <div className="form-group filter-search" style={{ margin: 0 }}>
            <label className="form-label">Type</label>
            <select className="form-select" value={filters.transaction_type}
              onChange={e => setFilters({...filters, transaction_type: e.target.value, page: 1})}>
              <option value="">All Types</option>
              {TXN_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Flagged</label>
            <select className="form-select" value={filters.flagged}
              onChange={e => setFilters({...filters, flagged: e.target.value, page: 1})}>
              <option value="">All</option>
              <option value="true">Flagged Only</option>
              <option value="false">Clean Only</option>
            </select>
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Min Amount</label>
            <input className="form-input" type="number" placeholder="0"
              value={filters.min_amount} onChange={e => setFilters({...filters, min_amount: e.target.value, page: 1})} />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Max Amount</label>
            <input className="form-input" type="number" placeholder="∞"
              value={filters.max_amount} onChange={e => setFilters({...filters, max_amount: e.target.value, page: 1})} />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Origin Country</label>
            <select className="form-select" value={filters.originating_country}
              onChange={e => setFilters({...filters, originating_country: e.target.value, page: 1})}>
              <option value="">All</option>
              {COUNTRIES.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{data.total} transactions</span>
        </div>
        <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
          {loading ? <div className="loading">Loading...</div> : (
            <table>
              <thead>
                <tr>
                  <th>Reference</th><th>Type</th><th>Amount</th><th>Currency</th>
                  <th>From Country</th><th>To Country</th><th>Risk Score</th>
                  <th>Flagged</th><th>Date</th>
                </tr>
              </thead>
              <tbody>
                {data.items?.map(t => (
                  <tr key={t.id}>
                    <td><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{t.reference}</span></td>
                    <td><span className="badge badge-open">{t.transaction_type}</span></td>
                    <td><strong>${t.amount.toLocaleString()}</strong></td>
                    <td>{t.currency}</td>
                    <td>{t.originating_country || '—'}</td>
                    <td>{t.destination_country || '—'}</td>
                    <td>
                      <span style={{ color: riskColor(t.risk_score), fontWeight: 600 }}>
                        {t.risk_score.toFixed(1)}
                      </span>
                    </td>
                    <td>
                      {t.flagged
                        ? <span style={{ color: '#EF4444' }}><MdFlag size={16} /></span>
                        : <span style={{ color: '#64748B' }}>—</span>}
                    </td>
                    <td style={{ fontSize: 12 }}>{new Date(t.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" disabled={filters.page <= 1}
            onClick={() => setFilters({...filters, page: filters.page - 1})}>Previous</button>
          <span style={{ color: 'var(--text-muted)', fontSize: 13, alignSelf: 'center' }}>Page {filters.page}</span>
          <button className="btn btn-secondary" disabled={data.items?.length < filters.page_size}
            onClick={() => setFilters({...filters, page: filters.page + 1})}>Next</button>
        </div>
      </div>

      {showCreate && (
        <CreateTransactionModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}
    </div>
  );
}
