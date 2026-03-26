import React, { useEffect, useState, useCallback } from 'react';
import { Layout } from '../../components/Layout';

const API_BASE = '/api';

function StatCard({ icon, label, value, sub, accent }) {
  return (
    <div className={`stat-card ${accent ? `stat-card--${accent}` : ''}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-body">
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  );
}

function formatBRL(value) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
}

function StatusBadge({ text }) {
  const lower = (text || '').toLowerCase();
  let cls = 'badge badge--gray';
  if (lower.includes('atendido') || lower.includes('conclu') || lower.includes('entregue')) cls = 'badge badge--green';
  else if (lower.includes('pendente') || lower.includes('aberto') || lower.includes('andamento')) cls = 'badge badge--yellow';
  else if (lower.includes('cancel') || lower.includes('devolvido')) cls = 'badge badge--red';
  return <span className={cls}>{text || '—'}</span>;
}

export function HomePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSummary = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const resp = await fetch(`${API_BASE}/dashboard/summary`);
      if (!resp.ok) throw new Error('Falha ao carregar indicadores');
      setData(await resp.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSummary(); }, [fetchSummary]);

  return (
    <Layout>
      <div className="page-inner">
      <div className="page-header">
        <div>
          <h2>Página Inicial</h2>
          <p className="page-subtitle">Visão geral do negócio</p>
        </div>
        <button className="btn-secondary" onClick={fetchSummary} disabled={loading}>
          {loading ? 'Atualizando...' : 'Atualizar'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {!data?.has_bling_auth && !loading && (
        <div className="info-box" style={{ marginBottom: 24 }}>
          <p>
            <strong>🔌 Bling não conectado.</strong> Os indicadores abaixo mostram dados zerados.
            Para ver dados reais, autentique-se em <code>/auth/bling/connect</code>.
          </p>
        </div>
      )}

      {/* ── KPI cards ── */}
      <div className="stats-grid">
        <StatCard
          icon="💰"
          label="Total vendido hoje"
          value={loading ? '…' : formatBRL(data?.total_sold_today ?? 0)}
          accent="blue"
        />
        <StatCard
          icon="📈"
          label="Total vendido no mês"
          value={loading ? '…' : formatBRL(data?.total_sold_month ?? 0)}
          accent="green"
        />
        <StatCard
          icon="🛒"
          label="Pedidos do dia"
          value={loading ? '…' : (data?.orders_today ?? 0)}
          accent="purple"
        />
        <StatCard
          icon="⏳"
          label="Pedidos pendentes"
          value={loading ? '…' : (data?.pending_orders ?? 0)}
          accent="yellow"
        />
        <StatCard
          icon="📦"
          label="Produtos com estoque baixo"
          value={loading ? '…' : (data?.low_stock_products ?? 0)}
          accent="red"
        />
      </div>

      {/* ── Recent orders ── */}
      <div className="card" style={{ marginTop: 28 }}>
        <div className="card-header">
          <h3>🕐 Últimos Pedidos</h3>
        </div>

        {loading && <p className="loading">Carregando pedidos…</p>}

        {!loading && (!data?.recent_orders || data.recent_orders.length === 0) && (
          <div className="empty-state">
            <span className="empty-state-icon">📋</span>
            <p>Nenhum pedido encontrado no período.</p>
            {!data?.has_bling_auth && (
              <p style={{ fontSize: 13, color: '#94a3b8' }}>
                Conecte o Bling para ver pedidos reais.
              </p>
            )}
          </div>
        )}

        {!loading && data?.recent_orders && data.recent_orders.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Data</th>
                <th>Cliente</th>
                <th>Total</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_orders.map((order) => (
                <tr key={order.id ?? order.numero}>
                  <td style={{ fontWeight: 600 }}>{order.numero ?? order.id}</td>
                  <td>{order.data ? new Date(order.data).toLocaleDateString('pt-BR') : '—'}</td>
                  <td>{order.cliente}</td>
                  <td style={{ fontWeight: 600 }}>{formatBRL(order.total)}</td>
                  <td><StatusBadge text={order.situacao} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      </div>
    </Layout>
  );
}
