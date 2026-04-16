import React, { useState, useEffect, useRef } from 'react';
import { MdNotifications, MdLightMode, MdDarkMode } from 'react-icons/md';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { alertsAPI } from '../../api/client';
import './Topbar.css';

const PAGE_TITLES = {
  '/': 'Dashboard',
  '/customers': 'Customers',
  '/transactions': 'Transactions',
  '/alerts': 'Alerts',
  '/cases': 'Case Management',
  '/sanctions': 'Sanctions Screening',
  '/rules': 'AML Rules Engine',
  '/audit': 'Audit Logs',
};

const SEVERITY_COLORS = {
  low: '#10B981',
  medium: '#FBBF24',
  high: '#F97316',
  critical: '#F87171',
};

export default function Topbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const title = PAGE_TITLES[location.pathname] || 'AML System';
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const dropdownRef = useRef(null);

  useEffect(() => {
    alertsAPI.list({ status: 'open', limit: 5 }).then(res => {
      setAlerts(res.data?.items || res.data || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-left">
        <h1 className="topbar-title">{title}</h1>
        <span className="topbar-date">
          {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </span>
      </div>
      <div className="topbar-right">
        <div className="topbar-env-badge">DEMO ENV</div>
        <button className="topbar-icon-btn" title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'} onClick={toggleTheme}>
          {theme === 'dark' ? <MdLightMode size={20} /> : <MdDarkMode size={20} />}
        </button>

        <div className="notif-wrapper" ref={dropdownRef}>
          <button className="topbar-icon-btn" title="Alerts" onClick={() => setOpen(o => !o)}>
            <MdNotifications size={20} />
            {alerts.length > 0 && <span className="notif-dot" />}
          </button>

          {open && (
            <div className="notif-dropdown">
              <div className="notif-dropdown-header">
                <span>Recent Open Alerts</span>
                <span className="notif-count">{alerts.length}</span>
              </div>
              {alerts.length === 0 ? (
                <div className="notif-empty">No open alerts</div>
              ) : (
                alerts.slice(0, 5).map(alert => (
                  <div key={alert.id} className="notif-item" onClick={() => { navigate('/alerts'); setOpen(false); }}>
                    <span className="notif-severity" style={{ background: SEVERITY_COLORS[alert.severity] }} />
                    <div className="notif-item-body">
                      <div className="notif-item-number">{alert.alert_number}</div>
                      <div className="notif-item-reason">{alert.reason}</div>
                    </div>
                    <span className="notif-item-badge" style={{ color: SEVERITY_COLORS[alert.severity] }}>
                      {alert.severity}
                    </span>
                  </div>
                ))
              )}
              <div className="notif-footer" onClick={() => { navigate('/alerts'); setOpen(false); }}>
                View all alerts →
              </div>
            </div>
          )}
        </div>

        <div className="topbar-user">
          <span>{user?.full_name}</span>
          <span className="topbar-role-badge">{user?.role}</span>
        </div>
      </div>
    </header>
  );
}
