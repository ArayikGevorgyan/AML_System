import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import Transactions from './pages/Transactions';
import Alerts from './pages/Alerts';
import Cases from './pages/Cases';
import Sanctions from './pages/Sanctions';
import Rules from './pages/Rules';
import Audit from './pages/Audit';
import Profile from './pages/Profile';
import Sessions from './pages/Sessions';
import GeoHeatmap from './pages/GeoHeatmap';
import Landing from './pages/Landing';
import Blacklist from './pages/Blacklist';

function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/home" replace />;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/home"     element={<Landing />} />
      <Route path="/login"    element={user ? <Navigate to="/dashboard" replace /> : <Login />} />
      <Route path="/register" element={<Navigate to="/home" replace />} />
      <Route path="/"         element={user ? <Navigate to="/dashboard" replace /> : <Navigate to="/home" replace />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/customers" element={<ProtectedRoute><Customers /></ProtectedRoute>} />
      <Route path="/transactions" element={<ProtectedRoute><Transactions /></ProtectedRoute>} />
      <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
      <Route path="/cases" element={<ProtectedRoute><Cases /></ProtectedRoute>} />
      <Route path="/sanctions" element={<ProtectedRoute><Sanctions /></ProtectedRoute>} />
      <Route path="/rules" element={<ProtectedRoute><Rules /></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute><Audit /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
      <Route path="/sessions" element={<ProtectedRoute><Sessions /></ProtectedRoute>} />
      <Route path="/geo-heatmap" element={<ProtectedRoute><GeoHeatmap /></ProtectedRoute>} />
      <Route path="/blacklist" element={<ProtectedRoute><Blacklist /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
