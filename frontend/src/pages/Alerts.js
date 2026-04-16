import React, { useState, useEffect, useCallback } from 'react';
import { MdRefresh, MdOpenInNew, MdDownload, MdDoneAll } from 'react-icons/md';
import { useNavigate } from 'react-router-dom';
import { alertsAPI, casesAPI } from '../api/client';

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
import './Alerts.css';

const SEVERITIES = ['low','medium','high','critical'];
const STATUSES = ['open','under_review','closed','false_positive','escalated'];

function AlertDetailModal({ alert, onClose, onUpdate, onNavigateCases }) {
  const [status, setStatus] = useState(alert.status);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);

  const saveStatus = async () => {
    setSaving(true);
    await alertsAPI.update(alert.id, { status });
    onUpdate();
    onClose();
  };

  const createCase = async () => {
    setCreating(true);
    try {
      await casesAPI.create({
        alert_id: alert.id,
        title: `Investigation: ${alert.reason.slice(0, 60)}`,
        priority: alert.severity,
      });
      onUpdate();
      onClose();
    } catch(e) {
      console.error(e);
    } finally { setCreating(false); }
  };

  const details = (() => {
    try { return JSON.parse(alert.details || '{}'); } catch { return {}; }
  })();

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 640 }}>
        <div className="modal-header">
          <div>
            <div className="modal-title">{alert.alert_number}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{alert.reason}</div>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="alert-detail-grid">
            <div className="alert-detail-item"><span>Severity</span><span className={`badge badge-${alert.severity}`}>{alert.severity}</span></div>
            <div className="alert-detail-item"><span>Status</span><span className={`badge badge-${alert.status}`}>{alert.status}</span></div>
            <div className="alert-detail-item"><span>Risk Score</span><span style={{ color: '#EF4444', fontWeight: 700 }}>{alert.risk_score?.toFixed(1)}</span></div>
            <div className="alert-detail-item"><span>Created</span><span>{new Date(alert.created_at).toLocaleString()}</span></div>
          </div>

          {Object.keys(details).length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div className="form-label" style={{ marginBottom: 8 }}>Rule Context</div>
              <div className="alert-details-box">
                {Object.entries(details).map(([k, v]) => (
                  <div key={k} className="alert-detail-row">
                    <span>{k.replace(/_/g, ' ')}</span>
                    <span>{typeof v === 'number' ? (k.includes('amount') || k.includes('volume') ? `$${Number(v).toLocaleString()}` : v) : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="form-group" style={{ marginTop: 16, marginBottom: 0 }}>
            <label className="form-label">Update Status</label>
            <select className="form-select" value={status} onChange={e => setStatus(e.target.value)}>
              {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
            </select>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
          <button className="btn btn-secondary" onClick={createCase} disabled={creating}>
            {creating ? 'Creating...' : 'Create Case'}
          </button>
          <button className="btn btn-primary" onClick={saveStatus} disabled={saving}>
            {saving ? 'Saving...' : 'Update Status'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Alerts() {
  const navigate = useNavigate();
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState({ severity: '', status: 'open', page: 1, page_size: 50 });
  const [markingAll, setMarkingAll] = useState(false);

  const handleMarkAllRead = async () => {
    setMarkingAll(true);
    try {
      await alertsAPI.markAllRead();
      load();
    } catch(e) { console.error(e); }
    finally { setMarkingAll(false); }
  };

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    Object.entries(filters).forEach(([k,v]) => { if (v !== '') params[k] = v; });
    alertsAPI.list(params).then(r => setData(r.data)).finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Alerts</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" onClick={handleMarkAllRead} disabled={markingAll}>
            <MdDoneAll size={16} /> {markingAll ? 'Marking...' : 'Mark All as Read'}
          </button>
          <button className="btn btn-secondary" onClick={() => downloadCSV('/export/alerts.csv', 'alerts.csv')}>
            <MdDownload size={16} /> Export CSV
          </button>
          <button className="btn btn-secondary" onClick={load}><MdRefresh size={16} />Refresh</button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="filters-bar" style={{ margin: 0 }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Severity</label>
            <select className="form-select" value={filters.severity}
              onChange={e => setFilters({...filters, severity: e.target.value, page: 1})}>
              <option value="">All</option>
              {SEVERITIES.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Status</label>
            <select className="form-select" value={filters.status}
              onChange={e => setFilters({...filters, status: e.target.value, page: 1})}>
              <option value="">All</option>
              {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g,' ')}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{data.total} alerts</span>
        </div>
        {loading ? <div className="loading">Loading...</div> : (
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr><th>Alert #</th><th>Severity</th><th>Status</th><th>Risk Score</th><th>Reason</th><th>Created</th><th></th></tr>
              </thead>
              <tbody>
                {data.items?.map(a => (
                  <tr key={a.id} onClick={() => setSelected(a)}>
                    <td><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{a.alert_number}</span></td>
                    <td><span className={`badge badge-${a.severity}`}>{a.severity}</span></td>
                    <td><span className={`badge badge-${a.status}`}>{a.status.replace(/_/g,' ')}</span></td>
                    <td><span style={{ color: a.risk_score >= 70 ? '#EF4444' : '#F59E0B', fontWeight: 600 }}>{a.risk_score?.toFixed(1)}</span></td>
                    <td style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.reason}</td>
                    <td style={{ fontSize: 12 }}>{new Date(a.created_at).toLocaleDateString()}</td>
                    <td><MdOpenInNew size={14} style={{ color: 'var(--text-muted)' }} /></td>
                  </tr>
                ))}
                {data.items?.length === 0 && (
                  <tr><td colSpan={7} className="empty-state">No alerts match your filters.</td></tr>
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

      {selected && (
        <AlertDetailModal alert={selected} onClose={() => setSelected(null)} onUpdate={load} onNavigateCases={() => navigate('/cases')} />
      )}
    </div>
  );
}
