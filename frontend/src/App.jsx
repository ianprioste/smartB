import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ModelsPage, ColorsPage, TemplatesPage } from './pages/admin/AdminPages';
import { WizardNewPage } from './pages/wizard/WizardNew';
import { WizardPlainPage } from './pages/wizard/WizardPlain';
import { HomePage } from './pages/home/HomePage';
import { OrdersPage } from './pages/orders/OrdersPage';
import { ProductsListPage } from './pages/products/ProductsListPage';
import { EventCreatePage } from './pages/events/EventCreatePage';
import { EventSalesPage } from './pages/events/EventSalesPage';
import { AccessControlPage } from './pages/admin/AccessControlPage';
import { LoginPage } from './pages/auth/LoginPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { ErrorBoundary } from './components/ErrorBoundary';
import './styles/admin.css';

const API_BASE = '/api';

function ProtectedRoute({ user, loading, children }) {
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', color: '#64748b' }}>
        Verificando acesso...
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/auth/access/me`, { credentials: 'include' });
        if (!resp.ok) {
          if (mounted) setUser(null);
          return;
        }
        const data = await resp.json();
        if (mounted) setUser(data.user || null);
      } catch {
        if (mounted) setUser(null);
      } finally {
        if (mounted) setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage onLoginSuccess={setUser} />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />

        <Route path="/" element={<ProtectedRoute user={user} loading={loading}><HomePage /></ProtectedRoute>} />
        <Route path="/products" element={<ProtectedRoute user={user} loading={loading}><ProductsListPage /></ProtectedRoute>} />
        <Route path="/wizard/new" element={<ProtectedRoute user={user} loading={loading}><WizardNewPage /></ProtectedRoute>} />
        <Route path="/wizard/plain" element={<ProtectedRoute user={user} loading={loading}><WizardPlainPage /></ProtectedRoute>} />
        <Route path="/admin/models" element={<ProtectedRoute user={user} loading={loading}><ModelsPage /></ProtectedRoute>} />
        <Route path="/admin/colors" element={<ProtectedRoute user={user} loading={loading}><ColorsPage /></ProtectedRoute>} />
        <Route path="/admin/templates" element={<ProtectedRoute user={user} loading={loading}><TemplatesPage /></ProtectedRoute>} />
        <Route path="/admin/access" element={<ProtectedRoute user={user} loading={loading}><AccessControlPage /></ProtectedRoute>} />
        <Route path="/orders" element={<ProtectedRoute user={user} loading={loading}><OrdersPage /></ProtectedRoute>} />
        <Route path="/events" element={<ProtectedRoute user={user} loading={loading}><EventCreatePage /></ProtectedRoute>} />
        <Route path="/events/sales" element={<ProtectedRoute user={user} loading={loading}><EventSalesPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  );
}

export default App;
