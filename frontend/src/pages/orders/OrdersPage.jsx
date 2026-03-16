import React, { useEffect, useState, useCallback } from 'react';
import { Layout } from '../../components/Layout';

const API_BASE = '/api';

function formatBRL(value) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value ?? 0);
}

function StatusBadge({ text }) {
  const lower = (text || '').toLowerCase();
  let cls = 'badge badge--gray';
  if (lower.includes('atendido') || lower.includes('conclu') || lower.includes('entregue')) cls = 'badge badge--green';
  else if (lower.includes('pendente') || lower.includes('aberto') || lower.includes('andamento')) cls = 'badge badge--yellow';
  else if (lower.includes('cancel') || lower.includes('devolvido')) cls = 'badge badge--red';
  return <span className={cls}>{text || '—'}</span>;
}

export function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasBling, setHasBling] = useState(false);

  const fetchOrders = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const resp = await fetch(`${API_BASE}/dashboard/summary`);
      if (!resp.ok) throw new Error('Falha ao carregar pedidos');
      const data = await resp.json();
      setHasBling(data.has_bling_auth);
      setOrders(data.recent_orders ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h2>Pedidos</h2>
          <p className="page-subtitle">Gerenciamento de pedidos de venda</p>
        </div>
        <button className="btn-refresh" onClick={fetchOrders} disabled={loading}>
          {loading ? '⟳ Atualizando…' : '⟳ Atualizar'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {!hasBling && !loading && (
        <div className="info-box">
          <p>
            <strong>🔌 Bling não conectado.</strong> Para visualizar e gerenciar pedidos reais,
            autentique-se no Bling em <code>/auth/bling/connect</code>.
          </p>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h3>📋 Pedidos de Venda</h3>
        </div>

        {loading && <p className="loading">Carregando pedidos…</p>}

        {!loading && orders.length === 0 && (
          <div className="empty-state">
            <span className="empty-state-icon">📭</span>
            <p>Nenhum pedido encontrado.</p>
            {!hasBling && (
              <p style={{ fontSize: 13, color: '#94a3b8' }}>
                Conecte o Bling para importar seus pedidos automaticamente.
              </p>
            )}
          </div>
        )}

        {!loading && orders.length > 0 && (
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
              {orders.map((order) => (
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
    </Layout>
  );
}
