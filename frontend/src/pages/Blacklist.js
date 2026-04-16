import React, { useState, useEffect, useCallback } from 'react';
import {
  MdBlock, MdWarning, MdCheckCircle, MdHistory,
  MdAdd, MdRefresh, MdArrowForward,
} from 'react-icons/md';
import { blacklistAPI } from '../api/client';
import './Blacklist.css';

const LIST_TYPES   = ['black', 'yellow', 'white'];
const ENTRY_TYPES  = ['entity', 'email', 'account', 'ip', 'country'];
const SEVERITIES   = ['low', 'medium', 'high', 'critical'];

const LIST_META = {
  black:  { label: 'Blacklist',  icon: MdBlock,        color: '#EF4444', bg: 'rgba(239,68,68,0.12)'  },
  yellow: { label: 'Watchlist',  icon: MdWarning,      color: '#F59E0B', bg: 'rgba(245,158,11,0.12)' },
  white:  { label: 'Whitelist',  icon: MdCheckCircle,  color: '#10B981', bg: 'rgba(16,185,129,0.12)' },
};

function ListBadge({ type }) {
  const m = LIST_META[type] || LIST_META.black;
  const Icon = m.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700,
      background: m.bg, color: m.color,
    }}>
      <Icon size={12} />{m.label}
    </span>
  );
}

function MoveModal({ entry, onClose, onMoved }) {
  const [toList, setToList]     = useState('yellow');
  const [reason, setReason]     = useState('');
  const [note, setNote]         = useState('');
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState('');

  const available = LIST_TYPES.filter(l => l !== entry.list_type);

  const handleMove = async () => {
    if (!reason.trim()) { setError('Reason is required.'); return; }
    setSaving(true);
    try {
      await blacklistAPI.move(entry.id, { to_list: toList, reason, review_note: note });
      onMoved();
      onClose();
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to move entry.');
    } finally { setSaving(false); }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 500 }}>
        <div className="modal-header">
          <div className="modal-title">Move Entry</div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div style={{ marginBottom: 16, padding: '10px 14px', background: 'var(--bg-hover)', borderRadius: 8, border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{entry.value}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{entry.entry_type} · {entry.reason}</div>
            <div style={{ marginTop: 6 }}><ListBadge type={entry.list_type} /></div>
          </div>

          <div className="form-group">
            <label className="form-label">Move To</label>
            <div style={{ display: 'flex', gap: 10 }}>
              {available.map(l => {
                const m = LIST_META[l];
                const Icon = m.icon;
                return (
                  <button key={l} onClick={() => setToList(l)} style={{
                    flex: 1, padding: '10px 0', borderRadius: 8, border: `2px solid ${toList === l ? m.color : 'var(--border)'}`,
                    background: toList === l ? m.bg : 'var(--bg-card)', color: toList === l ? m.color : 'var(--text-muted)',
                    cursor: 'pointer', fontWeight: 700, fontSize: 13,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  }}>
                    <Icon size={16} />{m.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Reason *</label>
            <input className="form-input" placeholder="Why is this entry being moved?"
              value={reason} onChange={e => setReason(e.target.value)} />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Review Note (optional)</label>
            <textarea className="form-input" rows={2} placeholder="Additional notes or evidence..."
              value={note} onChange={e => setNote(e.target.value)}
              style={{ resize: 'vertical', fontFamily: 'inherit' }} />
          </div>

          {error && <div className="login-error" style={{ marginTop: 12 }}>⚠ {error}</div>}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleMove} disabled={saving}>
            <MdArrowForward size={15} /> {saving ? 'Moving...' : `Move to ${LIST_META[toList].label}`}
          </button>
        </div>
      </div>
    </div>
  );
}

function HistoryModal({ entry, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    blacklistAPI.history(entry.id)
      .then(r => setLogs(r.data))
      .finally(() => setLoading(false));
  }, [entry.id]);

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 520 }}>
        <div className="modal-header">
          <div className="modal-title">Movement History — {entry.value}</div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {loading && <div className="loading">Loading...</div>}
          {!loading && logs.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No history found.</div>}
          {logs.map((l, i) => (
            <div key={i} style={{
              display: 'flex', gap: 12, padding: '12px 0',
              borderBottom: i < logs.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 180 }}>
                <ListBadge type={l.from_list === 'none' ? 'white' : l.from_list} />
                <MdArrowForward size={14} style={{ color: 'var(--text-muted)' }} />
                <ListBadge type={l.to_list} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>{l.reason}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                  {l.moved_by || 'System'} · {new Date(l.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function AddModal({ onClose, onAdded }) {
  const [form, setForm] = useState({ entry_type: 'entity', value: '', reason: '', severity: 'high', list_type: 'black' });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');
  const set = f => e => setForm({ ...form, [f]: e.target.value });

  const handleAdd = async () => {
    if (!form.value.trim() || !form.reason.trim()) { setError('Value and reason are required.'); return; }
    setSaving(true);
    try {
      await blacklistAPI.create(form);
      onAdded();
      onClose();
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to add entry.');
    } finally { setSaving(false); }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <div className="modal-title">Add New Entry</div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label className="form-label">List Type</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {LIST_TYPES.map(l => {
                const m = LIST_META[l];
                const Icon = m.icon;
                return (
                  <button key={l} onClick={() => setForm({ ...form, list_type: l })} style={{
                    flex: 1, padding: '8px 0', borderRadius: 8,
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
            <label className="form-label">Type</label>
            <select className="form-select" value={form.entry_type} onChange={set('entry_type')}>
              {ENTRY_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Value</label>
            <input className="form-input" placeholder="Name, email, IP, account..." value={form.value} onChange={set('value')} />
          </div>
          <div className="form-group">
            <label className="form-label">Severity</label>
            <select className="form-select" value={form.severity} onChange={set('severity')}>
              {SEVERITIES.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Reason *</label>
            <input className="form-input" placeholder="Why is this being added?" value={form.reason} onChange={set('reason')} />
          </div>
          {error && <div className="login-error" style={{ marginTop: 12 }}>⚠ {error}</div>}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleAdd} disabled={saving}>
            {saving ? 'Adding...' : 'Add Entry'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Blacklist() {
  const [entries, setEntries]     = useState([]);
  const [stats, setStats]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [filterList, setFilterList] = useState('');
  const [filterType, setFilterType] = useState('');
  const [moveTarget, setMoveTarget] = useState(null);
  const [histTarget, setHistTarget] = useState(null);
  const [showAdd, setShowAdd]     = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    if (filterList) params.list_type = filterList;
    if (filterType) params.entry_type = filterType;
    Promise.all([
      blacklistAPI.list(params),
      blacklistAPI.stats(),
    ]).then(([e, s]) => {
      setEntries(e.data);
      setStats(s.data);
    }).finally(() => setLoading(false));
  }, [filterList, filterType]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>List Management</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" onClick={load}><MdRefresh size={16} /> Refresh</button>
          <button className="btn btn-primary" onClick={() => setShowAdd(true)}><MdAdd size={16} /> Add Entry</button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 20 }}>
          {LIST_TYPES.map(lt => {
            const m = LIST_META[lt];
            const Icon = m.icon;
            return (
              <div key={lt} className="kpi-card" style={{ cursor: 'pointer', borderColor: filterList === lt ? m.color : undefined }}
                onClick={() => setFilterList(filterList === lt ? '' : lt)}>
                <div className="kpi-icon" style={{ background: m.bg, color: m.color }}><Icon size={22} /></div>
                <div className="kpi-body">
                  <div className="kpi-value">{stats.by_list?.[lt] ?? 0}</div>
                  <div className="kpi-title">{m.label} Entries</div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Filters */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="filters-bar" style={{ margin: 0 }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">List</label>
            <select className="form-select" value={filterList} onChange={e => setFilterList(e.target.value)}>
              <option value="">All Lists</option>
              {LIST_TYPES.map(l => <option key={l} value={l}>{LIST_META[l].label}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Type</label>
            <select className="form-select" value={filterType} onChange={e => setFilterType(e.target.value)}>
              <option value="">All Types</option>
              {ENTRY_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{entries.length} entries</span>
        </div>
        {loading ? <div className="loading">Loading...</div> : (
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>List</th><th>Type</th><th>Value</th><th>Severity</th>
                  <th>Reason</th><th>Review Note</th><th>Added</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {entries.length === 0 && (
                  <tr><td colSpan={8} className="empty-state">No entries found.</td></tr>
                )}
                {entries.map(e => (
                  <tr key={e.id}>
                    <td><ListBadge type={e.list_type} /></td>
                    <td><span className="badge badge-medium">{e.entry_type}</span></td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{e.value}</td>
                    <td><span className={`badge badge-${e.severity}`}>{e.severity}</span></td>
                    <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>{e.reason}</td>
                    <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12, color: 'var(--text-muted)' }}>
                      {e.review_note || '—'}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{new Date(e.created_at).toLocaleDateString()}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12 }}
                          onClick={() => setMoveTarget(e)}>
                          <MdArrowForward size={13} /> Move
                        </button>
                        <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12 }}
                          onClick={() => setHistTarget(e)}>
                          <MdHistory size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {moveTarget  && <MoveModal    entry={moveTarget} onClose={() => setMoveTarget(null)}  onMoved={load} />}
      {histTarget  && <HistoryModal entry={histTarget} onClose={() => setHistTarget(null)} />}
      {showAdd     && <AddModal     onClose={() => setShowAdd(false)} onAdded={load} />}
    </div>
  );
}
