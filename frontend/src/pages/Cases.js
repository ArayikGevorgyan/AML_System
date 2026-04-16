import React, { useState, useEffect, useCallback } from 'react';
import { MdAdd, MdRefresh, MdNote, MdDownload, MdAutoAwesome } from 'react-icons/md';
import { casesAPI } from '../api/client';

function getCurrentUser() {
  try { return JSON.parse(localStorage.getItem('aml_user') || '{}'); } catch { return {}; }
}

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
import './Cases.css';

const STATUSES = ['open','investigating','pending_review','escalated','closed','filed_sar'];
const PRIORITIES = ['low','medium','high','critical'];

function CaseDetailModal({ caseItem, onClose, onUpdate }) {
  const [notes, setNotes] = useState([]);
  const [newNote, setNewNote] = useState('');
  const [status, setStatus] = useState(caseItem.status);
  const [saving, setSaving] = useState(false);
  const currentUser = getCurrentUser();
  const isAnalyst = currentUser.role === 'analyst';
  const allowedStatuses = isAnalyst
    ? STATUSES.filter(s => s !== 'escalated' && s !== 'filed_sar')
    : STATUSES;
  const [aiSummary, setAiSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  useEffect(() => {
    casesAPI.getNotes(caseItem.id).then(r => setNotes(r.data));
  }, [caseItem.id]);

  const generateSummary = async () => {
    setLoadingSummary(true);
    setAiSummary(null);
    try {
      const r = await casesAPI.getAiSummary(caseItem.id);
      setAiSummary(r.data);
    } catch (e) {
      setAiSummary({ error: 'Failed to generate summary. Please try again.' });
    } finally {
      setLoadingSummary(false);
    }
  };

  const save = async () => {
    setSaving(true);
    await casesAPI.update(caseItem.id, { status });
    onUpdate(); onClose();
  };

  const addNote = async () => {
    if (!newNote.trim()) return;
    await casesAPI.addNote(caseItem.id, { note: newNote, note_type: 'comment' });
    setNewNote('');
    const r = await casesAPI.getNotes(caseItem.id);
    setNotes(r.data);
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 680 }}>
        <div className="modal-header">
          <div>
            <div className="modal-title">{caseItem.case_number}</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>{caseItem.title}</div>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="case-meta-grid">
            <div className="case-meta-item"><span>Priority</span><span className={`badge badge-${caseItem.priority}`}>{caseItem.priority}</span></div>
            <div className="case-meta-item"><span>Current Status</span><span className={`badge badge-${caseItem.status}`}>{caseItem.status.replace(/_/g,' ')}</span></div>
            <div className="case-meta-item"><span>SAR Filed</span><span style={{ color: caseItem.sar_filed ? '#10B981' : '#64748B' }}>{caseItem.sar_filed ? 'Yes' : 'No'}</span></div>
            <div className="case-meta-item"><span>Created</span><span>{new Date(caseItem.created_at).toLocaleDateString()}</span></div>
          </div>

          {caseItem.description && (
            <div style={{ marginTop: 16, padding: '12px 16px', background: 'var(--bg-hover)', borderRadius: 8, fontSize: 13, color: 'var(--text-subtle)', borderLeft: '3px solid var(--accent-blue)' }}>
              {caseItem.description}
            </div>
          )}

          {/* AI Summary */}
          <div style={{ marginTop: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div className="form-label" style={{ margin: 0 }}>AI Case Summary</div>
              <button className="btn btn-secondary" style={{ fontSize: 12, padding: '5px 12px' }}
                onClick={generateSummary} disabled={loadingSummary}>
                <MdAutoAwesome size={14} />
                {loadingSummary ? 'Generating...' : 'Generate'}
              </button>
            </div>
            {aiSummary && !aiSummary.error && (
              <div style={{
                background: 'linear-gradient(135deg, rgba(152,193,217,0.08), rgba(92,154,183,0.05))',
                border: '1px solid rgba(152,193,217,0.25)',
                borderRadius: 10,
                padding: '14px 16px',
                fontSize: 13,
                lineHeight: 1.65,
                color: 'var(--text-primary)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, color: 'var(--accent-blue)', fontSize: 11, fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                  <MdAutoAwesome size={12} /> AI Generated · {aiSummary.model}
                </div>
                {aiSummary.summary}
              </div>
            )}
            {aiSummary?.error && (
              <div style={{ color: '#EF4444', fontSize: 13 }}>{aiSummary.error}</div>
            )}
            {!aiSummary && !loadingSummary && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Click Generate to create an AI-powered summary of this case.
              </div>
            )}
          </div>

          <div style={{ marginTop: 20 }}>
            <div className="form-label" style={{ marginBottom: 10 }}>Update Status</div>
            <select className="form-select" style={{ marginBottom: 12 }} value={status} onChange={e => setStatus(e.target.value)}>
              {allowedStatuses.map(s => <option key={s} value={s}>{s.replace(/_/g,' ')}</option>)}
            </select>
            {isAnalyst && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: -6, marginBottom: 8 }}>
                Escalate and File SAR require Supervisor or Admin role.
              </div>
            )}
          </div>

          <div style={{ marginTop: 20 }}>
            <div className="form-label" style={{ marginBottom: 10 }}>Case Notes ({notes.length})</div>
            <div className="notes-list">
              {notes.map(n => (
                <div key={n.id} className="note-item">
                  <div className="note-header">
                    <span className={`note-type-badge note-${n.note_type}`}>{n.note_type.replace(/_/g,' ')}</span>
                    <span className="note-time">{new Date(n.created_at).toLocaleString()}</span>
                  </div>
                  <div className="note-text">{n.note}</div>
                </div>
              ))}
              {notes.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No notes yet.</p>}
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
              <input className="form-input" style={{ flex: 1 }} placeholder="Add a note..."
                value={newNote} onChange={e => setNewNote(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addNote()} />
              <button className="btn btn-primary" onClick={addNote}><MdNote size={16} />Add</button>
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Cases() {
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [filters, setFilters] = useState({ status: '', priority: '', page: 1, page_size: 50 });

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    Object.entries(filters).forEach(([k,v]) => { if (v !== '') params[k] = v; });
    casesAPI.list(params).then(r => setData(r.data)).finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const statusColor = { open: '#3B82F6', investigating: '#8B5CF6', pending_review: '#F59E0B', escalated: '#EF4444', closed: '#64748B', filed_sar: '#10B981' };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Case Management</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" onClick={() => downloadCSV('/export/cases.csv', 'cases.csv')}>
            <MdDownload size={16} /> Export CSV
          </button>
          <button className="btn btn-secondary" onClick={load}><MdRefresh size={16} />Refresh</button>
        </div>
      </div>

      {/* Status summary cards */}
      <div className="cases-status-row">
        {STATUSES.map(s => {
          const count = data.items?.filter(i => i.status === s).length || 0;
          return (
            <div key={s} className="cases-status-card" onClick={() => setFilters({...filters, status: filters.status === s ? '' : s, page: 1})}
              style={{ borderTop: `3px solid ${statusColor[s] || '#64748B'}`, cursor: 'pointer', opacity: filters.status && filters.status !== s ? 0.5 : 1 }}>
              <div className="cases-count">{count}</div>
              <div className="cases-label">{s.replace(/_/g,' ')}</div>
            </div>
          );
        })}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="filters-bar" style={{ margin: 0 }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Status</label>
            <select className="form-select" value={filters.status}
              onChange={e => setFilters({...filters, status: e.target.value, page: 1})}>
              <option value="">All</option>
              {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g,' ')}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Priority</label>
            <select className="form-select" value={filters.priority}
              onChange={e => setFilters({...filters, priority: e.target.value, page: 1})}>
              <option value="">All</option>
              {PRIORITIES.map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{data.total} cases</span>
        </div>
        {loading ? <div className="loading">Loading...</div> : (
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr><th>Case #</th><th>Title</th><th>Priority</th><th>Status</th><th>SAR</th><th>Created</th></tr>
              </thead>
              <tbody>
                {data.items?.map(c => (
                  <tr key={c.id} onClick={() => setSelected(c)}>
                    <td><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{c.case_number}</span></td>
                    <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</td>
                    <td><span className={`badge badge-${c.priority}`}>{c.priority}</span></td>
                    <td><span className={`badge badge-${c.status}`}>{c.status.replace(/_/g,' ')}</span></td>
                    <td>{c.sar_filed ? <span style={{ color: '#10B981', fontWeight: 600 }}>Filed</span> : '—'}</td>
                    <td style={{ fontSize: 12 }}>{new Date(c.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
                {data.items?.length === 0 && (
                  <tr><td colSpan={6}><div className="empty-state">No cases found.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && <CaseDetailModal caseItem={selected} onClose={() => setSelected(null)} onUpdate={load} />}
    </div>
  );
}
