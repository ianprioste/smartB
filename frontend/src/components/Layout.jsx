import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const API_BASE = '/api';

function useBlingStatus() {
  const [status, setStatus] = useState(null); // null = loading, true = valid, false = invalid

  const check = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/auth/bling/status`);
      if (!resp.ok) { setStatus(false); return; }
      const data = await resp.json();
      setStatus(data.valid === true);
    } catch {
      setStatus(false);
    }
  }, []);

  useEffect(() => {
    check();
    const id = setInterval(check, 30000); // re-check every 30s
    return () => clearInterval(id);
  }, [check]);

  return { status, refresh: check };
}

export function Layout({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [produtosOpen, setProdutosOpen] = useState(
    location.pathname.startsWith('/wizard') || location.pathname.startsWith('/products')
  );
  const [configOpen, setConfigOpen] = useState(
    location.pathname.startsWith('/admin')
  );
  const [configProdutosOpen, setConfigProdutosOpen] = useState(
    location.pathname.startsWith('/admin')
  );
  const { status: blingOk, refresh: recheckBling } = useBlingStatus();

  const isActive = (path) => location.pathname === path;
  const isParentActive = (paths) => paths.some((p) => location.pathname.startsWith(p));

  function go(path) {
    navigate(path);
  }

  function handleBlingAuth() {
    window.open(`${API_BASE}/auth/bling/connect`, '_blank');
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      await recheckBling();
      if (attempts >= 20) clearInterval(poll);
    }, 3000);
  }

  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-logo">✨</span>
          <span className="sidebar-title">smartBling</span>
        </div>

        <nav className="sidebar-nav">
          {/* Página Inicial */}
          <button
            className={`nav-item ${isActive('/') ? 'active' : ''}`}
            onClick={() => go('/')}
          >
            <span className="nav-icon">🏠</span>
            <span className="nav-label">Página Inicial</span>
          </button>

          {/* Produtos */}
          <div className="nav-group">
            <button
              className={`nav-item nav-group-header ${isParentActive(['/wizard', '/products']) ? 'active-parent' : ''}`}
              onClick={() => setProdutosOpen((v) => !v)}
            >
              <span className="nav-icon">📦</span>
              <span className="nav-label">Produtos</span>
              <span className={`nav-chevron ${produtosOpen ? 'open' : ''}`}>›</span>
            </button>

            {produtosOpen && (
              <div className="nav-sub">
                <button
                  className={`nav-item nav-sub-item ${isActive('/products') ? 'active' : ''}`}
                  onClick={() => go('/products')}
                >
                  <span className="nav-icon">📋</span>
                  <span className="nav-label">Listar Produtos</span>
                </button>
                <button
                  className={`nav-item nav-sub-item wizard-item ${isActive('/wizard/new') ? 'active' : ''}`}
                  onClick={() => go('/wizard/new')}
                >
                  <span className="nav-icon">🪄</span>
                  <span className="nav-label">Novo Produto Estampado</span>
                </button>
                <button
                  className={`nav-item nav-sub-item ${isActive('/wizard/plain') ? 'active' : ''}`}
                  onClick={() => go('/wizard/plain')}
                >
                  <span className="nav-icon">🧩</span>
                  <span className="nav-label">Novo Produto</span>
                </button>
              </div>
            )}
          </div>

          {/* Pedidos */}
          <button
            className={`nav-item ${isActive('/orders') ? 'active' : ''}`}
            onClick={() => go('/orders')}
          >
            <span className="nav-icon">📋</span>
            <span className="nav-label">Pedidos</span>
          </button>

          {/* Configurações */}
          <div className="nav-group">
            <button
              className={`nav-item nav-group-header ${isParentActive(['/admin']) ? 'active-parent' : ''}`}
              onClick={() => setConfigOpen((v) => !v)}
            >
              <span className="nav-icon">⚙️</span>
              <span className="nav-label">Configurações</span>
              <span className={`nav-chevron ${configOpen ? 'open' : ''}`}>›</span>
            </button>

            {configOpen && (
              <div className="nav-sub">
                {/* Configurações > Produtos (sub-grupo) */}
                <div className="nav-group">
                  <button
                    className={`nav-item nav-sub-item nav-group-header ${isParentActive(['/admin']) ? 'active-parent' : ''}`}
                    onClick={() => setConfigProdutosOpen((v) => !v)}
                  >
                    <span className="nav-icon">📦</span>
                    <span className="nav-label">Produtos</span>
                    <span className={`nav-chevron ${configProdutosOpen ? 'open' : ''}`}>›</span>
                  </button>

                  {configProdutosOpen && (
                    <div className="nav-sub nav-sub--deep">
                      <button
                        className={`nav-item nav-sub-item ${isActive('/admin/models') ? 'active' : ''}`}
                        onClick={() => go('/admin/models')}
                      >
                        <span className="nav-icon">📐</span>
                        <span className="nav-label">Modelos</span>
                      </button>
                      <button
                        className={`nav-item nav-sub-item ${isActive('/admin/colors') ? 'active' : ''}`}
                        onClick={() => go('/admin/colors')}
                      >
                        <span className="nav-icon">🎨</span>
                        <span className="nav-label">Cores</span>
                      </button>
                      <button
                        className={`nav-item nav-sub-item ${isActive('/admin/templates') ? 'active' : ''}`}
                        onClick={() => go('/admin/templates')}
                      >
                        <span className="nav-icon">📋</span>
                        <span className="nav-label">Templates</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </nav>

        {/* ── Bling Auth button ── */}
        <div className="sidebar-footer">
          <button
            className={`bling-auth-btn ${blingOk === true ? 'bling-auth-btn--ok' : blingOk === false ? 'bling-auth-btn--err' : 'bling-auth-btn--loading'}`}
            onClick={handleBlingAuth}
            title={blingOk === true ? 'Bling autenticado — clique para reconectar' : 'Clique para autenticar no Bling'}
          >
            <span className={`bling-status-dot ${blingOk === true ? 'dot--green' : blingOk === false ? 'dot--red' : 'dot--gray'}`} />
            <span className="bling-auth-label">
              {blingOk === null ? 'Verificando…' : blingOk ? 'Bling conectado' : 'Conectar Bling'}
            </span>
            <span className="bling-auth-icon">↗</span>
          </button>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <div className="page-content">
        {children}
      </div>
    </div>
  );
}
