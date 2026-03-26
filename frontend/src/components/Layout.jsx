import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const API_BASE = '/api';

function HamburgerBtn({ open, onClick }) {
  return (
    <button
      className={`hamburger-btn${open ? ' hamburger-btn--open' : ''}`}
      onClick={onClick}
      aria-label={open ? 'Fechar menu' : 'Abrir menu'}
    >
      <span />
      <span />
      <span />
    </button>
  );
}

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
  const [menuOpen, setMenuOpen] = useState(false);
  const [produtosOpen, setProdutosOpen] = useState(
    location.pathname.startsWith('/wizard') || location.pathname.startsWith('/products')
  );
  const [configOpen, setConfigOpen] = useState(
    location.pathname.startsWith('/admin')
  );
  const [configProdutosOpen, setConfigProdutosOpen] = useState(
    location.pathname.startsWith('/admin/models') ||
    location.pathname.startsWith('/admin/colors') ||
    location.pathname.startsWith('/admin/templates')
  );
  const { status: blingOk, refresh: recheckBling } = useBlingStatus();

  // Fecha o menu ao navegar
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  // Bloqueia scroll do body quando o menu mobile está aberto
  useEffect(() => {
    document.body.classList.toggle('menu-open', menuOpen);
    return () => document.body.classList.remove('menu-open');
  }, [menuOpen]);

  const isActive = (path) => location.pathname === path;
  const isParentActive = (paths) => paths.some((p) => location.pathname.startsWith(p));

  function go(path) {
    navigate(path);
    setMenuOpen(false);
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

  async function handleLogout() {
    try {
      await fetch(`${API_BASE}/auth/access/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // Ignore network errors; redirect anyway.
    }
    window.location.href = '/login';
  }

  return (
    <div className="app-shell">
      {/* ── Overlay mobile ── */}
      {menuOpen && (
        <div className="sidebar-overlay" onClick={() => setMenuOpen(false)} />
      )}

      {/* ── Sidebar ── */}
      <aside className={`sidebar${menuOpen ? ' sidebar--open' : ''}`}>
        <div className="sidebar-brand">
          <span className="sidebar-logo">✨</span>
          <span className="sidebar-title">smartBling</span>
          <HamburgerBtn open={menuOpen} onClick={() => setMenuOpen(false)} />
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

          <div className="nav-group">
            <button
              className={`nav-item nav-group-header ${isParentActive(['/events']) ? 'active-parent' : ''}`}
              onClick={() => go('/events')}
            >
              <span className="nav-icon">🎪</span>
              <span className="nav-label">Eventos de Vendas</span>
            </button>
            <div className="nav-sub">
              <button
                className={`nav-item nav-sub-item ${isActive('/events') ? 'active' : ''}`}
                onClick={() => go('/events')}
              >
                <span className="nav-icon">📝</span>
                <span className="nav-label">Cadastrar Evento</span>
              </button>
              <button
                className={`nav-item nav-sub-item ${isActive('/events/sales') ? 'active' : ''}`}
                onClick={() => go('/events/sales')}
              >
                <span className="nav-icon">💵</span>
                <span className="nav-label">Vendas por Evento</span>
              </button>
            </div>
          </div>

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
                <button
                  className={`nav-item nav-sub-item ${isActive('/admin/access') ? 'active' : ''}`}
                  onClick={() => go('/admin/access')}
                >
                  <span className="nav-icon">🔐</span>
                  <span className="nav-label">Perfis de Acesso</span>
                </button>

                {/* Configurações > Produtos (sub-grupo) */}
                <div className="nav-group">
                  <button
                    className={`nav-item nav-sub-item nav-group-header ${isParentActive(['/admin/models', '/admin/colors', '/admin/templates']) ? 'active-parent' : ''}`}
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
            className="btn-secondary"
            onClick={handleLogout}
            style={{ width: '100%', marginBottom: 8 }}
            title="Sair da sessão"
          >
            Sair
          </button>
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
        {/* Topbar mobile com hamburger */}
        <header className="mobile-topbar">
          <span className="sidebar-logo">✨</span>
          <span className="sidebar-title" style={{ flex: 1, color: '#f8fafc' }}>smartBling</span>
          <HamburgerBtn open={menuOpen} onClick={() => setMenuOpen((v) => !v)} />
        </header>
        {children}
      </div>
    </div>
  );
}
