import React, { useState, useEffect, useCallback } from 'react';
import { MdRefresh, MdHistory } from 'react-icons/md';
import { auditAPI } from '../api/client';
import './Audit.css';

const ACTION_COLORS = {
  LOGIN: '#10B981', LOGOUT: '#64748B', CREATE_CUSTOMER: '#3B82F6',
  UPDATE_CUSTOMER: '#3B82F6', CREATE_TRANSACTION: '#8B5CF6',
  CREATE_ALERT: '#EF4444', UPDATE_ALERT: '#F59E0B',
  CREATE_CASE: '#F59E0B', UPDATE_CASE: '#F59E0B', ADD_CASE_NOTE: '#6366F1',
  SANCTIONS_SEARCH: '#06B6D4', IMPORT_SDN: '#10B981',
  CREATE_RULE: '#3B82F6', UPDATE_RULE: '#3B82F6', CREATE_USER: '#8B5CF6',
};

export default function Audit() {
  const [data, setData] = useState({ items: [], total: 0 });
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ action: '', entity_type: '', page: 1, page_size: 50 });

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    Object.entries(filters).forEach(([k,v]) => { if (v !== '') params[k] = v; });
    auditAPI.list(params).then(r => setData(r.data)).finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { auditAPI.actions().then(r => setActions(r.data)).catch(() => {}); }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Audit Logs</h1>
        <button className="btn btn-secondary" onClick={load}><MdRefresh size={16} />Refresh</button>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="filters-bar" style={{ margin: 0 }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Action</label>
            <select className="form-select" value={filters.action}
              onChange={e => setFilters({...filters, action: e.target.value, page: 1})}>
              <option value="">All Actions</option>
              {actions.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Entity Type</label>
            <select className="form-select" value={filters.entity_type}
              onChange={e => setFilters({...filters, entity_type: e.target.value, page: 1})}>
              <option value="">All Entities</option>
              {['transaction','alert','case','customer','rule','user'].map(e => <option key={e}>{e}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 10, alignItems: 'center' }}>
          <MdHistory size={18} style={{ color: 'var(--text-muted)' }} />
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{data.total} audit entries</span>
        </div>

        {loading ? <div className="loading">Loading...</div> : (
          <div className="audit-log-list">
            {data.items?.map(log => {
              const color = ACTION_COLORS[log.action] || '#64748B';
              return (
                <div key={log.id} className="audit-log-item">
                  <div className="audit-log-indicator" style={{ background: color }} />
                  <div className="audit-log-content">
                    <div className="audit-log-row">
                      <span className="audit-action" style={{ color }}>{log.action}</span>
                      {log.entity_type && (
                        <span className="audit-entity">{log.entity_type} #{log.entity_id}</span>
                      )}
                      <span className="audit-time">
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="audit-log-row2">
                      <span className="audit-user">👤 {log.username || 'system'}</span>
                      {log.description && <span className="audit-desc">{log.description}</span>}
                      {log.ip_address && <span className="audit-ip">IP: {log.ip_address}</span>}
                    </div>
                    {(log.old_value || log.new_value) && (
                      <div className="audit-changes">
                        {log.old_value && (
                          <div className="audit-change audit-old">
                            <span>Before:</span>
                            <code>{log.old_value}</code>
                          </div>
                        )}
                        {log.new_value && (
                          <div className="audit-change audit-new">
                            <span>After:</span>
                            <code>{log.new_value}</code>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {data.items?.length === 0 && (
              <div className="empty-state">No audit logs match your filters.</div>
            )}
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
    </div>
  );
}
