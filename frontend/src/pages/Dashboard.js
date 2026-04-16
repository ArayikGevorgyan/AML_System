import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  MdNotifications, MdSwapHoriz, MdFolder, MdPeople,
  MdTrendingUp, MdSearch, MdPrint,
} from 'react-icons/md';
import { dashboardAPI } from '../api/client';
import './Dashboard.css';

const SEVERITY_COLORS = {
  low: '#10B981', medium: '#F59E0B', high: '#EF4444', critical: '#FCA5A5',
};
const STATUS_COLORS = ['#3B82F6','#8B5CF6','#F59E0B','#EF4444','#10B981','#6366F1'];

function KPICard({ title, value, sub, icon: Icon, color, format }) {
  const formatted = format === 'currency'
    ? `$${Number(value).toLocaleString()}`
    : Number(value).toLocaleString();
  return (
    <div className="kpi-card">
      <div className="kpi-icon" style={{ background: `${color}20`, color }}>
        <Icon size={22} />
      </div>
      <div className="kpi-body">
        <div className="kpi-value">{formatted}</div>
        <div className="kpi-title">{title}</div>
        {sub && <div className="kpi-sub">{sub}</div>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardAPI.get()
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading dashboard...</div>;
  if (!data) return <div className="empty-state">Failed to load dashboard.</div>;

  const { kpis, alerts_by_severity, transaction_series, alerts_series, top_rules, recent_alerts, cases_by_status } = data;

  const sevPieData = Object.entries(alerts_by_severity).map(([name, value]) => ({ name, value }));
  const txnChartData = transaction_series.dates.map((d, i) => ({
    date: d.slice(5),
    amount: transaction_series.amounts[i],
    count: transaction_series.counts[i],
  }));
  const alertChartData = alerts_series.dates.map((d, i) => ({
    date: d.slice(5),
    alerts: alerts_series.counts[i],
  }));
  const casesPie = Object.entries(cases_by_status).filter(([,v]) => v > 0).map(([name, value]) => ({ name, value }));

  return (
    <div className="dashboard">
      <div className="dashboard-header no-print">
        <h1 className="page-title" style={{ margin: 0 }}>Dashboard</h1>
        <button className="btn btn-secondary" onClick={() => window.print()}>
          <MdPrint size={16} /> Print Report
        </button>
      </div>

      <div className="kpi-grid">
        <KPICard title="Open Alerts" value={kpis.open_alerts} icon={MdNotifications}
          color="#EF4444" sub={`${kpis.high_critical_alerts} high/critical`} />
        <KPICard title="Transactions Today" value={kpis.total_transactions_today} icon={MdSwapHoriz}
          color="#3B82F6" sub={`${kpis.flagged_transactions_today} flagged`} />
        <KPICard title="Volume Today" value={kpis.total_volume_today} icon={MdTrendingUp}
          color="#10B981" format="currency" sub={`$${kpis.total_volume_month.toLocaleString()} this month`} />
        <KPICard title="Open Cases" value={kpis.open_cases} icon={MdFolder}
          color="#8B5CF6" />
        <KPICard title="High-Risk Customers" value={kpis.high_risk_customers} icon={MdPeople}
          color="#F59E0B" />
        <KPICard title="Sanctions Checks" value={kpis.sanctions_checks_today} icon={MdSearch}
          color="#6366F1" sub="today" />
      </div>

      <div className="chart-grid-2">
        <div className="card">
          <div className="chart-header">
            <h3>Transaction Volume — Last 30 Days</h3>
            <span className="chart-badge">${kpis.total_volume_month.toLocaleString()}</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={txnChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2D3748" />
              <XAxis dataKey="date" tick={{ fill: '#64748B', fontSize: 11 }} />
              <YAxis tick={{ fill: '#64748B', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1A1D27', border: '1px solid #2D3748', borderRadius: 8, color: '#F1F5F9' }} itemStyle={{ color: '#F1F5F9' }} labelStyle={{ color: '#F1F5F9' }} />
              <Line type="monotone" dataKey="amount" stroke="#3B82F6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="chart-header">
            <h3>Alerts Generated — Last 30 Days</h3>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={alertChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2D3748" />
              <XAxis dataKey="date" tick={{ fill: '#64748B', fontSize: 11 }} />
              <YAxis tick={{ fill: '#64748B', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1A1D27', border: '1px solid #2D3748', borderRadius: 8, color: '#F1F5F9' }} itemStyle={{ color: '#F1F5F9' }} labelStyle={{ color: '#F1F5F9' }} />
              <Bar dataKey="alerts" fill="#EF4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="chart-grid-3">
        <div className="card">
          <h3 className="chart-title">Alerts by Severity</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={sevPieData} cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                paddingAngle={4} dataKey="value">
                {sevPieData.map((entry) => (
                  <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#1A1D27', border: '1px solid #2D3748', borderRadius: 8, color: '#F1F5F9' }} itemStyle={{ color: '#F1F5F9' }} labelStyle={{ color: '#F1F5F9' }} />
              <Legend formatter={(v) => <span style={{ color: '#94A3B8', fontSize: 12 }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 className="chart-title">Cases by Status</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={casesPie} cx="50%" cy="50%" outerRadius={80} paddingAngle={3} dataKey="value">
                {casesPie.map((_, i) => <Cell key={i} fill={STATUS_COLORS[i % STATUS_COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#1A1D27', border: '1px solid #2D3748', borderRadius: 8, color: '#F1F5F9' }} itemStyle={{ color: '#F1F5F9' }} labelStyle={{ color: '#F1F5F9' }} />
              <Legend formatter={(v) => <span style={{ color: '#94A3B8', fontSize: 12 }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 className="chart-title">Top Triggered Rules</h3>
          <div className="top-rules-list">
            {top_rules.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No data yet.</p>}
            {top_rules.map((r, i) => (
              <div key={i} className="top-rule-item">
                <div className="top-rule-name">{r.rule_name}</div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className={`badge badge-${r.severity}`}>{r.severity}</span>
                  <span className="top-rule-count">{r.count}×</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="chart-header">
          <h3>Recent Open Alerts</h3>
          <a href="/alerts" className="btn btn-secondary" style={{ fontSize: 12 }}>View All</a>
        </div>
        <div className="table-container" style={{ marginTop: 12 }}>
          <table>
            <thead>
              <tr>
                <th>Alert #</th><th>Customer</th><th>Severity</th>
                <th>Reason</th><th>Created</th>
              </tr>
            </thead>
            <tbody>
              {recent_alerts.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No open alerts</td></tr>
              )}
              {recent_alerts.map(a => (
                <tr key={a.id} onClick={() => window.location.href = '/alerts'}>
                  <td><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{a.alert_number}</span></td>
                  <td>{a.customer_name}</td>
                  <td><span className={`badge badge-${a.severity}`}>{a.severity}</span></td>
                  <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.reason}</td>
                  <td>{a.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
