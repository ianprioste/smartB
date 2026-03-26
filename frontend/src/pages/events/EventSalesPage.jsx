import React, { useEffect, useMemo, useState } from 'react';
import { Layout } from '../../components/Layout';

const API_BASE = '/api';
const EVENT_STATUS_FILTERS = ['Em aberto', 'Atendido', 'Cancelado'];

function formatBRL(value) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value ?? 0);
}

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('pt-BR');
}

function StatusBadge({ text }) {
  const lower = (text || '').toLowerCase();
  let cls = 'badge badge--gray';
  if (lower.includes('atendido') || lower.includes('conclu') || lower.includes('entregue')) cls = 'badge badge--green';
  else if (lower.includes('pendente') || lower.includes('aberto') || lower.includes('andamento')) cls = 'badge badge--yellow';
  else if (lower.includes('cancel') || lower.includes('devolvido')) cls = 'badge badge--red';
  return <span className={cls}>{text || '—'}</span>;
}

function ChevronIcon({ isExpanded }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
        transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        display: 'inline-block',
      }}
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function normalizeStatusLabel(value) {
  const lower = (value || '').toString().toLowerCase();
  if (lower.includes('cancel')) return 'Cancelado';
  if (lower.includes('conclu') || lower.includes('atendid') || lower.includes('entreg') || lower.includes('andamento')) return 'Atendido';
  if (lower.includes('aberto') || lower.includes('pendente')) return 'Em aberto';
  return 'Outros';
}

export function EventSalesPage() {
  const [events, setEvents] = useState([]);
  const [selectedEventId, setSelectedEventId] = useState('');
  const [salesData, setSalesData] = useState(null);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [loadingSales, setLoadingSales] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState(() => new Set(EVENT_STATUS_FILTERS));
  const [expandedOrderId, setExpandedOrderId] = useState(null);

  async function loadEvents() {
    try {
      setLoadingEvents(true);
      const resp = await fetch(`${API_BASE}/events`);
      if (!resp.ok) throw new Error('Falha ao carregar eventos');
      const data = await resp.json();
      const list = Array.isArray(data) ? data : [];
      setEvents(list);
      if (!selectedEventId && list.length > 0) {
        setSelectedEventId(list[0].id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingEvents(false);
    }
  }

  async function loadSales(eventId) {
    if (!eventId) {
      setSalesData(null);
      return;
    }

    try {
      setLoadingSales(true);
      setError(null);
      const resp = await fetch(`${API_BASE}/events/${eventId}/sales`);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Falha ao carregar vendas do evento');
      }
      setSalesData(await resp.json());
    } catch (err) {
      setError(err.message);
      setSalesData(null);
    } finally {
      setLoadingSales(false);
    }
  }

  useEffect(() => {
    loadEvents();
  }, []);

  useEffect(() => {
    if (selectedEventId) {
      loadSales(selectedEventId);
    }
  }, [selectedEventId]);

  const visibleOrders = useMemo(() => {
    const allOrders = Array.isArray(salesData?.orders) ? salesData.orders : [];
    const term = (searchTerm || '').trim().toLowerCase();

    return allOrders.filter((order) => {
      const statusLabel = normalizeStatusLabel(order.situacao);
      const statusOk = selectedStatuses.has(statusLabel);
      if (!statusOk) return false;

      if (!term) return true;

      const pedidoText = String(order.numero || order.id || '').toLowerCase();
      const clienteText = String(order.cliente || '').toLowerCase();
      return pedidoText.includes(term) || clienteText.includes(term);
    });
  }, [salesData, searchTerm, selectedStatuses]);

  const filteredSummary = useMemo(() => {
    const matchedItemsCount = visibleOrders.reduce((acc, order) => acc + (order.matched_items?.length || 0), 0);
    const totalMatched = visibleOrders.reduce((acc, order) => acc + (order.total_matched || 0), 0);
    return {
      orders_count: visibleOrders.length,
      matched_items_count: matchedItemsCount,
      total_matched: totalMatched,
    };
  }, [visibleOrders]);

  const toggleStatus = (label) => {
    setSelectedStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const toggleOrder = (orderId) => {
    setExpandedOrderId((prev) => (prev === orderId ? null : orderId));
  };

  return (
    <Layout>
      <div className="page-inner">
        <div className="page-header">
          <div>
            <h2>Vendas por Evento</h2>
            <p className="page-subtitle">Pedidos de venda filtrados pelos produtos selecionados no evento</p>
          </div>
          <button className="btn-secondary" disabled={!selectedEventId || loadingSales} onClick={() => loadSales(selectedEventId)}>
            {loadingSales ? 'Atualizando...' : 'Atualizar'}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <h3>📌 Seleção de Evento</h3>
          </div>
          <div style={{ padding: 20 }}>
            {loadingEvents ? (
              <p className="loading">Carregando eventos...</p>
            ) : (
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label>Evento</label>
                <select value={selectedEventId} onChange={(e) => setSelectedEventId(e.target.value)}>
                  <option value="">Selecione um evento</option>
                  {events.map((event) => (
                    <option value={event.id} key={event.id}>
                      {event.name} ({formatDate(event.start_date)} - {formatDate(event.end_date)})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {salesData && (
          <>
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ padding: '16px 20px' }}>
                <div className="search-box" style={{ marginBottom: 12 }}>
                  <input
                    type="text"
                    placeholder="Buscar por nº do pedido ou nome do cliente..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: '#64748b', marginRight: 4 }}>Status:</span>
                  {EVENT_STATUS_FILTERS.map((statusLabel) => (
                    <button
                      key={statusLabel}
                      onClick={() => toggleStatus(statusLabel)}
                      style={{
                        cursor: 'pointer',
                        border: selectedStatuses.has(statusLabel) ? '2px solid #3b82f6' : '2px solid transparent',
                        padding: '5px 12px',
                        borderRadius: 16,
                        fontSize: 13,
                        fontWeight: selectedStatuses.has(statusLabel) ? 600 : 400,
                        background: selectedStatuses.has(statusLabel) ? '#dbeafe' : '#f1f5f9',
                        color: selectedStatuses.has(statusLabel) ? '#1d4ed8' : '#475569',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {statusLabel}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="stats-grid" style={{ marginBottom: 16 }}>
              <div className="stat-card stat-card--blue">
                <div className="stat-body">
                  <div className="stat-value">{filteredSummary.orders_count}</div>
                  <div className="stat-label">Pedidos com Itens do Evento</div>
                </div>
              </div>
              <div className="stat-card stat-card--green">
                <div className="stat-body">
                  <div className="stat-value">{filteredSummary.matched_items_count}</div>
                  <div className="stat-label">Itens Relacionados</div>
                </div>
              </div>
              <div className="stat-card stat-card--yellow">
                <div className="stat-body">
                  <div className="stat-value">{formatBRL(filteredSummary.total_matched)}</div>
                  <div className="stat-label">Total dos Itens do Evento</div>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3>📋 Pedidos Filtrados</h3>
                {!loadingSales && <span style={{ fontSize: 13, color: '#94a3b8' }}>{filteredSummary.orders_count} pedido(s)</span>}
              </div>
              {loadingSales ? (
                <p className="loading">Carregando vendas...</p>
              ) : visibleOrders.length === 0 ? (
                <div className="empty-state">
                  <span className="empty-state-icon">📭</span>
                  <p>Nenhuma venda encontrada para os produtos deste evento no período selecionado.</p>
                </div>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: 40 }}></th>
                      <th>Pedido</th>
                      <th>Data</th>
                      <th>Cliente</th>
                      <th>Situação</th>
                      <th>Itens do Evento</th>
                      <th>Total Itens Evento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleOrders.map((order) => {
                      const orderKey = order.id || order.numero;
                      const isExpanded = expandedOrderId === orderKey;
                      const matchedItems = Array.isArray(order.matched_items) ? order.matched_items : [];

                      return (
                        <React.Fragment key={orderKey}>
                          <tr
                            style={{ cursor: 'pointer', background: isExpanded ? '#f0f9ff' : undefined }}
                            onClick={() => toggleOrder(orderKey)}
                          >
                            <td style={{ textAlign: 'center', color: '#64748b', paddingTop: 12, paddingBottom: 12 }}>
                              {matchedItems.length > 0 && <ChevronIcon isExpanded={isExpanded} />}
                            </td>
                            <td style={{ fontWeight: 600 }}>{order.numero || order.id}</td>
                            <td>{formatDate(order.data)}</td>
                            <td>{order.cliente || '—'}</td>
                            <td><StatusBadge text={order.situacao} /></td>
                            <td>{matchedItems.length}</td>
                            <td style={{ fontWeight: 600 }}>{formatBRL(order.total_matched)}</td>
                          </tr>

                          {isExpanded && matchedItems.length > 0 && (
                            <tr style={{ background: '#f8fafc', borderTop: '2px solid #e2e8f0' }}>
                              <td colSpan="7" style={{ padding: '16px 20px' }}>
                                <div style={{ marginBottom: 12 }}>
                                  <h4 style={{ margin: '0 0 12px 0', color: '#1e293b', fontSize: 14 }}>📦 Itens do Evento no Pedido</h4>
                                  <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                                    <thead>
                                      <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>SKU</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Produto</th>
                                        <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 80 }}>Qtd</th>
                                        <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 100 }}>Unit. Pago</th>
                                        <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 100 }}>Total Pago</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {matchedItems.map((item) => (
                                        <tr key={`${orderKey}-${item.sku}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                          <td style={{ padding: '8px', color: '#64748b', fontFamily: 'monospace' }}>{item.sku || '—'}</td>
                                          <td style={{ padding: '8px', color: '#334155' }}>{item.product_name}</td>
                                          <td style={{ textAlign: 'right', padding: '8px', color: '#64748b' }}>{item.quantity}</td>
                                          <td style={{ textAlign: 'right', padding: '8px', color: '#64748b' }}>{formatBRL(item.paid_unit_price)}</td>
                                          <td style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#1e293b' }}>{formatBRL(item.paid_total)}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
