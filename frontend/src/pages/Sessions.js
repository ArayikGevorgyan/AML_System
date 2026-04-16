import React, { useState, useEffect } from 'react';
import { MdComputer, MdDelete, MdRefresh } from 'react-icons/md';
import client from '../api/client';

export default function Sessions() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await client.get('/sessions');
      setSessions(res.data);
    } catch (e) { } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const forceLogout = async (id) => {
    await client.delete(`/sessions/${id}`);
    load();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 className="page-title" style={{ marginBottom: 0 }}>Active Sessions</h2>
        <button className="btn btn-secondary" onClick={load}><MdRefresh size={16} /> Refresh</button>
      </div>
      {loading ? <div className="loading">Loading...</div> : (
        <div className="table-container card">
          <table>
            <thead>
              <tr>
                <th>User</th><th>Role</th><th>IP Address</th><th>Browser</th><th>Login Time</th><th>Last Seen</th><th>Action</th>
              </tr>
            </thead>
            <tbody>
              {sessions.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No active sessions</td></tr>
              ) : sessions.map(s => (
                <tr key={s.id}>
                  <td><strong>{s.full_name}</strong><br /><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>@{s.username}</span></td>
                  <td><span className="badge badge-open">{s.role}</span></td>
                  <td>{s.ip_address || '—'}</td>
                  <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.user_agent ? s.user_agent.substring(0, 60) + '...' : '—'}</td>
                  <td>{s.created_at ? new Date(s.created_at).toLocaleString() : '—'}</td>
                  <td>{s.last_seen ? new Date(s.last_seen).toLocaleString() : '—'}</td>
                  <td>
                    <button className="btn btn-danger" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => forceLogout(s.id)}>
                      <MdDelete size={14} /> Force Logout
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
