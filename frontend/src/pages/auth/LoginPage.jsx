import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const API_BASE = '/api';

export function LoginPage({ onLoginSuccess }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checkingBootstrap, setCheckingBootstrap] = useState(true);
  const [bootstrapHint, setBootstrapHint] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/auth/access/bootstrap-status`, { credentials: 'include' });
        const data = await resp.json();
        if (!mounted) return;
        if (data.needs_bootstrap) {
          const masterEmail = data.master_admin_email || 'ian.prioste@useruach.com.br';
          setBootstrapHint(`Primeiro acesso: entre com ${masterEmail} e defina sua senha de administrador.`);
        }
      } catch {
        // Ignore bootstrap hint failures
      } finally {
        if (mounted) setCheckingBootstrap(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const resp = await fetch(`${API_BASE}/auth/access/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password, remember_me: rememberMe }),
      });

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || 'Falha no login');
      }

      onLoginSuccess?.(data.user);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Falha no login');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)', padding: 16 }}>
      <div style={{ width: '100%', maxWidth: 420, background: '#ffffff', borderRadius: 16, boxShadow: '0 20px 50px rgba(15, 23, 42, 0.08)', border: '1px solid #e2e8f0' }}>
        <div style={{ padding: 24, borderBottom: '1px solid #e2e8f0' }}>
          <h2 style={{ margin: 0, color: '#0f172a' }}>Controle de Acesso</h2>
          <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 14 }}>Entre com seu e-mail corporativo autorizado</p>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: 24 }}>
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label htmlFor="email">E-mail</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              placeholder="nome@empresa.com"
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group" style={{ marginBottom: 16 }}>
            <label htmlFor="password">Senha</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              placeholder="Digite sua senha"
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              id="rememberMe"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              style={{ width: 18, height: 18, cursor: 'pointer' }}
            />
            <label 
              htmlFor="rememberMe" 
              style={{ cursor: 'pointer', userSelect: 'none', fontSize: 14, color: '#475569', margin: 0 }}
            >
              Manter-me conectado neste dispositivo
            </label>
          </div>

          {checkingBootstrap ? (
            <p style={{ fontSize: 13, color: '#94a3b8', marginTop: 0 }}>Verificando configuração inicial...</p>
          ) : bootstrapHint ? (
            <p style={{ fontSize: 13, color: '#0369a1', background: '#e0f2fe', border: '1px solid #bae6fd', padding: 10, borderRadius: 8 }}>{bootstrapHint}</p>
          ) : null}

          {error && (
            <div className="error" style={{ marginBottom: 12 }}>{error}</div>
          )}

          <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  );
}
