import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  MdDashboard, MdPeople, MdSwapHoriz, MdNotifications,
  MdFolder, MdSearch, MdHistory, MdPublic,
  MdSecurity, MdLogout, MdGavel, MdBlock,
  MdDevices, MdPerson, MdChevronLeft, MdChevronRight,
} from 'react-icons/md';
import { useAuth } from '../../context/AuthContext';
import './Sidebar.css';

const navItems = [
  { path: '/dashboard',    label: 'Dashboard',      icon: MdDashboard },
  { path: '/customers',    label: 'Customers',      icon: MdPeople },
  { path: '/transactions', label: 'Transactions',   icon: MdSwapHoriz },
  { path: '/alerts',       label: 'Alerts',         icon: MdNotifications },
  { path: '/cases',        label: 'Cases',          icon: MdFolder },
  { path: '/sanctions',    label: 'Sanctions Search', icon: MdSearch },
  { path: '/rules',        label: 'AML Rules',      icon: MdGavel },
  { path: '/blacklist',    label: 'List Management', icon: MdBlock },
  { path: '/audit',        label: 'Audit Logs',     icon: MdHistory },
  { path: '/geo-heatmap',  label: 'Geo Heatmap',   icon: MdPublic },
  { path: '/sessions',     label: 'Sessions',       icon: MdDevices },
  { path: '/profile',      label: 'My Profile',     icon: MdPerson },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/home');
  };

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>

      {/* Brand */}
      <div className="sidebar-brand">
        <div className="brand-icon"><MdSecurity size={22} /></div>
        {!collapsed && (
          <div>
            <div className="brand-name">AML Monitor</div>
            <div className="brand-sub">Compliance System</div>
          </div>
        )}
      </div>

      {/* Toggle button */}
      <button
        className="sidebar-toggle"
        onClick={() => setCollapsed(c => !c)}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <MdChevronRight size={18} /> : <MdChevronLeft size={18} />}
      </button>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navItems.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/dashboard'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            title={collapsed ? label : undefined}
          >
            <Icon size={18} className="nav-icon" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="user-avatar">{user?.full_name?.[0] || 'U'}</div>
        {!collapsed && (
          <div className="user-info">
            <div className="user-name">{user?.full_name}</div>
            <div className="user-role">{user?.role}</div>
          </div>
        )}
        <button className="logout-btn" onClick={handleLogout} title="Logout">
          <MdLogout size={18} />
        </button>
      </div>
    </aside>
  );
}
